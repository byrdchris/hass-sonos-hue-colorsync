
import aiohttp, colorsys
from colorthief import ColorThief
from io import BytesIO

def is_dull(rgb):
    r,g,b=[x/255 for x in rgb]
    h,s,v=colorsys.rgb_to_hsv(r,g,b)
    return s<0.2 or v<0.2

def luminance(rgb):
    r,g,b=[x/255 for x in rgb]
    return 0.2126*r+0.7152*g+0.0722*b

async def extract_palette(url,config):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            img=await resp.read()
    ct=ColorThief(BytesIO(img))
    palette=ct.get_palette(color_count=config.get("color_count",3))
    if config.get("filter_dull",True):
        palette=[c for c in palette if not is_dull(c)]
    return palette
