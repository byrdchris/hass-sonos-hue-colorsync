
import asyncio
from .palette import luminance

def rgb_to_mired(rgb):
    # crude approximation: warmer for low blue
    r, g, b = rgb
    if b > r:
        return 153  # cooler
    return 400  # warmer

async def snapshot_scene(hass, light_group):
    scene_id = "sonos_hue_snapshot"
    await hass.services.async_call("scene","create",{
        "scene_id": scene_id,
        "snapshot_entities": [light_group]
    },blocking=True)
    return f"scene.{scene_id}"

async def restore_scene(hass, scene_id):
    await hass.services.async_call("scene","turn_on",{"entity_id": scene_id},blocking=True)

async def apply_palette(hass, light_group, palette, config):
    state = hass.states.get(light_group)
    members = state.attributes.get("entity_id",[light_group])

    steps = 5
    transition = config.get("transition",2)

    for step in range(steps):
        for i, light in enumerate(members):
            color = palette[i % len(palette)]

            # brightness scaling
            lum = luminance(color)
            brightness = int(50 + lum * 205)

            # white detection
            if max(color) - min(color) < 15:
                await hass.services.async_call("light","turn_on",{
                    "entity_id": light,
                    "color_temp": rgb_to_mired(color),
                    "brightness": brightness,
                    "transition": transition/steps
                },blocking=False)
            else:
                await hass.services.async_call("light","turn_on",{
                    "entity_id": light,
                    "rgb_color": color,
                    "brightness": brightness,
                    "transition": transition/steps
                },blocking=False)

        await asyncio.sleep(transition/steps)
