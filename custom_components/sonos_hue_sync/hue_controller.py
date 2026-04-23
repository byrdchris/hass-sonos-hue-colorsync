from __future__ import annotations

import asyncio
import logging

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

from .const import CONF_EXPAND_GROUPS
from .palette import luminance

_LOGGER = logging.getLogger(__name__)

def rgb_to_mired(rgb: tuple[int, int, int]) -> int:
    r, _g, b = rgb
    return 153 if b > r else 400

def _supports(entity_state, mode: str) -> bool:
    modes = entity_state.attributes.get("supported_color_modes") or []
    return mode in modes

def _is_neutral(color: tuple[int, int, int]) -> bool:
    return max(color) - min(color) < 15

def _entity_platform(hass, entity_id: str) -> str | None:
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    return entry.platform if entry else None

def _device_light_members(hass, entity_id: str) -> list[str]:
    """Try to expand a Hue room/zone/group light to child light entities.

    Hue room/zone group light entities may not expose an entity_id attribute.
    In that case, HA's entity/device registries often still contain related
    individual Hue light entities linked to the same device/config entry.
    """
    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    source = registry.async_get(entity_id)
    if source is None:
        return []

    candidates = []

    # First try same device_id.
    if source.device_id:
        for ent in registry.entities.values():
            if (
                ent.entity_id != entity_id
                and ent.domain == "light"
                and ent.device_id == source.device_id
            ):
                candidates.append(ent.entity_id)

    # Then try area_id matching. This catches many Hue room/zone layouts.
    source_area_id = source.area_id
    if not source_area_id and source.device_id:
        device = device_registry.async_get(source.device_id)
        source_area_id = device.area_id if device else None

    if source_area_id:
        for ent in registry.entities.values():
            if ent.domain != "light" or ent.entity_id == entity_id:
                continue

            ent_area_id = ent.area_id
            if not ent_area_id and ent.device_id:
                device = device_registry.async_get(ent.device_id)
                ent_area_id = device.area_id if device else None

            if ent_area_id == source_area_id and ent.entity_id not in candidates:
                candidates.append(ent.entity_id)

    # Keep only loaded light states and exclude other grouped Hue lights to avoid
    # applying one color to another aggregate entity.
    loaded = []
    for candidate in candidates:
        state = hass.states.get(candidate)
        if state is None:
            continue
        attrs = state.attributes
        if attrs.get("entity_id"):
            continue
        if candidate not in loaded:
            loaded.append(candidate)

    return loaded

def resolve_light_entities(hass, selected_entities: list[str], expand_groups: bool = True) -> list[str]:
    resolved = []

    for entity_id in selected_entities:
        state = hass.states.get(entity_id)
        if state is None:
            _LOGGER.warning("Selected light entity %s does not exist", entity_id)
            continue

        members = state.attributes.get("entity_id")
        expanded = []

        if expand_groups and isinstance(members, list) and members:
            expanded = members
        elif expand_groups:
            expanded = _device_light_members(hass, entity_id)

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
    last_service_data = []

    for _step in range(steps):
        for idx, light in enumerate(resolved):
            color = effective_palette[idx % len(effective_palette)]
            state = hass.states.get(light)
            if state is None:
                continue

            service_data = _build_service_data(state, color, step_transition)
            last_service_data.append(dict(service_data))
            _LOGGER.debug("Calling light.turn_on with %s", service_data)

            await hass.services.async_call("light", "turn_on", service_data, blocking=True)

        if step_transition > 0:
            await asyncio.sleep(step_transition)

    return resolved, last_service_data
