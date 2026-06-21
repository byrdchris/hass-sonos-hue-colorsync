from .media_adapter import resolve_media_snapshot
from __future__ import annotations

# Runtime coordinator. Handles Sonos events, advanced config resolution, palette updates, rotation, and scene restore.
# brief-code-commented-build: moderate block-level comments added for maintainability.

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
    CONF_ARTWORK_STYLE,
    CONF_AUTO_STYLE_BEHAVIOR,
    CONF_NEUTRAL_TONE_HANDLING,
    CONF_LIGHT_ENTITIES,
    CONF_GROUP_ENTITIES,
    CONF_MEMBER_LIGHT_ENTITIES,
    CONF_LIGHT_GROUP,
    CONF_SONOS_ENTITY,
    CONF_PALETTE_ORDERING,
    CONF_COLOR_ACCURACY_MODE,
    CONF_TRANSITION,
    CONF_AUTO_ROTATE_COLORS,
    CONF_AUTO_ROTATE_INTERVAL,
    DEFAULT_AUTO_ROTATE_INTERVAL,
    MIN_AUTO_ROTATE_INTERVAL,
    MAX_AUTO_ROTATE_INTERVAL,
    AUTO_ROTATE_SAFETY_BUFFER_SECONDS,
    CONF_WHITE_HANDLING,
    CONF_ROTATION_MODE,
    CONF_COLOR_PURITY,
    CONF_PALETTE_COHERENCE,
    CONF_WHITE_LEVEL,
    ROTATION_MODE_TRACK_CHANGE,
    ROTATION_MODE_OFF,
    ROTATION_MODE_AUTO,
    ROTATION_MODE_TRACK_AND_AUTO,
)
from .applier import clear_apply_cache
from .hue_controller import apply_palette, resolve_light_entities, resolve_light_entities_detailed, restore_scene, snapshot_scene, _snapshot_count
from .palette import extract_palette_from_bytes, rgb_to_hex, fallback_palette_from_metadata, warm_neutral_fallback_palette
from .health import build_health_report, format_health_message

_LOGGER = logging.getLogger(__name__)

