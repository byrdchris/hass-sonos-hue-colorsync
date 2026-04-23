from __future__ import annotations

import asyncio
from .palette import luminance

def rgb_to_mired(rgb: tuple[int, int, int]) -> int:
    r, _g, b = rgb
    return 153 if b > r else 400

def _supports(entity_state, mode: str) -> bool:
    modes = entity_state.attributes.get("supported_color_modes") or []
    return mode in modes

def _is_neutral(color: tuple[int, int, int]) -> bool:
    return max(color) - min(color) < 15

def resolve_light_entities(hass, selected_entities: list[str]) -> list[str]:
    resolved = []
    for entity_id in selected_entities:
        state = hass.states.get(entity_id)
        if state is None:
            continue
        members = state.attributes.get("entity_id")
        if isinstance(members, list) and members:
            for member in members:
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
        {
            "scene_id": scene_id,
            "snapshot_entities": selected_entities,
        },
        blocking=True,
    )
    return f"scene.{scene_id}"

async def restore_scene(hass, scene_entity_id: str) -> None:
    await hass.services.async_call(
        "scene",
        "turn_on",
        {"entity_id": scene_entity_id},
        blocking=True,
    )

def _build_service_data(state, color, transition):
    brightness = int(50 + luminance(color) * 205)
    data = {
        "entity_id": state.entity_id,
        "brightness": brightness,
        "transition": transition,
    }

    if _is_neutral(color) and _supports(state, "color_temp"):
        data["color_temp"] = rgb_to_mired(color)
        return data

    if _supports(state, "rgb"):
        data["rgb_color"] = list(color)
        return data

    if _supports(state, "xy"):
        # Let HA convert from rgb_color for integrations that accept it.
        data["rgb_color"] = list(color)
        return data

    if _supports(state, "hs"):
        data["rgb_color"] = list(color)
        return data

    if _supports(state, "white") or _supports(state, "brightness"):
        return data

    data["rgb_color"] = list(color)
    return data

async def apply_palette(hass, selected_entities: list[str], palette: list[tuple[int, int, int]], config: dict):
    resolved = resolve_light_entities(hass, selected_entities)
    if not resolved:
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
            await hass.services.async_call(
                "light",
                "turn_on",
                service_data,
                blocking=True,
            )
        if step_transition > 0:
            await asyncio.sleep(step_transition)

    return resolved, last_service_data
