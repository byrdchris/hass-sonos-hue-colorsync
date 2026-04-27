from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

from aiohttp import ClientError
from homeassistant.components.http.auth import async_sign_path
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.network import get_url
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

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
    CONF_GROUP_ENTITIES,
    CONF_MEMBER_LIGHT_ENTITIES,
    CONF_LIGHT_GROUP,
    CONF_SONOS_ENTITY,
    CONF_PALETTE_ORDERING,
    CONF_TRANSITION,
    CONF_AUTO_ROTATE_COLORS,
    CONF_AUTO_ROTATE_INTERVAL,
    DEFAULT_AUTO_ROTATE_INTERVAL,
    MIN_AUTO_ROTATE_INTERVAL,
    MAX_AUTO_ROTATE_INTERVAL,
    AUTO_ROTATE_SAFETY_BUFFER_SECONDS,
)
from .applier import clear_apply_cache
from .hue_controller import apply_palette, resolve_light_entities, resolve_light_entities_detailed, restore_scene, snapshot_scene
from .palette import extract_palette_from_bytes, rgb_to_hex, fallback_palette_from_metadata, warm_neutral_fallback_palette
from .health import build_health_report, format_health_message

_LOGGER = logging.getLogger(__name__)

PALETTE_AFFECTING_OPTIONS = {
    "color_count",
    CONF_PALETTE_ORDERING,
    "filter_dull",
    "filter_bright_white",
    "monochrome_mode",
    "low_color_handling",
}

