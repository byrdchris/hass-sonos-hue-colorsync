from __future__ import annotations

import logging
from datetime import timedelta

from aiohttp import ClientError
from homeassistant.components.http.auth import async_sign_path
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.network import get_url

from .cache import PaletteCache
from .const import (
    ATTR_COLOR_COUNT_ACTUAL,
    ATTR_HEX_COLORS,
    ATTR_LAST_SERVICE_DATA,
    ATTR_PALETTE_PREVIEW,
    ATTR_RESOLVED_LIGHTS,
    ATTR_RGB_COLORS,
    ATTR_SOURCE_IMAGE,
    CONF_CACHE,
    CONF_LIGHT_ENTITIES,
    CONF_LIGHT_GROUP,
    CONF_SONOS_ENTITY,
)
from .hue_controller import apply_palette, restore_scene, snapshot_scene
from .palette import extract_palette_from_bytes, rgb_to_hex

_LOGGER = logging.getLogger(__name__)

class SonosHueCoordinator:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.scene = None
        self.enabled = True
        self._remove_listener = None
        self._listeners = []
        self.last_palette = []
        self.last_image = None
        self.last_error = None
        self.last_resolved_lights = []
        self.last_service_data = []
        self.last_resolver_source = None
        self.last_track_key = None
        self.last_processing_reason = None
        self.runtime_assignment_strategy = None
        self.cache = PaletteCache() if self.config.get(CONF_CACHE, True) else None

    @property
    def config(self):
        config = {**self.entry.data, **self.entry.options}
        if self.runtime_assignment_strategy:
            config["assignment_strategy"] = self.runtime_assignment_strategy
        return config

    @property
    def sonos_entity(self):
        return self.config[CONF_SONOS_ENTITY]

    @property
    def light_entities(self):
        if CONF_LIGHT_ENTITIES in self.config and self.config[CONF_LIGHT_ENTITIES]:
            return self.config[CONF_LIGHT_ENTITIES]
        legacy = self.config.get(CONF_LIGHT_GROUP)
        return [legacy] if legacy else []

    @property
    def palette_attributes(self):
        hex_colors = [rgb_to_hex(c) for c in self.last_palette]
        return {
            ATTR_HEX_COLORS: hex_colors,
            ATTR_RGB_COLORS: [list(c) for c in self.last_palette],
            ATTR_COLOR_COUNT_ACTUAL: len(hex_colors),
            ATTR_PALETTE_PREVIEW: self._palette_preview(),
            ATTR_SOURCE_IMAGE: self.last_image,
            ATTR_RESOLVED_LIGHTS: self.last_resolved_lights,
            ATTR_LAST_SERVICE_DATA: self.last_service_data[-20:],
            "last_error": self.last_error,
            "enabled": self.enabled,
            "sonos_entity": self.sonos_entity,
            "light_entities": self.light_entities,
            "selected_entity_members": self._selected_entity_members(),
            "last_track_key": self.last_track_key,
            "last_processing_reason": self.last_processing_reason,
            "selected_light_count": len(self.light_entities),
            "resolved_light_count": len(self.last_resolved_lights),
            "resolver_source": self.last_resolver_source,
            "assignment_strategy": self.config.get("assignment_strategy", "balanced"),
            "runtime_assignment_strategy": self.runtime_assignment_strategy,
        }

    def async_add_listener(self, update_callback):
        self._listeners.append(update_callback)
        def remove():
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)
        return remove

    def _notify(self):
        for listener in list(self._listeners):
            listener()

    def _selected_entity_members(self):
        members = {}
        for entity_id in self.light_entities:
            state = self.hass.states.get(entity_id)
            live = []
            if state is not None:
                value = state.attributes.get("entity_id")
                live = value if isinstance(value, list) else []
            members[entity_id] = {
                "live_entity_id": live,
                "friendly_name": state.attributes.get("friendly_name") if state is not None else None,
            }
        return members


    def _palette_preview(self):
        preview = []
        if self.last_service_data:
            for idx, item in enumerate(self.last_service_data):
                rgb = item.get("rgb_color")
                if not rgb:
                    continue
                preview.append({
                    "index": idx + 1,
                    "hex": rgb_to_hex(tuple(rgb)),
                    "rgb": rgb,
                    "assigned_light": item.get("entity_id"),
                    "gradient_aware": item.get("gradient_aware", False),
                    "assignment_strategy": item.get("assignment_strategy"),
                })
            return preview

        hex_colors = [rgb_to_hex(c) for c in self.last_palette]
        for idx, hex_color in enumerate(hex_colors):
            preview.append({
                "index": idx + 1,
                "hex": hex_color,
                "rgb": list(self.last_palette[idx]),
                "assigned_light": None,
            })
        return preview

    async def async_setup(self):
        _LOGGER.info("Setting up Sonos Hue Sync: sonos=%s lights=%s", self.sonos_entity, self.light_entities)
        await self.async_refresh_listener()
        # Do not process immediately on setup. Hue group attributes may not be populated yet.
        self.last_processing_reason = "setup_waiting_for_event_or_button"
        self._notify()

    async def async_unload(self):
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

    async def async_refresh_listener(self):
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None
        _LOGGER.info("Listening for Sonos state changes on %s", self.sonos_entity)
        self._remove_listener = async_track_state_change_event(self.hass, [self.sonos_entity], self._handle)

    async def async_update_config(self):
        self.cache = PaletteCache() if self.config.get(CONF_CACHE, True) else None
        await self.async_refresh_listener()
        self._notify()
        await self.async_process_current_state(reason="options_update")

    async def _fetch_image_bytes(self, image_path: str):
        try:
            if image_path.startswith("http://") or image_path.startswith("https://"):
                url = image_path
            else:
                base = get_url(self.hass, prefer_external=False)
                if "token=" in image_path:
                    url = f"{base}{image_path}"
                else:
                    signed_path = async_sign_path(
                        self.hass,
                        image_path,
                        expiration=timedelta(seconds=300),
                    )
                    url = f"{base}{signed_path}"

            _LOGGER.debug("Fetching artwork from %s", url)
            session = async_get_clientsession(self.hass)
            async with session.get(url) as resp:
                data = await resp.read()
                if resp.status >= 400:
                    self.last_error = f"image_fetch_failed:http_{resp.status}: {data[:120]!r}"
                    self._notify()
                    return None
                if not data:
                    self.last_error = "image_fetch_failed:empty_response"
                    self._notify()
                    return None
                return data
        except Exception as err:
            self.last_error = f"image_fetch_failed:{type(err).__name__}: {err}"
            _LOGGER.exception("Unable to fetch Sonos artwork from %s", image_path)
            self._notify()
            return None

    def _track_key(self, state):
        attrs = state.attributes
        return "|".join(str(attrs.get(k, "")) for k in (
            "media_content_id", "entity_picture", "media_title", "media_artist", "media_album_name"
        ))

    async def async_process_current_state(self, reason="manual"):
        state = self.hass.states.get(self.sonos_entity)
        if state is None:
            self.last_error = "sonos_entity_not_found"
            self._notify()
            return
        await self._process_state(state, reason=reason, force=True)

    async def async_set_assignment_strategy(self, strategy: str):
        self.runtime_assignment_strategy = strategy
        self._notify()
        if self.last_palette:
            await self._apply_palette_to_lights()

    async def async_apply_last_palette(self):
        if not self.last_palette:
            self.last_error = "no_palette_available"
            self._notify()
            return
        await self._apply_palette_to_lights()

    async def async_test_color(self, rgb):
        self.last_palette = [tuple(rgb)]
        await self._apply_palette_to_lights()

    async def async_test_rainbow(self):
        self.last_palette = [
            (255, 0, 0),
            (255, 127, 0),
            (255, 255, 0),
            (0, 255, 0),
            (0, 0, 255),
            (75, 0, 130),
            (148, 0, 211),
        ]
        await self._apply_palette_to_lights()

    async def _apply_palette_to_lights(self):
        try:
            resolved, last_service_data, resolver_source = await apply_palette(
                self.hass, self.light_entities, self.last_palette, self.config
            )
            self.last_resolved_lights = resolved
            self.last_resolver_source = resolver_source
            self.last_service_data = last_service_data
            self.last_error = None
        except Exception as err:
            self.last_error = f"light_apply_failed: {err}"
            _LOGGER.exception("Failed applying palette/test color")
        self._notify()

    async def _handle(self, event):
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if not new_state:
            return

        old_key = self._track_key(old_state) if old_state else None
        new_key = self._track_key(new_state)

        if new_state.state == "playing" and (old_state is None or old_state.state != "playing" or old_key != new_key):
            await self._process_state(new_state, reason="state_or_metadata_change", force=False)
        elif new_state.state in ["paused", "idle", "off"]:
            await self._handle_stop()

    async def _process_state(self, state, reason="event", force=False):
        self.last_processing_reason = reason

        if not self.enabled:
            self.last_error = "disabled"
            self._notify()
            return

        if state.state != "playing":
            self.last_error = f"not_playing:{state.state}"
            self._notify()
            return

        track_key = self._track_key(state)
        if not force and track_key == self.last_track_key:
            return
        self.last_track_key = track_key

        if not self.scene:
            self.scene = await snapshot_scene(self.hass, self.light_entities)

        art = state.attributes.get("entity_picture")
        if not art:
            self.last_error = "no_entity_picture"
            self._notify()
            return

        self.last_image = art
        self.last_error = None

        try:
            if self.cache and self.cache.exists(art):
                palette = self.cache.get(art)
            else:
                image_bytes = await self._fetch_image_bytes(art)
                if not image_bytes:
                    return
                palette = extract_palette_from_bytes(image_bytes, self.config)
                if self.cache:
                    self.cache.set(art, palette)

            self.last_palette = palette
            self._notify()
            await self._apply_palette_to_lights()
        except Exception as err:
            self.last_error = f"palette_extract_failed: {err}"
            _LOGGER.exception("Failed extracting/applying palette")
            self._notify()

    async def _handle_stop(self):
        if self.scene:
            await restore_scene(self.hass, self.scene)
            self.scene = None
        self._notify()

    async def async_enable(self):
        self.enabled = True
        self._notify()
        await self.async_process_current_state(reason="enabled")

    async def async_disable(self):
        self.enabled = False
        await self._handle_stop()
        self._notify()
