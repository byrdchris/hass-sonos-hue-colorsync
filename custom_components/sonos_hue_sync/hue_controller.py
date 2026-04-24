from __future__ import annotations

import asyncio
import logging
import math

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import entity_component

from .const import (
    ASSIGNMENT_STRATEGY_ALTERNATING,
    ASSIGNMENT_STRATEGY_BALANCED,
    ASSIGNMENT_STRATEGY_BRIGHTNESS,
    ASSIGNMENT_STRATEGY_SEQUENTIAL,
    CONF_ASSIGNMENT_STRATEGY,
    CONF_EXPAND_GROUPS,
)
from .palette import luminance

_LOGGER = logging.getLogger(__name__)

_LAST_GROUP_MEMBERS: dict[str, list[str]] = {}

COLOR_MODES = ("rgb", "xy", "hs", "rgbw", "rgbww", "color_temp")
GROUP_UNIQUE_ID_TOKENS = ("grouped_light", "grouped-light", "group", "room", "zone")
GRADIENT_HINTS = ("gradient", "signe", "play gradient", "lightstrip plus gradient")

def rgb_to_mired(rgb: tuple[int, int, int]) -> int:
    r, _g, b = rgb
    return 153 if b > r else 400

def _supports(entity_state, mode: str) -> bool:
    modes = entity_state.attributes.get("supported_color_modes") or []
    return mode in modes

def _supports_any_color(entity_state) -> bool:
    modes = entity_state.attributes.get("supported_color_modes") or []
    return any(mode in modes for mode in COLOR_MODES)

def _is_neutral(color: tuple[int, int, int]) -> bool:
    return max(color) - min(color) < 15

def _entry_area_id(hass, entry) -> str | None:
    if entry is None:
        return None
    if entry.area_id:
        return entry.area_id
    device_registry = dr.async_get(hass)
    if entry.device_id:
        device = device_registry.async_get(entry.device_id)
        if device and device.area_id:
            return device.area_id
    return None

def _unique_id_looks_grouped(entry) -> bool:
    if entry is None or not entry.unique_id:
        return False
    unique_id = entry.unique_id.lower()
    return any(token in unique_id for token in GROUP_UNIQUE_ID_TOKENS)

def _is_hue_group_entity(hass, entity_id: str) -> bool:
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    state = hass.states.get(entity_id)
    if state is None:
        return False
    if state.attributes.get("is_hue_group") is True:
        return True
    if state.attributes.get("hue_type") in ("room", "zone", "group"):
        return True
    members = state.attributes.get("entity_id")
    if isinstance(members, list) and members:
        return True
    if entry and entry.platform == "hue" and _unique_id_looks_grouped(entry):
        return True
    return False

def _same_area_physical_lights(hass, source_entity_id: str) -> list[str]:
    registry = er.async_get(hass)
    source_entry = registry.async_get(source_entity_id)
    source_area = _entry_area_id(hass, source_entry)
    if not source_area:
        return []

    candidates = []
    for entry in registry.entities.values():
        if entry.domain != "light" or entry.entity_id == source_entity_id:
            continue
        state = hass.states.get(entry.entity_id)
        if state is None:
            continue
        if state.attributes.get("is_hue_group") is True:
            continue
        if state.attributes.get("hue_type") in ("room", "zone", "group"):
            continue
        if state.attributes.get("entity_id"):
            continue
        if not _supports_any_color(state):
            continue
        if _entry_area_id(hass, entry) == source_area and entry.entity_id not in candidates:
            candidates.append(entry.entity_id)
    return candidates


def _ha_expand_entity_ids(hass, entity_ids: list[str]) -> list[str]:
    """Use Home Assistant's own group expansion helper where available."""
    try:
        expanded = entity_component.async_extract_from_target(
            hass,
            "light",
            {"entity_id": entity_ids},
        )
        result = []
        for entity_id in expanded:
            if entity_id not in result:
                result.append(entity_id)
        return result
    except Exception:
        _LOGGER.debug("HA entity expansion failed for %s", entity_ids, exc_info=True)
        return []