class SonosHueCoordinator:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.scene = None
        self.enabled = False
        self._remove_listener = None
        self._poll_remove = None
        self._apply_lock = asyncio.Lock()
        self._apply_in_progress = False
        self._apply_rerun_requested = False
        self.last_apply_queue_status = None
        self.last_sonos_attributes = {}
        self._restore_delay_task = None
        self._auto_rotate_task = None
        self._auto_rotate_wake_event = asyncio.Event()
        self.last_auto_rotation_started = None
        self.last_auto_rotation_completed = None
        self.last_auto_rotation_skipped_reason = None
        self.last_auto_rotation_timing = {}
        self._listeners = []
        self.last_palette = []
        self.last_image = None
        self.last_error = None
        self.last_palette_error = None
        self.last_image_fetch_status = None
        self.last_image_fetch_candidates = []
        self.last_artwork_fallback_mode = None
        self.last_artwork_fallback_applied = None
        self.last_fallback_suppressed = None
        self.last_resolved_lights = []
        self.last_service_data = []
        self.last_resolver_source = None
        self.last_resolver_source_map = {}
        self.last_group_resolution = {}
        self.last_skipped_lights = []
        self._frozen_track_key = None
        self._frozen_resolve_result = None
        self.last_track_key = None
        self.last_processing_reason = None
        self.runtime_assignment_strategy = None
        self.runtime_options = {}
        self.reapply_rotation_offset = 0
        self.last_timings = {}
        self.last_cache_result = None
        self.last_restore_result = None
        self.last_restore_snapshot_count = 0
        self.last_health_report = None
        self.cache = PaletteCache() if self.config.get(CONF_CACHE, True) else None

    @property
    def config(self):
        config = {**self.entry.data, **self.entry.options}
        config.update(self.runtime_options)
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
    def group_entities(self):
        return self.config.get(CONF_GROUP_ENTITIES, []) or []

    @property
    def member_light_entities(self):
        return self.config.get(CONF_MEMBER_LIGHT_ENTITIES, []) or []

    @property
    def expansion_entities(self):
        # Additive target list:
        # - Hue lights / groups remain active
        # - Hue groups to expand are added as extra expansion sources
        # - Member lights override acts as an explicit additional direct list
        #
        # The resolver deduplicates after expansion, so overlapping groups are safe.
        entities = []
        for entity_id in self.light_entities + self.group_entities + self.member_light_entities:
            if entity_id and entity_id not in entities:
                entities.append(entity_id)
        return entities

    def _resolved_control_targets(self):
        """Resolve targets and remove excluded lights for apply/snapshot/preview."""
        result = resolve_light_entities_detailed(
            self.hass,
            self.expansion_entities,
            expand_groups=self.config.get("expand_groups", True),
        )
        excluded = set(self.config.get("exclude_light_entities", []) or [])
        if excluded:
            before = list(result.lights)
            result.lights = [entity_id for entity_id in result.lights if entity_id not in excluded]
            for entity_id in before:
                if entity_id in excluded:
                    result.skipped.append({"entity_id": entity_id, "reason": "excluded_by_user"})
        return result

    @property
    def palette_attributes(self):
        hex_colors = [rgb_to_hex(c) for c in self.last_palette]
        return {
            ATTR_HEX_COLORS: hex_colors,
            ATTR_RGB_COLORS: [list(c) for c in self.last_palette],
            ATTR_COLOR_COUNT_ACTUAL: len(hex_colors),
            "palette_ordering": self.config.get(CONF_PALETTE_ORDERING, "vivid_first"),
            ATTR_PALETTE_PREVIEW: self._palette_preview(),
            ATTR_SOURCE_IMAGE: self.last_image,
            ATTR_RESOLVED_LIGHTS: self.last_resolved_lights,
            ATTR_LAST_SERVICE_DATA: self.last_service_data[-20:],
            "last_error": self.last_error,
            "last_palette_error": self.last_palette_error,
            "last_image_fetch_status": self.last_image_fetch_status,
            "last_image_fetch_candidates": self.last_image_fetch_candidates,
            "artwork_fallback_mode": self.last_artwork_fallback_mode,
            "artwork_fallback_applied": self.last_artwork_fallback_applied,
            "fallback_suppressed": self.last_fallback_suppressed,
            "enabled": self.enabled,
            "sonos_entity": self.sonos_entity,
            "sonos_media": self.last_sonos_attributes,
            "light_entities": self.light_entities,
            "group_entities": self.group_entities,
            "member_light_entities": self.member_light_entities,
            "expansion_entities": self.expansion_entities,
            "expansion_source": "additive: light_entities + group_entities + member_light_entities",
            "selected_entity_members": self._selected_entity_members(),
            "last_track_key": self.last_track_key,
            "last_processing_reason": self.last_processing_reason,
            "selected_light_count": len(self.light_entities),
            "resolved_light_count": len(self.last_resolved_lights),
            "expansion_entity_count": len(self.expansion_entities),
            "resolver_source": self.last_resolver_source,
            "resolver_source_map": self.last_resolver_source_map,
            "group_resolution": self.last_group_resolution,
            "skipped_lights": self.last_skipped_lights,
            "assignment_strategy": self.config.get("assignment_strategy", "balanced"),
            "runtime_assignment_strategy": self.runtime_assignment_strategy,
            "runtime_options": self.runtime_options,
            "reapply_rotation_offset": self.reapply_rotation_offset,
            "apply_queue_status": self.last_apply_queue_status,
            "brightness_limits": {"minimum": self.config.get("min_brightness", 30), "maximum": self.config.get("max_brightness", 255), "gradient": self.config.get("gradient_brightness", 255)},
            "excluded_lights": self.config.get("exclude_light_entities", []),
            "restore_delay": self.config.get("restore_delay", 0),
            "auto_rotate_colors": self.config.get(CONF_AUTO_ROTATE_COLORS, False),
            "auto_rotate_interval_seconds": self._auto_rotate_interval_seconds(),
            "auto_rotate_active": bool(self._auto_rotate_task and not self._auto_rotate_task.done()),
            "auto_rotation_timing": self._auto_rotation_timing(),
            "auto_rotation_last_timing": self.last_auto_rotation_timing,
            "auto_rotation_apply_in_progress": self._apply_in_progress,
            "auto_rotation_last_started": self.last_auto_rotation_started,
            "auto_rotation_last_completed": self.last_auto_rotation_completed,
            "auto_rotation_last_skipped_reason": self.last_auto_rotation_skipped_reason,
            "timings": self.last_timings,
            "cache_result": self.last_cache_result,
            "restore_snapshot_count": self.last_restore_snapshot_count,
            "restore_last_result": self.last_restore_result,
            "health_report": self.last_health_report,
        }

    @property
    def target_preview_attributes(self):
        try:
            preview = self._resolved_control_targets()
            preview_targets = preview.lights
            resolver_source = preview.source
            skipped = preview.skipped
        except Exception as err:
            return {
                "preview_error": str(err),
                "preview_targets": [],
                "preview_target_count": 0,
                "expansion_entities": self.expansion_entities,
                "expansion_source": "additive: Hue lights/groups + Additional Hue groups + Additional member lights",
            }

        return {
            "preview_targets": preview_targets,
            "preview_target_count": len(preview_targets),
            "preview_resolver_source": resolver_source,
            "preview_skipped_lights": skipped,
            "preview_source_map": preview.source_map,
            "preview_group_resolution": getattr(preview, "group_diagnostics", {}),
            "expansion_entities": self.expansion_entities,
            "light_targets": self.light_entities,
            "additional_hue_groups": self.group_entities,
            "additional_member_lights": self.member_light_entities,
            "expansion_source": "additive: Hue lights/groups + Additional Hue groups + Additional member lights",
            "selected_entity_members": self._selected_entity_members(),
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
        for entity_id in self.expansion_entities:
            state = self.hass.states.get(entity_id)
            live = []
            if state is not None:
                value = state.attributes.get("entity_id")
                live = value if isinstance(value, list) else []
            members[entity_id] = {
                "state": state.state if state is not None else None,
                "friendly_name": state.attributes.get("friendly_name") if state is not None else None,
                "is_hue_group": state.attributes.get("is_hue_group") if state is not None else None,
                "hue_type": state.attributes.get("hue_type") if state is not None else None,
                "live_entity_id": live,
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
        self._poll_remove = None
        self._apply_lock = asyncio.Lock()
        self._apply_in_progress = False
        self._apply_rerun_requested = False
        self.last_apply_queue_status = None
        self.last_sonos_attributes = {}
        self._restore_delay_task = None
        self._stop_auto_rotate()

    async def async_refresh_listener(self):
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None
        self._poll_remove = None
        self._apply_lock = asyncio.Lock()
        self._apply_in_progress = False
        self._apply_rerun_requested = False
        self.last_apply_queue_status = None
        self.last_sonos_attributes = {}
        self._restore_delay_task = None
        self._stop_auto_rotate()
        _LOGGER.info("Listening for Sonos state changes on %s", self.sonos_entity)
        self._ensure_polling()
        self._remove_listener = async_track_state_change_event(self.hass, [self.sonos_entity], self._handle)

    async def async_update_config(self):
        self.cache = PaletteCache() if self.config.get(CONF_CACHE, True) else None
        await self.async_refresh_listener()
        self._notify()
        await self.async_process_current_state(reason="options_update")



    def _snapshot_sonos_attrs(self, state):
        attrs = state.attributes if state is not None else {}
        self.last_sonos_attributes = {
            "state": state.state if state is not None else None,
            "media_title": attrs.get("media_title"),
            "media_artist": attrs.get("media_artist"),
            "media_album_name": attrs.get("media_album_name"),
            "media_content_id": attrs.get("media_content_id"),
            "media_duration": attrs.get("media_duration"),
            "entity_picture_present": bool(attrs.get("entity_picture")),
            "entity_picture": attrs.get("entity_picture"),
            "media_image_url_present": bool(attrs.get("media_image_url")),
            "media_image_url": attrs.get("media_image_url"),
        }

    def _art_candidates(self, state):
        attrs = state.attributes
        candidates = []
        for key in ("entity_picture", "media_image_url", "media_image_proxy", "thumbnail"):
            value = attrs.get(key)
            if value and value not in candidates:
                candidates.append(value)
        return candidates


    def _palette_for_artwork_failure(self, state, reason: str):
        """Return a fallback palette for artwork failures.

        Transient Sonos/Home Assistant artwork proxy failures should not replace
        an existing useful palette with generic fallback colors. This is common
        with AirPlay-to-Sonos where `/api/media_player_proxy` may intermittently
        return HTTP 500.
        """
        mode = self.config.get("artwork_fallback_mode", "reuse_last")
        desired = int(self.config.get("color_count", 3))
        self.last_artwork_fallback_mode = mode
        self.last_fallback_suppressed = None

        has_previous = bool(self.last_palette)

        if has_previous and reason in ("image_fetch_empty", "image_fetch_failed", "no_artwork"):
            self.last_artwork_fallback_applied = "reuse_existing_palette"
            self.last_palette_error = f"{reason}_reuse_existing_palette"
            self.last_fallback_suppressed = f"suppressed_{mode}_fallback_previous_palette_available"
            return list(self.last_palette)

        if mode == "reuse_last":
            if has_previous:
                self.last_artwork_fallback_applied = "reuse_last_palette"
                self.last_palette_error = f"{reason}_reuse_last_palette"
                return list(self.last_palette)
            self.last_artwork_fallback_applied = "track_based_no_previous_palette"
            self.last_palette_error = f"{reason}_track_based_no_previous_palette"
            return self._metadata_fallback_palette(state)

        if mode == "track_based":
            self.last_artwork_fallback_applied = "track_based"
            self.last_palette_error = f"{reason}_track_based"
            return self._metadata_fallback_palette(state)

        if mode == "warm_neutral":
            self.last_artwork_fallback_applied = "warm_neutral"
            self.last_palette_error = f"{reason}_warm_neutral"
            return warm_neutral_fallback_palette(desired)

        if mode == "do_nothing":
            self.last_artwork_fallback_applied = "do_nothing"
            self.last_palette_error = f"{reason}_do_nothing"
            return None

        self.last_artwork_fallback_applied = "unknown_mode_track_based"
        self.last_palette_error = f"{reason}_unknown_mode_track_based"
        return self._metadata_fallback_palette(state)

    def _metadata_fallback_palette(self, state):
        attrs = state.attributes
        metadata = "|".join(str(attrs.get(key, "")) for key in (
            "media_title",
            "media_artist",
            "media_album_name",
            "media_content_id",
        ))
        return fallback_palette_from_metadata(metadata, int(self.config.get("color_count", 3)))

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
                    self.last_image_fetch_status = f"http_{resp.status}"
                    self.last_error = f"image_fetch_failed:http_{resp.status}: {data[:120]!r}"
                    self._notify()
                    return None
                if not data:
                    self.last_image_fetch_status = "empty_response"
                    self.last_error = "image_fetch_failed:empty_response"
                    self._notify()
                    return None
                self.last_image_fetch_status = f"ok:{len(data)}_bytes"
                return data
        except Exception as err:
            self.last_image_fetch_status = f"exception:{type(err).__name__}"
            self.last_error = f"image_fetch_failed:{type(err).__name__}: {err}"
            _LOGGER.exception("Unable to fetch Sonos artwork from %s", image_path)
            self._notify()
            return None

    def _track_key(self, state):
        attrs = state.attributes
        return "|".join(str(attrs.get(k, "")) for k in (
            "media_content_id", "entity_picture", "media_title", "media_artist", "media_album_name"
        ))

    def _palette_cache_key(self, art: str) -> str:
        """Include palette-affecting options in cache identity.

        This prevents switching Palette Ordering, filters, or Color Count from
        reusing an older palette generated with different extraction settings.
        """
        parts = [
            art or "",
            f"count={self.config.get('color_count', 3)}",
            f"ordering={self.config.get(CONF_PALETTE_ORDERING, 'vivid_first')}",
            f"filter_dull={self.config.get('filter_dull', True)}",
            f"filter_white={self.config.get('filter_bright_white', True)}",
            f"mono={self.config.get('monochrome_mode', 'warm_neutral')}",
            f"low_color={self.config.get('low_color_handling', True)}",
        ]
        return "|".join(str(part) for part in parts)

    async def async_process_current_state(self, reason="manual", bypass_cache=False, force_apply=False):
        state = self.hass.states.get(self.sonos_entity)
        if state is None:
            self.last_error = "sonos_entity_not_found"
            self._notify()
            return
        await self._process_state(state, reason=reason, force=True, bypass_cache=bypass_cache, force_apply=force_apply)

    async def async_set_runtime_option(self, key: str, value, reapply: bool = True):
        self.runtime_options[key] = value
        self._frozen_track_key = None
        self._frozen_resolve_result = None
        if key == "cache":
            from .cache import PaletteCache
            self.cache = PaletteCache() if value else None
        if key == CONF_AUTO_ROTATE_COLORS:
            if value:
                self._maybe_start_auto_rotate()
            else:
                self._stop_auto_rotate()

        if key in (CONF_AUTO_ROTATE_INTERVAL, CONF_TRANSITION):
            self._wake_auto_rotate_timer()
            self._maybe_start_auto_rotate()

        self._notify()

        if key in (CONF_AUTO_ROTATE_COLORS, CONF_AUTO_ROTATE_INTERVAL):
            return

        if not reapply:
            return

        if key in PALETTE_AFFECTING_OPTIONS:
            await self.async_process_current_state(
                reason=f"runtime_option_changed:{key}",
                bypass_cache=True,
                force_apply=True,
            )
            return

        if self.last_palette:
            await self._apply_palette_to_lights(force_apply=True)

    async def async_set_assignment_strategy(self, strategy: str):
        self.runtime_assignment_strategy = strategy
        self.runtime_options["assignment_strategy"] = strategy
        self._notify()
        if self.last_palette:
            await self._apply_palette_to_lights()


    async def async_show_help(self):
        message = """## Sonos Hue Sync quick guide

### Targets
- **Hue lights / groups**: your main lights, room, zone, or group.
- **Additional Hue groups to expand**: add real Hue rooms/zones/groups when the main selection misses members. These are additive.
- **Additional member lights**: add specific individual lights that should always be controlled directly.

### Palette controls
- **Number of Colors**: number of album-art colors to extract. If there are more lights than colors, colors repeat.
- **Palette Ordering**: choose whether extracted palettes keep the most dominant artwork colors first or prioritize vivid, visually distinct colors.
- **Filter Dull Colors**: removes dark, gray, muddy, or low-saturation tones.
- **Filter Bright Whites**: removes harsh pure/cool whites while keeping cream and soft warm whites.
- **Black-and-White Album Handling**: controls grayscale covers so they do not produce random neon colors.
- **Handle Low-Color Album Art**: keeps nearly monochrome covers restrained instead of over-saturating tiny color noise.

### Light behavior
- **Assignment Strategy**:
  - **Balanced**: best default for visible color variety.
  - **Sequential**: applies colors in the selected palette order. With **Dominant Colors First**, this preserves dominance order across lights.
  - **Alternating bright / dim**: alternates light and dark tones.
  - **Brightness order**: sorts colors by lightness; can make similar hues dominate.
- **Transition Time**: fade duration for light changes.
- **Auto Rotate Colors**: automatically cycles the current palette while music is playing.
- **Auto Rotation Interval**: total cycle time between automatic rotation starts. The current **Transition Time** is treated as the fade portion of that cycle, with a conservative internal safety buffer to avoid overlapping Hue updates. Changes take effect immediately while auto-rotation is running.
- **Gradient Pattern**: choose whether gradient lights use the same order, offset order per light, or random order per track.
- **Distribute Colors Across Group Members**: applies colors to individual lights inside groups when members are available.

### Troubleshooting
- Use **Targets** to check which lights will be controlled before a song changes.
- If lights are missing, add them under **Additional member lights**.
- If everything looks like one color, try **Vivid Colors First** palette ordering or **Balanced** assignment.
- If black-and-white art looks too colorful, use **Warm neutral** or **Preserve grayscale**.

### Download diagnostics
For deeper troubleshooting, download diagnostics from:

**Settings → Devices & services → Sonos Hue Sync → three-dot menu → Download diagnostics**

Diagnostics include:
- current configuration and runtime options
- resolved light targets and source mapping
- light capabilities and registry metadata
- Hue bridge runtime summary
- gradient troubleshooting fields
- last service data and skipped-light reasons

Tokens and artwork URLs are redacted.
"""
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Sonos Hue Sync Help",
                "message": message,
                "notification_id": "sonos_hue_sync_help",
            },
            blocking=False,
        )

    async def async_apply_last_palette(self, reason: str = "button_reapply_rotate_colors"):
        """Rotate the current color assignment across lights and reapply.

        This intentionally does not re-extract album art. It uses the current
        palette and frozen target list, then shifts which light receives which
        color. For true-gradient lights, the gradient point order is rotated too.
        """
        if not self.last_palette:
            state = self.hass.states.get(self.sonos_entity)
            if state is not None:
                self.last_palette = self._metadata_fallback_palette(state)
                self.last_palette_error = "reapply_metadata_fallback"
            else:
                self.last_error = "no_palette_available"
                self._notify()
                return

        palette_len = len(self.last_palette or [])
        resolved_len = len(self.last_resolved_lights or [])
        rotate_size = max(palette_len, resolved_len, 1)
        self.reapply_rotation_offset = (int(self.reapply_rotation_offset or 0) + 1) % rotate_size
        self.last_processing_reason = reason

        await self._apply_palette_to_lights(force_apply=True)

    async def async_test_color(self, rgb):
        self.last_palette = [tuple(rgb)]
        await self._apply_palette_to_lights(force_apply=True)

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


    def _resolve_for_track(self):
        """Resolve once per track and freeze targets for the current track.

        If the earlier frozen result used same-area fallback and direct Hue group
        members become available later, refresh the frozen result so Hue room
        membership is not permanently missing a light for the rest of the track.
        """
        if self._frozen_track_key == self.last_track_key and self._frozen_resolve_result is not None:
            frozen = self._frozen_resolve_result
            if "same_area_hue_group_fallback" not in getattr(frozen, "source", ""):
                return frozen

            refreshed = self._resolved_control_targets()
            refreshed_direct = "direct_entity_id_members" in getattr(refreshed, "source", "")
            refreshed_has_more = len(refreshed.lights) > len(frozen.lights)
            if refreshed_direct or refreshed_has_more:
                self._frozen_resolve_result = refreshed
                self.last_group_resolution = getattr(refreshed, "group_diagnostics", {})
                return refreshed

            self.last_group_resolution = getattr(frozen, "group_diagnostics", {})
            return frozen

        result = self._resolved_control_targets()
        self._frozen_track_key = self.last_track_key
        self._frozen_resolve_result = result
        self.last_group_resolution = getattr(result, "group_diagnostics", {})
        return result

    async def _apply_palette_to_lights(self, force_apply=False):
        """Apply current palette with a single-flight guard.

        If multiple triggers arrive while an apply is already running, queue one
        follow-up apply using the latest palette/options instead of stacking
        several overlapping full passes.
        """
        if self._apply_in_progress:
            self._apply_rerun_requested = True
            self.last_apply_queue_status = "queued_latest"
            self._notify()
            return

        async with self._apply_lock:
            self._apply_in_progress = True
            try:
                while True:
                    self._apply_rerun_requested = False
                    apply_started = time.perf_counter()
                    try:
                        if force_apply:
                            clear_apply_cache()
                        frozen = self._resolve_for_track()
                        apply_config = dict(self.config)
                        apply_config["_frozen_resolved_lights"] = frozen.lights
                        apply_config["_frozen_resolver_source"] = frozen.source
                        apply_config["_frozen_skipped_lights"] = frozen.skipped
                        apply_config["_track_key"] = self.last_track_key
                        apply_config["_rotation_offset"] = self.reapply_rotation_offset

                        resolved, last_service_data, resolver_source, skipped_lights = await apply_palette(
                            self.hass, self.expansion_entities, self.last_palette, apply_config
                        )
                        self.last_resolved_lights = resolved
                        self.last_resolver_source = resolver_source
                        self.last_resolver_source_map = frozen.source_map
                        self.last_group_resolution = getattr(frozen, "group_diagnostics", {})
                        self.last_skipped_lights = skipped_lights
                        self.last_service_data = last_service_data
                        self.last_error = None
                        self.last_timings["light_apply_ms"] = round((time.perf_counter() - apply_started) * 1000, 1)
                        self.last_apply_queue_status = "applied"
                    except Exception as err:
                        self.last_error = f"light_apply_failed: {err}"
                        self.last_apply_queue_status = f"failed:{type(err).__name__}"
                        _LOGGER.exception("Failed applying palette/test color")

                    self._notify()

                    if not self._apply_rerun_requested:
                        break
                    force_apply = True
                    self.last_apply_queue_status = "rerun_latest"
            finally:
                self._apply_in_progress = False
                self._maybe_start_auto_rotate()

    def _is_currently_playing(self) -> bool:
        state = self.hass.states.get(self.sonos_entity)
        return bool(state is not None and state.state == "playing")

    def _auto_rotate_interval_seconds(self) -> int:
        value = self.config.get(CONF_AUTO_ROTATE_INTERVAL, DEFAULT_AUTO_ROTATE_INTERVAL)
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = DEFAULT_AUTO_ROTATE_INTERVAL
        return max(MIN_AUTO_ROTATE_INTERVAL, min(MAX_AUTO_ROTATE_INTERVAL, value))

    def _auto_rotate_allowed(self) -> bool:
        return bool(
            self.enabled
            and self.config.get(CONF_AUTO_ROTATE_COLORS, False)
            and self.last_palette
            and self._is_currently_playing()
        )

    def _maybe_start_auto_rotate(self):
        if not self._auto_rotate_allowed():
            return
        if self._auto_rotate_task and not self._auto_rotate_task.done():
            return
        self._auto_rotate_task = self.hass.loop.create_task(self._auto_rotate_loop())
        self._notify()

    def _stop_auto_rotate(self):
        if self._auto_rotate_task and not self._auto_rotate_task.done():
            self._auto_rotate_task.cancel()
        self._auto_rotate_task = None

    def _wake_auto_rotate_timer(self):
        """Wake the active auto-rotation loop so timing changes apply immediately."""
        try:
            self._auto_rotate_wake_event.set()
        except Exception:
            pass

    def _transition_seconds(self) -> float:
        value = self.config.get(CONF_TRANSITION, 0)
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.0
        return max(0.0, min(60.0, value))

    def _auto_rotation_timing(self) -> dict:
        """Return cycle timing for auto rotation.

        Auto Rotation Interval is treated as the total time between rotation
        starts. Transition Time is the fade portion of that cycle. A small
        internal buffer accounts for Home Assistant/Hue service-call latency.
        """
        interval = float(self._auto_rotate_interval_seconds())
        transition = self._transition_seconds()
        safety_buffer = float(AUTO_ROTATE_SAFETY_BUFFER_SECONDS)
        protected_time = transition + safety_buffer
        hold_time = max(0.0, interval - protected_time)
        effective_cycle = protected_time + hold_time
        limited_by_transition = interval < protected_time
        return {
            "configured_interval_seconds": interval,
            "transition_time_seconds": transition,
            "safety_buffer_seconds": safety_buffer,
            "calculated_hold_seconds": round(hold_time, 3),
            "effective_cycle_seconds": round(effective_cycle, 3),
            "limited_by_transition": limited_by_transition,
        }

    async def _auto_rotate_wait(self, seconds: float) -> bool:
        """Wait for auto-rotation timing, waking early on option changes.

        Returns True if an option change woke the timer, False if the timeout
        completed normally. The short polling cadence lets pause/stop/disable
        take effect promptly without waiting for the full interval.
        """
        if seconds <= 0:
            return False

        deadline = time.monotonic() + seconds
        while self._auto_rotate_allowed():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            self._auto_rotate_wake_event.clear()
            try:
                await asyncio.wait_for(
                    self._auto_rotate_wake_event.wait(),
                    timeout=min(1.0, remaining),
                )
                return True
            except asyncio.TimeoutError:
                continue
        return False

    async def _wait_for_apply_idle(self) -> bool:
        """Wait briefly for a current light update to finish before rotating."""
        while self._apply_in_progress:
            self.last_auto_rotation_skipped_reason = "waiting_for_active_light_update"
            self._notify()
            changed = await self._auto_rotate_wait(0.25)
            if changed:
                return False
            if not self._auto_rotate_allowed():
                return False
        return True

    async def _auto_rotate_loop(self):
        try:
            while self._auto_rotate_allowed():
                timing = self._auto_rotation_timing()
                self.last_auto_rotation_timing = timing
                self.last_auto_rotation_skipped_reason = None
                self._notify()

                changed = await self._auto_rotate_wait(timing["effective_cycle_seconds"])
                if changed:
                    continue
                if not self._auto_rotate_allowed():
                    break

                if not await self._wait_for_apply_idle():
                    continue
                if not self._auto_rotate_allowed():
                    break

                self.last_auto_rotation_started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self.last_auto_rotation_skipped_reason = None
                self._notify()
                await self.async_apply_last_palette(reason="auto_rotate_colors")
                self.last_auto_rotation_completed = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._notify()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self.last_error = f"auto_rotate_failed: {err}"
            self.last_auto_rotation_skipped_reason = f"error:{type(err).__name__}"
            _LOGGER.exception("Auto Rotate Colors failed")
            self._notify()
        finally:
            self._auto_rotate_task = None
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

    async def _process_state(self, state, reason="event", force=False, bypass_cache=False, force_apply=False):
        self._cancel_pending_restore()
        process_started = time.perf_counter()
        self.last_timings = {}
        self.last_cache_result = None
        self.last_processing_reason = reason
        self._snapshot_sonos_attrs(state)

        if reason in ("button_extract_now", "extract_now_service") or reason.startswith("runtime_option_changed") or reason == "options_update":
            bypass_cache = True
            force_apply = True

        if not self.enabled:
            self._stop_auto_rotate()
            self.last_error = "disabled"
            self._notify()
            return

        if state.state != "playing":
            self._stop_auto_rotate()
            self.last_error = f"not_playing:{state.state}"
            self._notify()
            return

        track_key = self._track_key(state)
        if not force and track_key == self.last_track_key:
            return
        self.last_track_key = track_key
        self._frozen_track_key = None
        self._frozen_resolve_result = None

        if not self.scene:
            snapshot_targets = self._resolved_control_targets().lights
            if snapshot_targets:
                self.scene = await snapshot_scene(self.hass, snapshot_targets)

        art_candidates = self._art_candidates(state)
        self.last_image_fetch_candidates = art_candidates
        art = art_candidates[0] if art_candidates else None
        if not art:
            palette = self._palette_for_artwork_failure(state, "no_artwork")
            self.last_image = None
            if not palette:
                self.last_error = "no_palette_available"
                self._notify()
                return
            self.last_palette = palette
            self.last_error = None
            self._notify()
            await self._apply_palette_to_lights(force_apply=True)
            self.last_timings["total_processing_ms"] = round((time.perf_counter() - process_started) * 1000, 1)
            return

        self.last_image = art
        self.last_error = None

        try:
            cache_key = self._palette_cache_key(art)
            if self.cache and not bypass_cache and self.cache.exists(cache_key):
                self.last_cache_result = 'hit'
                palette = self.cache.get(cache_key)
            else:
                self.last_cache_result = 'disabled' if not self.cache else 'miss'
                fetch_started = time.perf_counter()
                image_bytes = None
                used_art = None
                for candidate in art_candidates:
                    image_bytes = await self._fetch_image_bytes(candidate)
                    if image_bytes:
                        used_art = candidate
                        break
                self.last_timings['album_art_fetch_ms'] = round((time.perf_counter() - fetch_started) * 1000, 1)
                extract_started = time.perf_counter()
                if not image_bytes:
                    palette = self._palette_for_artwork_failure(state, "image_fetch_empty")
                    if not palette:
                        self.last_error = "no_palette_available"
                        self._notify()
                        return
                    self.last_error = None
                    self.last_palette = palette
                    self._notify()
                    await self._apply_palette_to_lights(force_apply=True)
                    self.last_timings["total_processing_ms"] = round((time.perf_counter() - process_started) * 1000, 1)
                    return
                self.last_image = used_art or art
                palette = extract_palette_from_bytes(image_bytes, self.config)
                self.last_timings['palette_extract_ms'] = round((time.perf_counter() - extract_started) * 1000, 1)
                if self.cache:
                    self.cache.set(cache_key, palette)

            if not palette:
                self.last_palette_error = "palette_empty"
                if self.last_palette:
                    palette = self.last_palette
                    self.last_error = None
                    self.last_palette_error = "palette_fallback_previous"
                else:
                    self.last_error = "no_palette_available"
                    self._notify()
                    return
            else:
                self.last_palette_error = None

            self.last_palette = palette
            self._notify()
            await self._apply_palette_to_lights(force_apply=force_apply)
            self.last_timings['total_processing_ms'] = round((time.perf_counter() - process_started) * 1000, 1)
        except Exception as err:
            self.last_error = f"palette_extract_failed: {err}"
            _LOGGER.exception("Failed extracting/applying palette")
            self._notify()


    def _cancel_pending_restore(self):
        if self._restore_delay_task and not self._restore_delay_task.done():
            self._restore_delay_task.cancel()
        self._restore_delay_task = None

    async def _restore_after_delay(self, delay: float):
        try:
            if delay > 0:
                await asyncio.sleep(delay)
            if self.scene:
                try:
                    self.last_restore_snapshot_count = len(self.scene) if hasattr(self.scene, "__len__") else 1
                    await restore_scene(self.hass, self.scene)
                    self.last_restore_result = "restored"
                except Exception as err:
                    self.last_restore_result = f"failed: {err}"
                    _LOGGER.exception("Failed restoring Sonos Hue Sync scene")
                self.scene = None
            clear_apply_cache()
            self._notify()
        except asyncio.CancelledError:
            self.last_restore_result = "cancelled"
            raise

    async def _handle_stop(self):
        self._stop_auto_rotate()
        delay = float(self.config.get("restore_delay", 0) or 0)
        self._cancel_pending_restore()
        self._restore_delay_task = self.hass.loop.create_task(self._restore_after_delay(delay))

    async def async_health_check(self) -> dict:
        """Run a user-facing integration health check."""
        report = build_health_report(self.hass, self)
        self.last_health_report = report
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Sonos Hue Sync Health Check",
                "message": format_health_message(report),
                "notification_id": "sonos_hue_sync_health_check",
            },
            blocking=False,
        )
        self._notify()
        return report


    async def _poll_playing_sonos(self, now=None):
        """Fallback poll for AirPlay/Sonos metadata sources that do not emit reliable HA state events."""
        if not self.enabled:
            return
        state = self.hass.states.get(self.sonos_entity)
        if state is None:
            return
        if state.state != "playing":
            return

        attrs = state.attributes
        track_key = self._track_key(state)
        current_key = self.last_track_key

        # Only process if track/art metadata changed since the last successful/attempted run.
        if track_key and track_key != current_key:
            await self._process_state(state, reason="airplay_poll_metadata_change", force=True, bypass_cache=False, force_apply=True)

    def _ensure_polling(self):
        interval = int(self.config.get("airplay_poll_interval", 5) or 5)
        interval = max(2, min(60, interval))
        if self._poll_remove is not None:
            return
        self._poll_remove = async_track_time_interval(
            self.hass,
            self._poll_playing_sonos,
            timedelta(seconds=interval),
        )

    def _stop_polling(self):
        if self._poll_remove is not None:
            self._poll_remove()
            self._poll_remove = None
        self._apply_lock = asyncio.Lock()
        self._apply_in_progress = False
        self._apply_rerun_requested = False
        self.last_apply_queue_status = None

    async def async_enable(self):
        self.enabled = True
        self._ensure_polling()
        self._notify()
        await self.async_process_current_state(reason="enabled")

    async def async_disable(self):
        self.last_processing_reason = "sync_disabled"
        self.enabled = False
        self._stop_auto_rotate()
        self._stop_polling()
        await self._handle_stop()
        self._notify()