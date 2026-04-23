from __future__ import annotations

import logging
from aiohttp import ClientError
from homeassistant.components.http.auth import async_sign_path
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.network import get_url

from .cache import PaletteCache
from .const import (
    ATTR_HEX_COLORS,
    ATTR_LAST_SERVICE_DATA,
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
        self.cache = PaletteCache() if self.config.get(CONF_CACHE, True) else None

    @property
    def config(self):
        return {**self.entry.data, **self.entry.options}

    @property
    def sonos_entity(self):
        return self.config[CONF_SONOS_ENTITY]

    @property
    def light_entities(self):
        if CONF_LIGHT_ENTITIES in self.config and self.config[CONF_LIGHT_ENTITIES]:
            return self.config[CONF_LIGHT_ENTITIES]
        # backward compatibility with old single selector
        legacy = self.config.get(CONF_LIGHT_GROUP)
        return [legacy] if legacy else []

    @property
    def palette_attributes(self):
        return {
            ATTR_HEX_COLORS: [rgb_to_hex(c) for c in self.last_palette],
            ATTR_RGB_COLORS: [list(c) for c in self.last_palette],
            ATTR_SOURCE_IMAGE: self.last_image,
            ATTR_RESOLVED_LIGHTS: self.last_resolved_lights,
            ATTR_LAST_SERVICE_DATA: self.last_service_data,
            "last_error": self.last_error,
            "enabled": self.enabled,
            "sonos_entity": self.sonos_entity,
            "light_entities": self.light_entities,
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

    async def async_setup(self):
        await self.async_refresh_listener()

    async def async_unload(self):
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

    async def async_refresh_listener(self):
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None
        self._remove_listener = async_track_state_change_event(
            self.hass, [self.sonos_entity], self._handle
        )

    async def async_update_config(self):
        self.cache = PaletteCache() if self.config.get(CONF_CACHE, True) else None
        await self.async_refresh_listener()
        self._notify()

    async def _fetch_image_bytes(self, image_path: str):
        try:
            if image_path.startswith("http://") or image_path.startswith("https://"):
                url = image_path
            else:
                signed_path = async_sign_path(self.hass, image_path, expiration=300)
                base = get_url(self.hass, prefer_external=False)
                url = f"{base}{signed_path}"

            session = async_get_clientsession(self.hass)
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.read()
        except (ClientError, ValueError) as err:
            self.last_error = f"image_fetch_failed: {err}"
            _LOGGER.warning("Unable to fetch Sonos artwork from %s: %s", image_path, err)
            self._notify()
            return None

    async def async_apply_last_palette(self):
        if not self.last_palette:
            self.last_error = "no_palette_available"
            self._notify()
            return
        try:
            resolved, last_service_data = await apply_palette(
                self.hass, self.light_entities, self.last_palette, self.config
            )
            self.last_resolved_lights = resolved
            self.last_service_data = last_service_data
            self.last_error = None
        except Exception as err:
            self.last_error = f"light_apply_failed: {err}"
            _LOGGER.exception("Failed applying last palette")
        self._notify()

    async def async_test_color(self, rgb):
        palette = [tuple(rgb)]
        try:
            resolved, last_service_data = await apply_palette(
                self.hass, self.light_entities, palette, self.config
            )
            self.last_resolved_lights = resolved
            self.last_service_data = last_service_data
            self.last_error = None
        except Exception as err:
            self.last_error = f"light_apply_failed: {err}"
            _LOGGER.exception("Failed applying test color")
        self._notify()

    async def _handle(self, event):
        state = event.data.get("new_state")
        if not state or not self.enabled:
            return

        if state.state == "playing":
            if not self.scene:
                self.scene = await snapshot_scene(self.hass, self.light_entities)

            art = state.attributes.get("entity_picture")
            if not art:
                self.last_error = "no_entity_picture"
                self._notify()
                return

            self.last_image = art
            self.last_error = None

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

            try:
                resolved, last_service_data = await apply_palette(
                    self.hass, self.light_entities, palette, self.config
                )
                self.last_resolved_lights = resolved
                self.last_service_data = last_service_data
                self.last_error = None
            except Exception as err:
                self.last_error = f"light_apply_failed: {err}"
                _LOGGER.exception("Failed applying palette")
            self._notify()

        elif state.state in ["paused", "idle", "off"]:
            await self._handle_stop()

    async def _handle_stop(self):
        if self.scene:
            await restore_scene(self.hass, self.scene)
            self.scene = None
        self._notify()

    async def async_enable(self):
        self.enabled = True
        self._notify()

    async def async_disable(self):
        self.enabled = False
        await self._handle_stop()
        self._notify()