def _direct_member_lights(hass, entity_id: str) -> list[str]:
    """Return direct members from a HA/Hue group exactly as HA exposes them.

    Important: do not filter these through area/device metadata. Hue Play and
    some other Hue entities may not share registry area/device data reliably,
    but if the Hue room/group exposes them under `entity_id`, they are valid
    members and should be used.
    """
    state = hass.states.get(entity_id)
    if state is None:
        return []

    members = state.attributes.get("entity_id")
    if not isinstance(members, list) or not members:
        return []

    resolved = []
    for member in members:
        member_state = hass.states.get(member)
        if member_state is None:
            continue

        nested = member_state.attributes.get("entity_id")
        if isinstance(nested, list) and nested:
            for nested_member in nested:
                if nested_member not in resolved:
                    resolved.append(nested_member)
        elif member not in resolved:
            resolved.append(member)

    if resolved:
        _LAST_GROUP_MEMBERS[entity_id] = resolved

    return resolved


def resolve_light_entities(hass, selected_entities: list[str], expand_groups: bool = True) -> tuple[list[str], str]:
    resolved: list[str] = []
    resolver_source = "selected_entities"

    for entity_id in selected_entities:
        state = hass.states.get(entity_id)
        if state is None:
            _LOGGER.warning("Selected light entity %s does not exist", entity_id)
            continue

        expanded: list[str] = []

        if expand_groups:
            direct = _direct_member_lights(hass, entity_id)
            if direct:
                expanded = direct
                resolver_source = "direct_entity_id_members"
            elif _is_hue_group_entity(hass, entity_id):
                area_members = _same_area_physical_lights(hass, entity_id)
                if area_members:
                    expanded = area_members
                    resolver_source = "same_area_hue_group_fallback"

        if expanded:
            _LOGGER.info("Expanded %s to %s via %s", entity_id, expanded, resolver_source)
            for member in expanded:
                if member not in resolved:
                    resolved.append(member)
        else:
            if entity_id not in resolved:
                resolved.append(entity_id)

    return resolved, resolver_source

def _is_gradient_entity(hass, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)

    haystack = " ".join(
        str(x or "").lower()
        for x in (
            entity_id,
            state.attributes.get("friendly_name") if state else "",
            entry.name if entry else "",
            entry.original_name if entry else "",
            entry.unique_id if entry else "",
            state.attributes.get("model") if state else "",
        )
    )

    effects = state.attributes.get("effect_list") if state else []
    if isinstance(effects, list):
        haystack += " " + " ".join(str(e).lower() for e in effects)

    return any(hint in haystack for hint in GRADIENT_HINTS)

def _color_score(color: tuple[int, int, int]) -> float:
    r, g, b = [x / 255 for x in color]
    mx = max(r, g, b)
    mn = min(r, g, b)
    saturation = 0 if mx == 0 else (mx - mn) / mx
    return saturation * 0.65 + luminance(color) * 0.35

def _reorder_palette_for_strategy(
    palette: list[tuple[int, int, int]],
    strategy: str,
) -> list[tuple[int, int, int]]:
    if not palette:
        return palette

    if strategy == ASSIGNMENT_STRATEGY_SEQUENTIAL:
        return palette

    if strategy == ASSIGNMENT_STRATEGY_BRIGHTNESS:
        return sorted(palette, key=luminance, reverse=True)

    if strategy == ASSIGNMENT_STRATEGY_ALTERNATING:
        bright = sorted(palette, key=luminance, reverse=True)
        output = []
        left = 0
        right = len(bright) - 1
        while left <= right:
            output.append(bright[left])
            if left != right:
                output.append(bright[right])
            left += 1
            right -= 1
        return output

    return sorted(palette, key=_color_score, reverse=True)

