from __future__ import annotations

import colorsys
from io import BytesIO

from colorthief import ColorThief

def is_dull(rgb: tuple[int, int, int]) -> bool:
    r, g, b = [x / 255 for x in rgb]
    _h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return s < 0.2 or v < 0.2

def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = [x / 255 for x in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def extract_palette_from_bytes(image_bytes: bytes, config: dict) -> list[tuple[int, int, int]]:
    ct = ColorThief(BytesIO(image_bytes))
    palette = ct.get_palette(color_count=config.get("color_count", 3))
    if config.get("filter_dull", True):
        palette = [c for c in palette if not is_dull(c)]
    return palette or [(255, 255, 255)]

def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)