PALETTE_AFFECTING_OPTIONS = {
    "color_count",
    CONF_PALETTE_ORDERING,
    CONF_COLOR_ACCURACY_MODE,
    CONF_ARTWORK_STYLE,
    CONF_AUTO_STYLE_BEHAVIOR,
    CONF_NEUTRAL_TONE_HANDLING,
    CONF_COLOR_PURITY,
    CONF_PALETTE_COHERENCE,
    CONF_WHITE_LEVEL,
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
        self.last_sonos_attributes = {
        # v1.2.21 media snapshot
        # v1.2.22 pipeline ordering enforced
        self.media_snapshot = resolve_media_snapshot(self.sonos_entity, state)
        if state else None
        }
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
        self.last_palette_track_key = None
        self.last_processing_reason = None
        self.runtime_assignment_strategy = None
        self.runtime_options = {}
        self.reapply_rotation_offset = 0
        self.last_timings = {}
        self.last_cache_result = None
        self.last_restore_result = None
        self.last_restore_snapshot_count = 0
        self.last_restore_reason = None
        self.last_health_report = None
        self.last_palette_coherence = {}
        self.last_detected_artwork_style = None
        self.last_auto_artwork_style_diagnostics = {}
        self.last_auto_style_behavior_diagnostics = {}
        self.last_final_palette_guardrails = {}
        self.last_advanced_overrides_active = False
        self.cache = PaletteCache() if self.config.get(CONF_CACHE, True) else None

    @property
    def config(self):
        config = {**self.entry.data, **self.entry.options}
        config.update(self.runtime_options)
        if self.runtime_assignment_strategy:
            config["assignment_strategy"] = self.runtime_assignment_strategy
        return config

    # Resolve one effective configuration immediately before light updates.
    # This avoids race conditions by not syncing current color controls together.
    def effective_config(self) -> dict:
        """Resolve the one authoritative config used for palette/apply work.

        v1.2.0 removes legacy mode. All visible controls are
        authoritative, with Color Purity and White Suppression kept separate so
        album-color fidelity and white suppression can be tuned independently.
        """
        config = dict(self.config)
        config.setdefault(CONF_COLOR_PURITY, 65)
        config.setdefault(CONF_WHITE_LEVEL, 50)
        config.setdefault(CONF_PALETTE_COHERENCE, "balanced")
        config["_effective_brightness_source"] = "Brightness controls"
        config["_effective_white_source"] = "White Handling + White Level"
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
        effective = self.effective_config()
        entities = []
        source_entities = (
            self.light_entities
            + (effective.get(CONF_GROUP_ENTITIES, []) or [])
            + (effective.get(CONF_MEMBER_LIGHT_ENTITIES, []) or [])
        )
        for entity_id in source_entities:
            if entity_id and entity_id not in entities:
                entities.append(entity_id)
        return entities

    def _resolved_control_targets(self):
        """Resolve targets and remove excluded lights for apply/snapshot/preview."""
        result = resolve_light_entities_detailed(
            self.hass,
            self.expansion_entities,
            expand_groups=self.effective_config().get("expand_groups", True),
        )
        excluded = set(self.effective_config().get("exclude_light_entities", []) or [])
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
        effective = self.effective_config()
        return {
            ATTR_HEX_COLORS: hex_colors,
            ATTR_RGB_COLORS: [list(c) for c in self.last_palette],
            ATTR_COLOR_COUNT_ACTUAL: len(hex_colors),
            "artwork_style": effective.get(CONF_ARTWORK_STYLE),
            "auto_style_behavior": effective.get(CONF_AUTO_STYLE_BEHAVIOR),
            "neutral_tone_handling": effective.get(CONF_NEUTRAL_TONE_HANDLING),
            "detected_artwork_style": getattr(self, "last_detected_artwork_style", None),
            "auto_artwork_style_diagnostics": getattr(self, "last_auto_artwork_style_diagnostics", {}),
            "auto_style_behavior_diagnostics": getattr(self, "last_auto_style_behavior_diagnostics", {}),
            "final_palette_guardrails": getattr(self, "last_final_palette_guardrails", {}),
            "advanced_overrides_active": getattr(self, "last_advanced_overrides_active", False),
            "artwork_style_applied": effective.get("_artwork_style_applied"),
            "neutral_tone_handling_applied": effective.get("_neutral_tone_handling_applied"),
            "artwork_style_diagnostics": effective.get("_artwork_style_diagnostics", {}),
            "palette_ordering": effective.get(CONF_PALETTE_ORDERING, self.config.get(CONF_PALETTE_ORDERING, "vivid_first")),
            "color_accuracy_mode": effective.get(CONF_COLOR_ACCURACY_MODE, self.config.get(CONF_COLOR_ACCURACY_MODE, "natural")),
            "color_purity": self.config.get(CONF_COLOR_PURITY, 65),
            "palette_coherence": self.config.get(CONF_PALETTE_COHERENCE, "balanced"),
            "palette_coherence_diagnostics": self.last_palette_coherence,
            "white_level": self.config.get(CONF_WHITE_LEVEL, 50),
            "effective_brightness_source": effective.get("_effective_brightness_source"),
            "effective_white_source": effective.get("_effective_white_source"),
            "ignored_advanced_controls": effective.get("_ignored_advanced_controls", []),
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
            "brightness_limits": {"minimum": effective.get("min_brightness", 30), "maximum": effective.get("max_brightness", 255), "gradient": effective.get("gradient_brightness", 255)},
            "excluded_lights": self.config.get("exclude_light_entities", []),
            "restore_delay": self.config.get("restore_delay", 0),
            "color_rotation": self._rotation_effective_state(),
            "auto_rotate_colors": self.config.get(CONF_AUTO_ROTATE_COLORS, False),
            "color_rotation_mode": self._rotation_mode(),
            "rotate_on_track_change": self._rotate_on_track_change_enabled(),
            "continuous_rotation_enabled": self._auto_rotate_enabled(),
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
            "restore_last_reason": self.last_restore_reason,
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
        self.last_sonos_attributes = {
        # v1.2.21 media snapshot
        # v1.2.22 pipeline ordering enforced
        self.media_snapshot = resolve_media_snapshot(self.sonos_entity, state)
        if state else None
        }
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
        self.last_sonos_attributes = {
        # v1.2.21 media snapshot
        # v1.2.22 pipeline ordering enforced
        self.media_snapshot = resolve_media_snapshot(self.sonos_entity, state)
        if state else None
        }
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
        # v1.2.21 media snapshot
        # v1.2.22 pipeline ordering enforced
        self.media_snapshot = resolve_media_snapshot(self.sonos_entity, state)
        if state else None
        
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
        current_track_key = self._track_key(state) if state else None
        same_palette_track = bool(
            has_previous
            and current_track_key
            and self.last_palette_track_key
            and current_track_key == self.last_palette_track_key
        )

        # Reuse an existing palette only when it belongs to the same track.
        # This prevents transient artwork HTTP errors from painting a new track
        # with stale colors from the previous album.
        if same_palette_track and reason in ("image_fetch_empty", "image_fetch_failed", "no_artwork"):
            self.last_artwork_fallback_applied = "reuse_existing_palette_same_track"
            self.last_palette_error = f"{reason}_reuse_existing_palette_same_track"
            self.last_fallback_suppressed = f"suppressed_{mode}_fallback_same_track_palette_available"
            return list(self.last_palette)

        if mode == "reuse_last":
            if same_palette_track:
                self.last_artwork_fallback_applied = "reuse_last_palette_same_track"
                self.last_palette_error = f"{reason}_reuse_last_palette_same_track"
                return list(self.last_palette)
            self.last_artwork_fallback_applied = "track_based_stale_palette_blocked"
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
            f"count={self.effective_config().get('color_count', 3)}",
            f"artwork_style={self.effective_config().get(CONF_ARTWORK_STYLE, 'auto')}",
            f"auto_style_behavior={self.effective_config().get(CONF_AUTO_STYLE_BEHAVIOR, 'balanced')}",
            f"neutral_tone={self.effective_config().get(CONF_NEUTRAL_TONE_HANDLING, 'natural')}",
            f"ordering={self.effective_config().get(CONF_PALETTE_ORDERING, 'vivid_first')}",
            f"color_accuracy={self.effective_config().get(CONF_COLOR_ACCURACY_MODE, 'natural' )}",
            f"color_purity={self.effective_config().get(CONF_COLOR_PURITY, 65)}",
            f"palette_coherence={self.effective_config().get(CONF_PALETTE_COHERENCE, 'balanced')}",
            f"white={self.effective_config().get('white_handling', 'suppress_when_color_exists')}",
            f"white_level={self.effective_config().get(CONF_WHITE_LEVEL, 50)}",
            f"mono={self.effective_config().get('monochrome_mode', 'warm_neutral')}",
            f"low_color={self.effective_config().get('low_color_handling', True)}",
        ]
        return "|".join(str(part) for part in parts)

    # Public apply trigger used by buttons, options changes, and other manual refresh paths.
    # The actual apply pipeline resolves effective settings at runtime before touching lights.
    async def async_process_current_state(self, reason="manual", bypass_cache=False, force_apply=False, allow_disabled=False):
        state = self.hass.states.get(self.sonos_entity)
        if state is None:
            self.last_error = "sonos_entity_not_found"
            self._notify()
            return
        await self._process_state(state, reason=reason, force=True, bypass_cache=bypass_cache, force_apply=force_apply, allow_disabled=allow_disabled)

    async def async_set_runtime_option(self, key: str, value, reapply: bool = True):
        self.runtime_options[key] = value
        try:
            options = dict(self.entry.options)
            options[key] = value
            self.hass.config_entries.async_update_entry(self.entry, options=options)
        except Exception:
            pass
        self._frozen_track_key = None
        self._frozen_resolve_result = None
        if key == "cache":
            from .cache import PaletteCache
            self.cache = PaletteCache() if value else None
        if key == CONF_ROTATION_MODE:
            if self._auto_rotate_enabled():
                self._maybe_start_auto_rotate()
            else:
                self._stop_auto_rotate()

        if key == CONF_AUTO_ROTATE_COLORS:
            if self._auto_rotate_enabled():
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
        message = """## Sonos Hue Sync Help & Guide

### What it does
Sonos Hue Sync watches the selected Sonos player, extracts colors from the current album art, applies those colors to Hue lights, and restores the previous lighting state when playback stops or Sync is turned off.

### Artwork Style
**Artwork Style** is the main color interpretation control. Use **Auto** for playlists so the integration chooses a conservative style per track from local image statistics. No cloud service or AI service is used.

- **Auto** analyzes the album art and lightly adapts per track. If Auto confidence is low, the integration falls back to Album Accurate handling instead of applying an aggressive stylized preset.
- **Album Accurate** preserves the album cover’s intended colors, including muted and neutral tones.
- **Ambient** softens the palette for comfortable room lighting without heavy recoloring.
- **Vivid** favors stronger color energy and saturated accents.
- **High Contrast** increases light/dark and color separation for graphic or poster-like covers.
- **Monochrome / Neutral** is for black-and-white, grayscale, beige, cream, or mostly neutral covers. It preserves neutral structure and avoids inventing unrelated red/pink warmth.

Legacy style values such as Photography, Cinematic, and the older Graphic / Poster names are still understood internally for saved configurations, but the visible UI uses the simpler choices above.

### Auto Intensity
This only affects **Artwork Style → Auto**. Auto remains conservative by default.
- **Subtle** stays closest to the extracted album colors and is the default.
- **Balanced** allows moderate Auto shaping when confidence is good.
- **Expressive** adds a modest visible color/contrast lift without forcing a drastic vivid or ambient reinterpretation.

### Neutral Tone Handling
**Neutral Tone Handling** controls whites, grays, blacks, cream, and beige tones.
- **Natural** preserves neutral tones unless white reduction is clearly useful.
- **Reduce Whites** suppresses pale whites, creams, and light grays.
- **Warm Neutral** turns neutral-heavy art into warmer room lighting. It is constrained for normal colorful artwork so it does not recolor valid album palettes into unrelated brown/red tones.
- **Preserve Contrast** keeps stronger black/white or light/dark separation when the artwork depends on it.

### Advanced color controls
Advanced controls are still available in the options form for compatibility and fine tuning. They are not removed.
- **Color Accuracy Mode** controls the older broad extraction behavior.
- **Color Purity Preset** controls saturation filtering with named presets instead of a raw slider.
- **Palette Ordering** prefers dominant colors or vivid colors first.
- **Palette Coherence** removes isolated outlier colors.
- **White Handling**, **White Suppression**, and **Black & White Handling** remain available as lower-level tuning controls.

### Light behavior
- **Hue lights / groups** select the primary rooms, zones, groups, or individual lights to control.
- **Additional Hue groups** and **Additional member lights** add more targets.
- **Excluded lights** are never changed, even if they are members of a selected group.
- **Color Distribution Mode** controls how colors are assigned across lights: Balanced, Sequential, Alternating bright / dim, or Brightness order.
- **Number of Colors** controls how many album-art colors are extracted.
- **Transition Time** controls fade duration.
- **Minimum Brightness** and **Maximum Brightness** bound standard-light brightness.
- **Restore Delay** waits before restoring the previous lighting state after playback stops. Turning Sync off always restores immediately and does not wait for this delay.

### Gradient lights
- **Enable True Gradient** sends multi-point gradients to supported Hue gradient lights while standard lights still receive normal colors.
- **Gradient Detail Level** controls how many gradient points are sent.
- **Gradient Brightness** controls the brightness ceiling for supported gradient lights.
- **Gradient Pattern** controls color order inside gradients: Same Order, Offset, Random Order, Dark to Light, or Light to Dark.
- **Gradient Neutral Suppression** avoids gray/black/white-like gradient anchors on Hue gradient lights when usable colorized anchors are available. This is gradient-only and does not change standard Hue Play lights.
- For Dark to Light and Light to Dark, the selected gradient direction is locked. Artwork Style Auto may change which colors are extracted, but it does not change how the ordered ramp flows. The chosen palette anchors are kept stable, sorted by gamma-corrected perceptual luminance as the final layout step, and rotation is suppressed so the ramp is not reversed.

### Rotation and animation
- **Color Rotation** is the single control for rotation behavior: Off, On Track Change, Continuous, or Track Change and Continuous.
- **On Track Change** rotates colors once per new song.
- **Continuous** rotates the current palette on the timer while music keeps playing.
- **Auto Rotation Interval** is the full cycle timing.
- **Rotate Colors** manually shifts the current palette without re-extracting album art.

### Manual actions
- **Update Lights Now** fetches current artwork and applies colors immediately.
- **Refresh Colors** re-extracts colors for the current artwork.
- **Rotate Colors** reapplies the current palette with a shifted assignment.
- **Test Lighting** sends a test color pattern.
- **Health Check** checks Sonos availability, target resolution, Hue bridge state, gradient capability, and last run status.

### Diagnostics
The Status sensor exposes the current palette, resolved lights, selected artwork style, detected artwork style, auto detection confidence, detection reasons, monochrome guardrail status, neutral tone handling, runtime options, last service data, cache result, restore result, restore reason, gradient diagnostics, palette diagnostics, and timing data.

Download diagnostics from:

**Settings → Devices & services → Sonos Hue Sync → three-dot menu → Download diagnostics**

### Common troubleshooting
- For playlists with mixed artwork, use **Artwork Style → Auto** and adjust **Auto Intensity** if the results are too subtle or too expressive.
- For poster-like covers with red/black/white typography, use **High Contrast** or let **Auto** detect it.
- For black-and-white covers, use **Monochrome / Neutral** or let **Auto** detect it. Auto will preserve grayscale when diagnostics show high neutral ratio and near-zero vivid color.
- If colors look pastel or unrelated, try **High Contrast** or **Vivid**.
- If colors look too harsh, use **Ambient**, **Album Accurate**, or Auto Intensity → Subtle.
- If palette ordering appears unchanged, use Sequential distribution and set Color Rotation to Off.
- If gradients look reversed, check Status diagnostics for luminance values and rotation suppression.
- If too many lights change, use Excluded lights or review the Targets sensor.
- If lights do not restore, check Status → restore result and restore reason. Sync Off should show an immediate forced restore; music stop/pause should show pending until Restore Delay expires.
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

    def _advance_rotation_offset(self, reason: str) -> None:
        palette_len = len(self.last_palette or [])
        resolved_len = len(self.last_resolved_lights or [])
        rotate_size = max(palette_len, resolved_len, 1)
        self.reapply_rotation_offset = (int(self.reapply_rotation_offset or 0) + 1) % rotate_size
        self.runtime_options["last_rotation_reason"] = reason

    # Manual Update Lights Now action.
    # Runs the same apply pipeline as playback without requiring Sync to be enabled.
    async def async_update_lights_now(self):
        """Manually update lights using the current track/artwork and effective settings.

        This intentionally works even when Sync Active is off, so the button can
        be used as a one-off test or manual refresh without enabling automation.
        """
        await self.async_process_current_state(
            reason="manual_update",
            bypass_cache=True,
            force_apply=True,
            allow_disabled=True,
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

        self._advance_rotation_offset(reason)
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

    # Final light update step.
    # Resolves current targets and sends either gradient or standard Hue updates.
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
                        apply_config = dict(self.effective_config())
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

    def _rotation_mode(self) -> str:
        return str(self.config.get(CONF_ROTATION_MODE, ROTATION_MODE_TRACK_CHANGE) or ROTATION_MODE_TRACK_CHANGE)

    def _auto_rotate_enabled(self) -> bool:
        # The Color Rotation selector is authoritative. The legacy Auto Rotate
        # switch value is retained only for stored-config compatibility and no
        # longer overrides Off or On Track Change.
        return self._rotation_mode() in (ROTATION_MODE_AUTO, ROTATION_MODE_TRACK_AND_AUTO)

    def _rotate_on_track_change_enabled(self) -> bool:
        # Track-change rotation is controlled by the same Color Rotation selector
        # so users do not have to reason about a separate enable switch.
        return self._rotation_mode() in (ROTATION_MODE_TRACK_CHANGE, ROTATION_MODE_TRACK_AND_AUTO)

    def _rotation_effective_state(self) -> dict:
        # Expose the resolved rotation behavior for diagnostics and support.
        mode = self._rotation_mode()
        ordered_gradient = str(self.config.get("gradient_order_mode", "")) in ("dark_to_light", "light_to_dark")
        timed_enabled = mode in (ROTATION_MODE_AUTO, ROTATION_MODE_TRACK_AND_AUTO)
        track_enabled = mode in (ROTATION_MODE_TRACK_CHANGE, ROTATION_MODE_TRACK_AND_AUTO)
        return {
            "mode": mode,
            "track_change_enabled": bool(track_enabled),
            "continuous_enabled": bool(timed_enabled),
            "legacy_auto_rotate_value": bool(self.config.get(CONF_AUTO_ROTATE_COLORS, False)),
            "legacy_auto_rotate_ignored": bool(self.config.get(CONF_AUTO_ROTATE_COLORS, False) and mode not in (ROTATION_MODE_AUTO, ROTATION_MODE_TRACK_AND_AUTO)),
            "ordered_gradient_rotation_suppressed": bool(ordered_gradient),
            "reason": (
                "off" if mode == ROTATION_MODE_OFF else
                "track_change" if mode == ROTATION_MODE_TRACK_CHANGE else
                "continuous" if mode == ROTATION_MODE_AUTO else
                "track_change_and_continuous"
            ),
        }

    def _auto_rotate_allowed(self) -> bool:
        return bool(
            self.enabled
            and self._auto_rotate_enabled()
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
            _LOGGER.exception("Continuous color rotation failed")
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
            await self._handle_stop(reason="playback_stopped")

    # Main playback apply pipeline.
    # Fetches artwork, resolves current settings, extracts colors, and updates Hue targets.
    async def _process_state(self, state, reason="event", force=False, bypass_cache=False, force_apply=False, allow_disabled=False):
        process_started = time.perf_counter()
        self.last_timings = {}
        self.last_cache_result = None
        self.last_processing_reason = reason
        self._snapshot_sonos_attrs(state)

        if reason in ("button_extract_now", "extract_now_service") or reason.startswith("runtime_option_changed") or reason == "options_update":
            bypass_cache = True
            force_apply = True

        if not self.enabled and not allow_disabled:
            self._stop_auto_rotate()
            self.last_error = "disabled"
            self._notify()
            return

        if state.state != "playing":
            self._stop_auto_rotate()
            self.last_error = f"not_playing:{state.state}"
            self._notify()
            return

        # A real playback/apply run means music has resumed. Only this path
        # should cancel a delayed playback-stop restore. Options changes or
        # manual buttons while not playing must not cancel restore.
        self._cancel_pending_restore(reason="playback_resumed_or_palette_apply")

        track_key = self._track_key(state)
        previous_track_key = self.last_track_key
        if not force and track_key == previous_track_key:
            return
        is_new_track = bool(previous_track_key and track_key and track_key != previous_track_key)
        self.last_track_key = track_key
        self._frozen_track_key = None
        self._frozen_resolve_result = None
        if is_new_track and self._rotate_on_track_change_enabled() and self.last_palette:
            self._advance_rotation_offset("track_change")

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
            self.last_palette_track_key = self.last_track_key
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
                    self.last_palette_track_key = self.last_track_key
                    self._notify()
                    await self._apply_palette_to_lights(force_apply=True)
                    self.last_timings["total_processing_ms"] = round((time.perf_counter() - process_started) * 1000, 1)
                    return
                self.last_image = used_art or art
                # Artwork was fetched successfully, so fallback modes must not
                # tint or otherwise influence this palette. Keep diagnostics
                # explicit so stale fallback state is not mistaken for active work.
                self.last_artwork_fallback_mode = self.config.get("artwork_fallback_mode", "reuse_last")
                self.last_artwork_fallback_applied = "not_used_artwork_fetch_succeeded"
                self.last_fallback_suppressed = None
                # Build one effective palette config and let extraction attach
                # coherence diagnostics to it for the Status sensor.
                palette_config = self.effective_config()
                palette_config["_artwork_fetch_succeeded"] = True
                palette = extract_palette_from_bytes(image_bytes, palette_config)
                self.last_palette_coherence = palette_config.get("_palette_coherence_diagnostics", {})
                self.last_detected_artwork_style = palette_config.get("_auto_artwork_style_detected")
                self.last_auto_artwork_style_diagnostics = palette_config.get("_auto_artwork_style_diagnostics", {})
                self.last_auto_style_behavior_diagnostics = palette_config.get("_auto_style_behavior_diagnostics", {})
                self.last_final_palette_guardrails = palette_config.get("_final_palette_guardrails", {})
                self.last_advanced_overrides_active = bool(palette_config.get("_advanced_overrides_active", False))
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
            self.last_palette_track_key = self.last_track_key
            self._notify()
            await self._apply_palette_to_lights(force_apply=force_apply)
            self.last_timings['total_processing_ms'] = round((time.perf_counter() - process_started) * 1000, 1)
        except Exception as err:
            self.last_error = f"palette_extract_failed: {err}"
            _LOGGER.exception("Failed extracting/applying palette")
            self._notify()


    def _cancel_pending_restore(self, reason="cancelled"):
        """Cancel a pending delayed restore and record why it was cancelled."""
        if self._restore_delay_task and not self._restore_delay_task.done():
            self.last_restore_result = {"status": "cancelled", "reason": reason}
            self._restore_delay_task.cancel()
        self._restore_delay_task = None

    async def _restore_snapshot_now(self, reason="restore", clear_snapshot=True):
        """Restore the captured light snapshot immediately.

        This is used when Sync is turned off and by delayed playback-stop
        restores. It bypasses the apply queue so a restore cannot be mistaken
        for another palette update.
        """
        self.last_restore_reason = reason
        if not self.scene:
            self.last_restore_snapshot_count = 0
            self.last_restore_result = {"status": "no_snapshot", "reason": reason}
            clear_apply_cache()
            self._notify()
            return self.last_restore_result

        try:
            self.last_restore_snapshot_count = _snapshot_count(self.scene)
            restore_result = await restore_scene(self.hass, self.scene)
            restore_result["status"] = "restored"
            restore_result["reason"] = reason
            self.last_restore_result = restore_result
            if clear_snapshot:
                self.scene = None
        except Exception as err:
            self.last_restore_result = {"status": "failed", "reason": reason, "failed": str(err)}
            _LOGGER.exception("Failed restoring Sonos Hue Sync scene")
        clear_apply_cache()
        self._notify()
        return self.last_restore_result

    # Delay scene restore after playback stops.
    # This prevents abrupt restore flicker during short pauses or track transitions.
    async def _restore_after_delay(self, delay: float, reason="playback_stopped"):
        try:
            if delay > 0:
                self.last_restore_result = {"status": "pending", "reason": reason, "delay_seconds": delay}
                self._notify()
                await asyncio.sleep(delay)
            await self._restore_snapshot_now(reason=reason, clear_snapshot=True)
        except asyncio.CancelledError:
            # The caller records the precise cancellation reason before
            # cancelling the task. Keep that diagnostic instead of replacing it
            # with a generic string.
            if not isinstance(self.last_restore_result, dict) or self.last_restore_result.get("status") != "cancelled":
                self.last_restore_result = {"status": "cancelled", "reason": reason}
                self._notify()
            raise

    async def _handle_stop(self, reason="playback_stopped"):
        self._stop_auto_rotate()
        self.last_restore_reason = reason
        delay = float(self.config.get("restore_delay", 0) or 0)
        self._cancel_pending_restore(reason=f"new_restore_request:{reason}")
        self._restore_delay_task = self.hass.loop.create_task(self._restore_after_delay(delay, reason=reason))
        self.last_restore_result = {"status": "pending", "reason": reason, "delay_seconds": delay}
        self._notify()

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

    # Capture original light state for later restore.
    # Includes lights that are off so disabling sync can return them to off.
    async def _capture_restore_snapshot(self, reason="snapshot"):
        """Capture target light state before Sonos Hue Sync changes anything."""
        targets = self._resolved_control_targets().lights
        if not targets:
            self.scene = None
            self.last_restore_snapshot_count = 0
            self.last_restore_result = "no_targets_to_snapshot"
            self.last_restore_reason = reason
            return
        self.scene = await snapshot_scene(self.hass, targets)
        self.last_restore_snapshot_count = _snapshot_count(self.scene)
        self.last_restore_result = "snapshot_captured"
        self.last_restore_reason = reason

    # Enable sync and snapshot target lights before any changes.
    # Capturing off-state here ensures disabled sync can restore lights that were originally off.
    async def async_enable(self):
        self.enabled = True
        self._ensure_polling()
        await self._capture_restore_snapshot(reason="sync_enabled")
        self._notify()
        await self.async_process_current_state(reason="enabled")

    # Disable sync and restore the saved light state.
    # The snapshot is kept until restore finishes so partial failures can be diagnosed.
    async def async_disable(self):
        self.last_processing_reason = "sync_disabled"
        self.enabled = False
        self._stop_auto_rotate()
        self._stop_polling()
        # Sync Off is an explicit user action. Restore immediately instead of
        # honoring Restore Delay so lights return to their previous state right
        # away and cannot be cancelled by unrelated updates.
        self._cancel_pending_restore(reason="sync_disabled_force_restore")
        await self._restore_snapshot_now(reason="sync_disabled", clear_snapshot=True)
        self._notify()