def _assign_colors(
    hass,
    resolved_lights: list[str],
    palette: list[tuple[int, int, int]],
    strategy: str,
) -> dict[str, tuple[int, int, int]]:
    ordered_palette = _reorder_palette_for_strategy(palette, strategy)

    if not ordered_palette:
        return {}

    assignments: dict[str, tuple[int, int, int]] = {}

    gradient_lights = [light for light in resolved_lights if _is_gradient_entity(hass, light)]
    normal_lights = [light for light in resolved_lights if light not in gradient_lights]

    accent_palette = sorted(ordered_palette, key=_color_score, reverse=True)

    idx = 0
    for light in gradient_lights:
        assignments[light] = accent_palette[idx % len(accent_palette)]
        idx += 1

    if strategy == ASSIGNMENT_STRATEGY_BALANCED and normal_lights:
        step = max(1, math.floor(len(ordered_palette) / max(1, min(len(normal_lights), len(ordered_palette)))))
        color_indexes = [(i * step) % len(ordered_palette) for i in range(len(normal_lights))]
    else:
        color_indexes = list(range(len(normal_lights)))

    for idx, light in enumerate(normal_lights):
        assignments[light] = ordered_palette[color_indexes[idx] % len(ordered_palette)]

    return assignments

async def snapshot_scene(hass, selected_entities: list[str]) -> str:
    scene_id = "sonos_hue_sync_snapshot"
    await hass.services.async_call(
        "scene",
        "create",
        {"scene_id": scene_id, "snapshot_entities": selected_entities},
        blocking=True,
    )
    return f"scene.{scene_id}"

async def restore_scene(hass, scene_entity_id: str) -> None:
    await hass.services.async_call("scene", "turn_on", {"entity_id": scene_entity_id}, blocking=True)

def _build_service_data(state, color, transition):
    brightness = int(50 + luminance(color) * 205)
    data = {"entity_id": state.entity_id, "brightness": brightness, "transition": transition}

    # Always use rgb_color for color-capable lights. This avoids HA service
    # schema issues with color_temp and works for Hue xy-capable lights.
    if any(_supports(state, mode) for mode in ("rgb", "xy", "hs", "rgbw", "rgbww", "color_temp")):
        data["rgb_color"] = list(color)
        return data

    return data


async def apply_palette(hass, selected_entities: list[str], palette: list[tuple[int, int, int]], config: dict):
    resolved, resolver_source = await _stabilized_resolve_light_entities(
        hass,
        selected_entities,
        expand_groups=config.get(CONF_EXPAND_GROUPS, True),
    )

    if not resolved:
        _LOGGER.warning("No resolved light entities from selected entities: %s", selected_entities)
        return [], [], resolver_source

    strategy = config.get(CONF_ASSIGNMENT_STRATEGY, ASSIGNMENT_STRATEGY_BALANCED)
    assignments = _assign_colors(hass, resolved, palette, strategy)

    steps = 5
    total_transition = float(config.get("transition", 2))
    step_transition = total_transition / steps if steps else total_transition
    last_step_service_data = []

    for _step in range(steps):
        step_service_data = []

        for light in resolved:
            color = assignments.get(light)
            if color is None:
                continue

            state = hass.states.get(light)
            if state is None:
                continue

            service_data = _build_service_data(state, color, step_transition)
            service_data["assignment_strategy"] = strategy
            service_data["gradient_aware"] = _is_gradient_entity(hass, light)
            step_service_data.append(dict(service_data))

            call_data = dict(service_data)
            call_data.pop("assignment_strategy", None)
            call_data.pop("gradient_aware", None)
            _LOGGER.debug("Calling light.turn_on with %s", call_data)
            await hass.services.async_call("light", "turn_on", call_data, blocking=True)

        last_step_service_data = step_service_data

        if step_transition > 0:
            await asyncio.sleep(step_transition)

    return resolved, last_step_service_data, resolver_source
