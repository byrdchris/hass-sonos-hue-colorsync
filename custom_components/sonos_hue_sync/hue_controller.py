from __future__ import annotations

import asyncio
from .palette import luminance

def rgb_to_mired(rgb: tuple[int, int, int]) -> int:
    r, _g, b = rgb
    return 153 if b > r else 400

async def snapshot_scene(hass, group: str) -> str:
    scene_id = "sonos_hue_sync_snapshot"
    await hass.services.async_call(
        "scene",
        "create",
        {
            "scene_id": scene_id,
            "snapshot_entities": [group],
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

async def apply_palette(hass, group: str, palette: list[tuple[int, int, int]], config: dict) -> None:
    state = hass.states.get(group)
    if state is None:
        return

    members = state.attributes.get("entity_id")
    if not isinstance(members, list) or not members:
        members = [group]

    steps = 5
    total_transition = float(config.get("transition", 2))
    step_transition = total_transition / steps if steps else total_transition

    for _step in range(steps):
        for i, light in enumerate(members):
            color = palette[i % len(palette)]
            bri = int(50 + luminance(color) * 205)

            service_data = {
                "entity_id": light,
                "brightness": bri,
                "transition": step_transition,
            }

            if max(color) - min(color) < 15:
                service_data["color_temp"] = rgb_to_mired(color)
            else:
                service_data["rgb_color"] = list(color)

            await hass.services.async_call(
                "light",
                "turn_on",
                service_data,
                blocking=True,
            )

        if step_transition > 0:
            await asyncio.sleep(step_transition)
