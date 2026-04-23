from __future__ import annotations

import colorsys
from io import BytesIO
from colorthief import ColorThief

def is_dull(rgb: tuple[int, int, int]) -> bool:
    """Filter colors that are visually unhelpful for lights.

    The old filter removed any low-saturation color. That was too aggressive
    because album art often uses bright whites, creams, and pale neutrals that
    should influence the room. This version removes mostly:
      - near-black colors
      - dark low-saturation grays/browns
      - mid gray colors

    It intentionally keeps bright neutral/cream tones.
    """
    r, g, b = [x / 255 for x in rgb]
    _h, s, v = colorsys.rgb_to_hsv(r, g, b)

    # Very dark colors usually make poor lighting colors.
    if v < 0.18:
        return True

    # Dark, low-saturation colors read muddy on lights.
    if s < 0.18 and v < 0.62:
        return True

    # Mid grays, but keep light creams/whites.
    if s < 0.08 and v < 0.82:
        return True

    return False

def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = [x / 255 for x in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def _visual_score(rgb: tuple[int, int, int]) -> float:
    """Rank colors for light usefulness while keeping bright neutrals."""
    r, g, b = [x / 255 for x in rgb]
    _h, s, v = colorsys.rgb_to_hsv(r, g, b)
    lum = luminance(rgb)

    # Prefer visible, usable light colors. Bright neutrals get a boost,
    # saturated colors get a boost, very dark colors fall away.
    bright_neutral_bonus = 0.30 if s < 0.20 and v > 0.78 else 0.0
    return (s * 0.45) + (v * 0.35) + (lum * 0.20) + bright_neutral_bonus

def _dedupe_similar(colors: list[tuple[int, int, int]], min_distance: int = 28) -> list[tuple[int, int, int]]:
    kept: list[tuple[int, int, int]] = []
    for color in colors:
        if all(
            sum((color[i] - existing[i]) ** 2 for i in range(3)) ** 0.5 >= min_distance
            for existing in kept
        ):
            kept.append(color)
    return kept

def extract_palette_from_bytes(image_bytes: bytes, config: dict) -> list[tuple[int, int, int]]:
    desired = int(config.get("color_count", 3))

    # Request more candidates than needed. This helps keep whites/creams and
    # avoid near-duplicate reddish/pink tones dominating the output.
    ct = ColorThief(BytesIO(image_bytes))
    candidates = ct.get_palette(color_count=max(desired * 4, 12), quality=5)

    if config.get("filter_dull", True):
        filtered = [c for c in candidates if not is_dull(c)]
        candidates = filtered or candidates

    candidates = sorted(candidates, key=_visual_score, reverse=True)
    candidates = _dedupe_similar(candidates)

    return candidates[:desired] or [(255, 255, 255)]

def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)
