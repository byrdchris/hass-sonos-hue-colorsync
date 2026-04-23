
import asyncio
from .palette import luminance

def rgb_to_mired(rgb):
    r,g,b=rgb
    return 153 if b>r else 400

async def snapshot_scene(hass,group):
    await hass.services.async_call("scene","create",{
        "scene_id":"sonos_hue_snapshot",
        "snapshot_entities":[group]
    },blocking=True)
    return "scene.sonos_hue_snapshot"

async def restore_scene(hass,scene):
    await hass.services.async_call("scene","turn_on",{"entity_id":scene},blocking=True)

async def apply_palette(hass,group,palette,config):
    state=hass.states.get(group)
    members=state.attributes.get("entity_id",[group])
    steps=5
    t=config.get("transition",2)

    for step in range(steps):
        for i,light in enumerate(members):
            color=palette[i%len(palette)]
            lum=luminance(color)
            bri=int(50+lum*205)

            if max(color)-min(color)<15:
                await hass.services.async_call("light","turn_on",{
                    "entity_id":light,
                    "color_temp":rgb_to_mired(color),
                    "brightness":bri,
                    "transition":t/steps
                },blocking=False)
            else:
                await hass.services.async_call("light","turn_on",{
                    "entity_id":light,
                    "rgb_color":color,
                    "brightness":bri,
                    "transition":t/steps
                },blocking=False)
        await asyncio.sleep(t/steps)
