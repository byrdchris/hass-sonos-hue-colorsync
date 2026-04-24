from __future__ import annotations

import colorsys
import math
from io import BytesIO

from colorthief import ColorThief

def _hsv(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = [x / 255 for x in rgb]
    return colorsys.rgb_to_hsv(r, g, b)

def is_dull(rgb: tuple[int, int, int]) -> bool:
    """Filter visually unhelpful colors while keeping bright whites/creams."""
    _h, s, v = _hsv(rgb)
    if v < 0.18:
        return True
    if s < 0.18 and v < 0.62:
        return True
    if s < 0.08 and v < 0.82:
        return True
    return False

def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = [x / 255 for x in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def _visual_score(rgb: tuple[int, int, int]) -> float:
    _h, s, v = _hsv(rgb)
    lum = luminance(rgb)
    bright_neutral_bonus = 0.32 if s < 0.20 and v > 0.78 else 0.0
    accent_bonus = 0.18 if s > 0.45 and v > 0.35 else 0.0
    too_dark_penalty = -0.35 if v < 0.28 else 0.0
    return (s * 0.42) + (v * 0.30) + (lum * 0.20) + bright_neutral_bonus + accent_bonus + too_dark_penalty

def _rgb_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))

def _hue_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    ha, sa, _va = _hsv(a)
    hb, sb, _vb = _hsv(b)
    if sa < 0.18 or sb < 0.18:
        return abs(luminance(a) - luminance(b)) * 180
    diff = abs(ha - hb)
    return min(diff, 1 - diff) * 360

def _clustered_select(
    candidates: list[tuple[int, int, int]],
    desired: int,
) -> list[tuple[int, int, int]]:
    if not candidates:
        return []

    ordered = sorted(candidates, key=_visual_score, reverse=True)
    selected: list[tuple[int, int, int]] = []

    for rgb_min, hue_min in [(55, 42), (42, 30), (30, 18), (18, 8), (0, 0)]:
        for color in ordered:
            if color in selected:
                continue
            if all(
                _rgb_distance(color, existing) >= rgb_min
                and _hue_distance(color, existing) >= hue_min
                for existing in selected
            ):
                selected.append(color)
            if len(selected) >= desired:
                return selected[:desired]

    return selected[:desired]

def extract_palette_from_bytes(image_bytes: bytes, config: dict) -> list[tuple[int, int, int]]:
    desired = int(config.get("color_count", 3))

    ct = ColorThief(BytesIO(image_bytes))
    candidates = ct.get_palette(color_count=max(desired * 6, 20), quality=3)

    if config.get("filter_dull", True):
        filtered = [c for c in candidates if not is_dull(c)]
        candidates = filtered or candidates

    clustered = _clustered_select(candidates, desired)
    return clustered[:desired] or [(255, 255, 255)]

def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)
