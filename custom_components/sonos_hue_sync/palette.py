from __future__ import annotations

import colorsys
import math
import hashlib
from io import BytesIO

from colorthief import ColorThief
from PIL import Image

from .const import (
    CONF_WHITE_HANDLING,
    CONF_WHITE_FILTER_STRENGTH,
    WHITE_FILTER_STRENGTH_BALANCED,
    WHITE_FILTER_STRENGTH_GENTLE,
    WHITE_FILTER_STRENGTH_STRONG,
    WHITE_HANDLING_CONTEXTUAL,
    WHITE_HANDLING_ALWAYS_FILTER,
    WHITE_HANDLING_ALLOW,
)

def _hsv(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = [x / 255 for x in rgb]
    return colorsys.rgb_to_hsv(r, g, b)

def is_dull(rgb: tuple[int, int, int]) -> bool:
    _h, s, v = _hsv(rgb)
    if v < 0.18:
        return True
    if s < 0.18 and v < 0.62:
        return True
    if s < 0.08 and v < 0.82:
        return True
    return False

def is_bright_white(rgb: tuple[int, int, int]) -> bool:
    r, _g, b = rgb
    _h, s, v = _hsv(rgb)
    if v < 0.90:
        return False
    if s > 0.16:
        return False
    if r - b >= 10:
        return False
    return True


def _white_filter_thresholds(config: dict | None = None) -> tuple[float, float]:
    """Return value/saturation limits for white and pale-neutral filtering."""
    strength = (config or {}).get(CONF_WHITE_FILTER_STRENGTH, WHITE_FILTER_STRENGTH_BALANCED)
    if strength == WHITE_FILTER_STRENGTH_GENTLE:
        # Original conservative behavior: only obvious white, cream, beige, and very pale tones.
        return 0.78, 0.24
    if strength == WHITE_FILTER_STRENGTH_STRONG:
        # Aggressive behavior: also suppress brighter low-saturation grays and pale pastels.
        return 0.62, 0.30
    # Balanced behavior: suppress pale neutrals such as blue-gray that Hue can render as bright white.
    return 0.70, 0.24


def is_soft_or_bright_white(rgb: tuple[int, int, int], config: dict | None = None) -> bool:
    """Return True for white, cream, beige, pale gray, or other near-white tones."""
    _h, s, v = _hsv(rgb)
    min_value, max_saturation = _white_filter_thresholds(config)
    return v >= min_value and s <= max_saturation


def is_real_color(rgb: tuple[int, int, int]) -> bool:
    """Return True for chromatic colors that should count as real album colors."""
    _h, s, v = _hsv(rgb)
    return s >= 0.22 and 0.18 <= v <= 0.96


def _apply_white_handling(candidates: list[tuple[int, int, int]], config: dict) -> list[tuple[int, int, int]]:
    """Apply White Color Handling without allowing an empty palette."""
    original = list(candidates)
    if not original:
        return original
    white_mode = config.get(CONF_WHITE_HANDLING)
    if white_mode is None:
        white_mode = WHITE_HANDLING_CONTEXTUAL if config.get("filter_bright_white", True) else WHITE_HANDLING_ALLOW
    filtered: list[tuple[int, int, int]] | None = None
    if white_mode == WHITE_HANDLING_ALWAYS_FILTER:
        filtered = [c for c in original if not is_soft_or_bright_white(c, config)]
    elif white_mode == WHITE_HANDLING_CONTEXTUAL:
        has_color = any(is_real_color(c) and not is_soft_or_bright_white(c, config) for c in original)
        if has_color:
            filtered = [c for c in original if not is_soft_or_bright_white(c, config)]
    elif white_mode != WHITE_HANDLING_ALLOW and config.get("filter_bright_white", True):
        filtered = [c for c in original if not is_bright_white(c)]
    if filtered is None:
        return original
    return filtered or original

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

def _dominant_select(candidates: list[tuple[int, int, int]], desired: int) -> list[tuple[int, int, int]]:
    """Return the first usable candidates in ColorThief dominance order.

    ColorThief returns palette candidates in dominance order. This mode keeps
    that order after filtering, so Number of Colors means top N dominant usable
    colors rather than most vivid or most visually distinct colors.
    """
    selected: list[tuple[int, int, int]] = []
    for color in candidates:
        if color not in selected:
            selected.append(color)
        if len(selected) >= desired:
            break
    return selected[:desired]


def _clustered_select(candidates: list[tuple[int, int, int]], desired: int) -> list[tuple[int, int, int]]:
    if not candidates:
        return []
    ordered = sorted(candidates, key=_visual_score, reverse=True)
    selected: list[tuple[int, int, int]] = []
    for rgb_min, hue_min in [(55, 42), (42, 30), (30, 18), (18, 8), (0, 0)]:
        for color in ordered:
            if color in selected:
                continue
            if all(_rgb_distance(color, existing) >= rgb_min and _hue_distance(color, existing) >= hue_min for existing in selected):
                selected.append(color)
            if len(selected) >= desired:
                return selected[:desired]
    return selected[:desired]

def _image_chroma_ratio(image_bytes: bytes) -> float | None:
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((64, 64))
        pixels = list(img.getdata())
    except Exception:
        return None

    if not pixels:
        return None

    chromatic = 0
    useful = 0

    for rgb in pixels:
        _h, s, v = _hsv(rgb)
        if v < 0.08:
            continue
        useful += 1
        if s > 0.12:
            chromatic += 1

    if useful == 0:
        return 0.0

    return chromatic / useful

def _image_color_class(image_bytes: bytes) -> str:
    """Return monochrome, low_color, or full_color."""
    ratio = _image_chroma_ratio(image_bytes)
    if ratio is None:
        return "full_color"
    if ratio < 0.035:
        return "monochrome"
    if ratio < 0.10:
        return "low_color"
    return "full_color"

def _repeat_to_count(colors: list[tuple[int, int, int]], desired: int) -> list[tuple[int, int, int]]:
    if not colors:
        return [(220, 198, 176)] * desired
    return [colors[idx % len(colors)] for idx in range(desired)]

def _monochrome_palette(image_bytes: bytes, desired: int, mode: str) -> list[tuple[int, int, int]] | None:
    if mode == "disabled":
        return None

    if mode == "muted_accent":
        return _repeat_to_count([
            (190, 170, 145),
            (120, 135, 150),
            (155, 130, 115),
            (105, 110, 118),
        ], desired)

    if mode == "grayscale":
        try:
            ct = ColorThief(BytesIO(image_bytes))
            raw = ct.get_palette(color_count=max(desired * 3, 8), quality=3)
            grays = []
            for color in raw:
                y = int(luminance(color) * 255)
                y = max(70, min(218, y))
                gray = (y, y, y)
                if gray not in grays:
                    grays.append(gray)
            return _repeat_to_count(grays, desired)
        except Exception:
            return _repeat_to_count([(190, 190, 190), (150, 150, 150), (110, 110, 110)], desired)

    return _repeat_to_count([
        (225, 204, 178),
        (190, 170, 148),
        (150, 135, 122),
        (110, 100, 95),
    ], desired)


def _dominant_accent_candidates(candidates: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """Return strong, useful accent colors from otherwise dark/neutral artwork."""
    accents = []
    for rgb in candidates:
        h, s, v = _hsv(rgb)

        # Keep real accent colors such as orange stars/logos/text.
        # Avoid black, near-white, and low-saturation neutrals.
        if s >= 0.34 and 0.20 <= v <= 0.92 and not is_bright_white(rgb):
            accents.append(rgb)

    return _clustered_select(accents, max(1, min(len(accents), 6)))


def _dark_anchor_candidates(candidates: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """Keep usable dark anchors from artwork without collapsing everything to black."""
    anchors = []
    for rgb in candidates:
        h, s, v = _hsv(rgb)

        # Deep navy, charcoal, and dark colored backgrounds are visually useful.
        if 0.08 <= v <= 0.34 and (s >= 0.08 or v >= 0.16):
            adjusted_v = max(v, 0.18)
            adjusted_s = min(max(s, 0.14), 0.42)
            r, g, b = colorsys.hsv_to_rgb(h, adjusted_s, adjusted_v)
            anchors.append((int(r * 255), int(g * 255), int(b * 255)))

    return _clustered_select(anchors, max(1, min(len(anchors), 4)))


def _accent_preserving_low_color_palette(candidates: list[tuple[int, int, int]], desired: int) -> list[tuple[int, int, int]] | None:
    """Preserve strong accent + dark anchor colors in mostly dark/neutral art.

    This avoids turning covers with one real accent color into generic warm
    neutral palettes.
    """
    accents = _dominant_accent_candidates(candidates)
    if not accents:
        return None

    anchors = _dark_anchor_candidates(candidates)
    soft_neutrals = []

    for rgb in candidates:
        h, s, v = _hsv(rgb)
        if is_bright_white(rgb):
            continue
        if s < 0.22 and 0.24 <= v <= 0.82:
            # Keep neutral support, but avoid harsh white and pure gray dominance.
            v = min(v, 0.70)
            s = min(s, 0.16)
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            soft_neutrals.append((int(r * 255), int(g * 255), int(b * 255)))

    result = []
    for group in (accents, anchors, soft_neutrals):
        for color in group:
            if color not in result:
                result.append(color)

    if not result:
        return None

    clustered = _clustered_select(result, desired)
    return _repeat_to_count(clustered or result, desired)[:desired]


def _muted_low_color_palette(candidates: list[tuple[int, int, int]], desired: int) -> list[tuple[int, int, int]]:
    """Bias low-color art toward restrained colors instead of saturated noise."""
    muted = []

    for rgb in candidates:
        h, s, v = _hsv(rgb)

        # Ignore extremely dark and harsh white.
        if v < 0.16 or is_bright_white(rgb):
            continue

        # Desaturate candidate while preserving the art's hue family.
        s = min(s, 0.28)
        v = max(0.34, min(v, 0.78))
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        color = (int(r * 255), int(g * 255), int(b * 255))

        if color not in muted:
            muted.append(color)

    if not muted:
        muted = [
            (190, 175, 158),
            (145, 150, 155),
            (120, 112, 105),
            (100, 115, 125),
        ]

    return _clustered_select(muted, desired) or _repeat_to_count(muted, desired)

def extract_palette_from_bytes(image_bytes: bytes, config: dict) -> list[tuple[int, int, int]]:
    desired = int(config.get("color_count", 3))
    color_class = _image_color_class(image_bytes)

    if color_class == "monochrome":
        mono = _monochrome_palette(image_bytes, desired, config.get("monochrome_mode", "warm_neutral"))
        if mono:
            return mono[:desired]

    ct = ColorThief(BytesIO(image_bytes))
    candidates = ct.get_palette(color_count=max(desired * 6, 20), quality=3)
    ordering = config.get("palette_ordering", "vivid_first")

    if color_class == "low_color" and config.get("low_color_handling", True) and ordering != "dominant_first":
        # Prefer preserving real accent colors on mostly dark/neutral artwork
        # before falling back to generic muted low-color handling.
        accent_palette = _accent_preserving_low_color_palette(candidates, desired)
        if accent_palette:
            return accent_palette[:desired]
        return _muted_low_color_palette(candidates, desired)[:desired]

    if config.get("filter_dull", True):
        filtered = [c for c in candidates if not is_dull(c)]
        candidates = filtered or candidates

    candidates = _apply_white_handling(candidates, config)

    if ordering == "dominant_first":
        dominant = _dominant_select(candidates, desired)
        return dominant[:desired] or [(220, 198, 176)]

    clustered = _clustered_select(candidates, desired)
    return clustered[:desired] or [(220, 198, 176)]

def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def fallback_palette_from_metadata(metadata: str, desired: int) -> list[tuple[int, int, int]]:
    """Generate a stable fallback palette when album art is temporarily unavailable.

    The palette is deterministic per track/artist/album and intentionally muted
    enough for room lighting.
    """
    desired = max(1, int(desired or 3))
    digest = hashlib.sha256((metadata or "sonos-hue-sync").encode("utf-8")).digest()
    colors = []

    for idx in range(max(desired, 3)):
        h = digest[idx] / 255.0
        s = 0.36 + (digest[idx + 8] / 255.0) * 0.34
        v = 0.42 + (digest[idx + 16] / 255.0) * 0.34
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        color = (int(r * 255), int(g * 255), int(b * 255))
        if color not in colors:
            colors.append(color)

    return _repeat_to_count(colors, desired)[:desired]


def warm_neutral_fallback_palette(desired: int) -> list[tuple[int, int, int]]:
    desired = max(1, int(desired or 3))
    base = [
        (255, 214, 170),
        (220, 190, 150),
        (180, 160, 130),
        (130, 115, 100),
    ]
    return _repeat_to_count(base, desired)[:desired]
