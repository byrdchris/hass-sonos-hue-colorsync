from __future__ import annotations

import asyncio
import logging

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import CONF_EXPAND_GROUPS
from .palette import luminance

_LOGGER = logging.getLogger(__name__)

COLOR_MODES = ("rgb", "xy", "hs", "rgbw", "rgbww", "color_temp")
GROUP_UNIQUE_ID_TOKENS = (
    "grouped_light",
    "grouped-light",
    "group",
    "room",
    "zone",
)

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

def _has_direct_members(state) -> bool:
    members = state.attributes.get("entity_id")
    return isinstance(members, list) and bool(members)

def _is_hue_group_entity(hass, entity_id: str) -> bool:
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    state = hass.states.get(entity_id)

    if state is None:
        return False

    if _has_direct_members(state):
        return True

    if entry and entry.platform == "hue" and _unique_id_looks_grouped(entry):
        return True

    return False

def _is_physical_candidate(hass, entity_id: str) -> bool:
    """Non-recursive check for final light targets."""
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    state = hass.states.get(entity_id)

    if state is None:
        return False

    # Avoid direct HA group entities.
    if _has_direct_members(state):
        return False

    # Avoid registry-known Hue grouped lights.
    if entry and entry.platform == "hue" and _unique_id_looks_grouped(entry):
        return False

    return _supports_any_color(state)

def _same_area_physical_lights(hass, source_entity_id: str) -> list[str]:
    registry = er.async_get(hass)
    source_entry = registry.async_get(source_entity_id)
    source_area = _entry_area_id(hass, source_entry)

    if not source_area:
        return []

    candidates: list[str] = []

    for entry in registry.entities.values():
        if entry.domain != "light":
            continue

        entity_id = entry.entity_id
        if entity_id == source_entity_id:
            continue

        if not _is_physical_candidate(hass, entity_id):
            continue

        if _entry_area_id(hass, entry) == source_area and entity_id not in candidates:
            candidates.append(entity_id)

    return candidates

def resolve_light_entities(hass, selected_entities: list[str], expand_groups: bool = True) -> list[str]:
    resolved: list[str] = []

    for entity_id in selected_entities:
        state = hass.states.get(entity_id)
        if state is None:
            _LOGGER.warning("Selected light entity %s does not exist", entity_id)
            continue

        expanded: list[str] = []

        if expand_groups:
            direct_members = state.attributes.get("entity_id")
            if isinstance(direct_members, list) and direct_members:
                for member in direct_members:
                    if _is_physical_candidate(hass, member):
                        expanded.append(member)
                    else:
                        # If a direct member is itself a Hue group helper, expand it by area.
                        for nested in _same_area_physical_lights(hass, member):
                            if nested not in expanded:
                                expanded.append(nested)

            if _is_hue_group_entity(hass, entity_id):
                for member in _same_area_physical_lights(hass, entity_id):
                    if member not in expanded:
                        expanded.append(member)

        if expanded:
            _LOGGER.info("Expanded %s to %s", entity_id, expanded)
            for member in expanded:
                if member not in resolved:
                    resolved.append(member)
        else:
            if entity_id not in resolved:
                resolved.append(entity_id)

    return resolved

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

    if _is_neutral(color) and _supports(state, "color_temp"):
        data["color_temp"] = rgb_to_mired(color)
        return data

    if any(_supports(state, mode) for mode in ("rgb", "xy", "hs", "rgbw", "rgbww")):
        data["rgb_color"] = list(color)
        return data

    return data

async def apply_palette(hass, selected_entities: list[str], palette: list[tuple[int, int, int]], config: dict):
    resolved = resolve_light_entities(
        hass,
        selected_entities,
        expand_groups=config.get(CONF_EXPAND_GROUPS, True),
    )

    if not resolved:
        _LOGGER.warning("No resolved light entities from selected entities: %s", selected_entities)
        return [], []

    effective_palette = palette[:len(resolved)] if len(palette) >= len(resolved) else palette
    steps = 5
    total_transition = float(config.get("transition", 2))
    step_transition = total_transition / steps if steps else total_transition
    last_step_service_data = []

    for step in range(steps):
        step_service_data = []

        for idx, light in enumerate(resolved):
            color = effective_palette[idx % len(effective_palette)]
            state = hass.states.get(light)
            if state is None:
                continue

            service_data = _build_service_data(state, color, step_transition)
            step_service_data.append(dict(service_data))
            _LOGGER.debug("Calling light.turn_on with %s", service_data)

            await hass.services.async_call("light", "turn_on", service_data, blocking=True)

        last_step_service_data = step_service_data

        if step_transition > 0:
            await asyncio.sleep(step_transition)

    return resolved, last_step_service_data
