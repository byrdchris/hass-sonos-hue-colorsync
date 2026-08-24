from __future__ import annotations

# Neutral tone handling and monochrome guardrails.
# brief-code-commented-build: moderate block-level comments added for maintainability.

import colorsys
import math
from io import BytesIO
from colorthief import ColorThief
from PIL import Image

from .const import (
    ARTWORK_STYLE_CINEMATIC,
    ARTWORK_STYLE_GRAPHIC,
    ARTWORK_STYLE_MONOCHROME,
    CONF_NEUTRAL_TONE_HANDLING,
    CONF_WHITE_FILTER_STRENGTH,
    CONF_WHITE_HANDLING,
    DEFAULT_NEUTRAL_TONE_HANDLING,
    NEUTRAL_TONE_ALLOW_WHITE,
    NEUTRAL_TONE_GRAPHIC,
    NEUTRAL_TONE_PRESERVE_CONTRAST,
    NEUTRAL_TONE_REDUCE_WHITES,
    NEUTRAL_TONE_WARM_AMBIENT,
    WHITE_FILTER_STRENGTH_BALANCED,
    WHITE_FILTER_STRENGTH_GENTLE,
    WHITE_FILTER_STRENGTH_STRONG,
    WHITE_HANDLING_ALLOW,
    WHITE_HANDLING_ALWAYS_FILTER,
    WHITE_HANDLING_CONTEXTUAL,
)
from .models import RGB

def _hsv(rgb: RGB) -> tuple[float, float, float]:
    r, g, b = [x / 255 for x in rgb]
    return colorsys.rgb_to_hsv(r, g, b)

def luminance(rgb: RGB) -> float:
    r, g, b = [x / 255 for x in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def _rgb_distance(a: RGB, b: RGB) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))

def _hue_distance(a: RGB, b: RGB) -> float:
    ha, sa, _va = _hsv(a)
    hb, sb, _vb = _hsv(b)
    if sa < 0.18 or sb < 0.18:
        return abs(luminance(a) - luminance(b)) * 180
    diff = abs(ha - hb)
    return min(diff, 1 - diff) * 360

def _colorfulness_score(rgb: RGB) -> float:
    h, s, v = _hsv(rgb)
    lum = luminance(rgb)
    warm_accent = 0.20 if ((h <= 0.12 or h >= 0.90) and s >= 0.25 and 0.25 <= v <= 0.92) else 0.0
    skin_or_warm = 0.18 if (0.03 <= h <= 0.13 and 0.18 <= s <= 0.70 and 0.30 <= v <= 0.95) else 0.0
    neutral_penalty = -0.38 if s < 0.18 else 0.0
    near_black_penalty = -0.45 if v < 0.22 else 0.0
    near_white_penalty = -0.35 if v > 0.88 and s < 0.22 else 0.0
    return (s * 0.58) + (v * 0.18) + (lum * 0.10) + warm_accent + skin_or_warm + neutral_penalty + near_black_penalty + near_white_penalty

def _clustered_select(candidates: list[RGB], desired: int) -> list[RGB]:
    if not candidates:
        return []
    ordered = sorted(candidates, key=_colorfulness_score, reverse=True)
    selected: list[RGB] = []
    for rgb_min, hue_min in [(55, 42), (42, 30), (30, 18), (18, 8), (0, 0)]:
        for color in ordered:
            if color in selected:
                continue
            if all(_rgb_distance(color, existing) >= rgb_min and _hue_distance(color, existing) >= hue_min for existing in selected):
                selected.append(color)
            if len(selected) >= desired:
                return selected[:desired]
    return selected[:desired]

def _repeat_to_count(colors: list[RGB], desired: int) -> list[RGB]:
    if not colors:
        return [(220, 198, 176)] * desired
    return [colors[idx % len(colors)] for idx in range(desired)]

def is_dull(rgb: RGB) -> bool:
    _h, s, v = _hsv(rgb)
    if v < 0.18:
        return True
    if s < 0.18 and v < 0.62:
        return True
    if s < 0.08 and v < 0.82:
        return True
    return False

def is_bright_white(rgb: RGB) -> bool:
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
    strength = (config or {}).get(CONF_WHITE_FILTER_STRENGTH, WHITE_FILTER_STRENGTH_BALANCED)
    if strength == WHITE_FILTER_STRENGTH_GENTLE:
        return 0.78, 0.24
    if strength == WHITE_FILTER_STRENGTH_STRONG:
        return 0.62, 0.30
    return 0.70, 0.24

def is_soft_or_bright_white(rgb: RGB, config: dict | None = None) -> bool:
    _h, s, v = _hsv(rgb)
    min_value, max_saturation = _white_filter_thresholds(config)
    return v >= min_value and s <= max_saturation

def is_real_color(rgb: RGB) -> bool:
    _h, s, v = _hsv(rgb)
    return s >= 0.22 and 0.18 <= v <= 0.96

def apply_white_handling(candidates: list[RGB], config: dict) -> list[RGB]:
    original = list(candidates)
    if not original:
        return original
    white_mode = config.get(CONF_WHITE_HANDLING)
    if white_mode is None:
        white_mode = WHITE_HANDLING_CONTEXTUAL if config.get("filter_bright_white", True) else WHITE_HANDLING_ALLOW
    filtered: list[RGB] | None = None
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

def image_chroma_ratio(image_bytes: bytes) -> float | None:
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

def image_color_class(image_bytes: bytes) -> str:
    ratio = image_chroma_ratio(image_bytes)
    if ratio is None:
        return "full_color"
    if ratio < 0.035:
        return "monochrome"
    if ratio < 0.10:
        return "low_color"
    return "full_color"

def is_monochrome_guard_active(config: dict | None) -> bool:
    """Return true when Auto detected low-chroma grayscale art.

    This guard prevents vivid/warm modes from converting black-and-white
    photography into red, pink, or brown pseudo-colors.
    """
    diagnostics = (config or {}).get("_auto_artwork_style_diagnostics") or {}
    metrics = diagnostics.get("metrics") or {}
    detected = diagnostics.get("detected_style")
    try:
        avg_sat = float(metrics.get("average_saturation", 1.0))
        neutral_ratio = float(metrics.get("neutral_ratio", 0.0))
        vivid_ratio = float(metrics.get("vivid_ratio", 1.0))
        color_diversity = float(metrics.get("color_diversity", 1.0))
    except (TypeError, ValueError):
        return False
    return (
        detected in (ARTWORK_STYLE_MONOCHROME, ARTWORK_STYLE_GRAPHIC, ARTWORK_STYLE_CINEMATIC)
        and avg_sat <= 0.18
        and neutral_ratio >= 0.56
        and vivid_ratio <= 0.02
        and color_diversity <= 0.08
    )

def monochrome_guardrail_palette_mode(config: dict | None) -> str:
    """Map Neutral Tone Handling to safe monochrome palette behavior.

    The guardrail should prevent accidental red/pink/brown drift, but the
    user's Neutral Tone Handling choice should still change the result.
    """
    neutral_style = (config or {}).get(CONF_NEUTRAL_TONE_HANDLING, DEFAULT_NEUTRAL_TONE_HANDLING)
    if neutral_style == NEUTRAL_TONE_REDUCE_WHITES:
        return "grayscale_reduce_whites"
    if neutral_style == NEUTRAL_TONE_PRESERVE_CONTRAST:
        return "grayscale_contrast"
    if neutral_style == NEUTRAL_TONE_WARM_AMBIENT:
        return "warm_grayscale"
    if neutral_style == NEUTRAL_TONE_GRAPHIC:
        return "grayscale_graphic"
    if neutral_style == NEUTRAL_TONE_ALLOW_WHITE:
        return "grayscale_allow_white"
    return "grayscale"

def tint_warm_gray(value: int) -> RGB:
    """Return a warm off-white/greige, not a colored red/brown."""
    return (
        max(0, min(255, value + 16)),
        max(0, min(255, value + 7)),
        max(0, min(255, value - 16)),
    )

def shape_monochrome_values(values: list[int], desired: int, mode: str) -> list[int]:
    """Adjust grayscale luminance stops for each Neutral Tone Handling mode."""
    if not values:
        values = [190, 150, 110]
    ordered = sorted(dict.fromkeys(values), reverse=True)
    if mode == "grayscale_reduce_whites":
        shaped = [min(152, max(45, value)) for value in ordered]
        shaped.extend([122, 82, 48])
    elif mode == "grayscale_contrast":
        shaped = []
        for value in ordered:
            if value >= 150:
                shaped.append(min(232, value + 18))
            elif value <= 105:
                shaped.append(max(38, value - 22))
            else:
                shaped.append(value)
        shaped.extend([232, 42])
    elif mode == "grayscale_graphic":
        shaped = [235, 170, 95, 42]
        shaped.extend(ordered)
    elif mode == "grayscale_allow_white":
        shaped = [min(252, max(45, value)) for value in ordered]
        shaped.insert(0, 252)
    elif mode == "warm_grayscale":
        shaped = [min(188, max(76, value)) for value in ordered]
        shaped.extend([172, 136, 96])
    else:
        shaped = [min(205, max(62, value)) for value in ordered]
    result: list[int] = []
    for value in shaped:
        value = int(max(0, min(255, value)))
        if value not in result:
            result.append(value)
        if len(result) >= desired:
            break
    return _repeat_to_count(result, desired)

def monochrome_palette(image_bytes: bytes, desired: int, mode: str) -> list[RGB] | None:
    """Build a palette for monochrome or near-monochrome artwork.

    Several modes are deliberately grayscale-only so Neutral Tone Handling remains
    visible without reintroducing red/pink/brown drift on black-and-white covers.
    """
    if mode == "disabled":
        return None
    if mode == "muted_accent":
        return _repeat_to_count([(190, 170, 145), (120, 135, 150), (155, 130, 115), (105, 110, 118)], desired)

    grayscale_modes = {
        "grayscale",
        "grayscale_reduce_whites",
        "grayscale_contrast",
        "grayscale_graphic",
        "grayscale_allow_white",
        "warm_grayscale",
    }
    if mode in grayscale_modes:
        try:
            ct = ColorThief(BytesIO(image_bytes))
            raw = ct.get_palette(color_count=max(desired * 4, 12), quality=3)
            values = [int(luminance(color) * 255) for color in raw]
        except Exception:
            values = [205, 160, 120, 80]
        shaped = shape_monochrome_values(values, desired, mode)
        if mode == "warm_grayscale":
            return [tint_warm_gray(value) for value in shaped[:desired]]
        return [(value, value, value) for value in shaped[:desired]]

    return _repeat_to_count([(225, 204, 178), (190, 170, 148), (150, 135, 122), (110, 100, 95)], desired)

def dominant_accent_candidates(candidates: list[RGB]) -> list[RGB]:
    accents = []
    for rgb in candidates:
        _h, s, v = _hsv(rgb)
        if s >= 0.34 and 0.20 <= v <= 0.92 and not is_bright_white(rgb):
            accents.append(rgb)
    return _clustered_select(accents, max(1, min(len(accents), 6)))

def dark_anchor_candidates(candidates: list[RGB]) -> list[RGB]:
    anchors = []
    for rgb in candidates:
        h, s, v = _hsv(rgb)
        if 0.08 <= v <= 0.34 and (s >= 0.08 or v >= 0.16):
            adjusted_v = max(v, 0.18)
            adjusted_s = min(max(s, 0.14), 0.42)
            r, g, b = colorsys.hsv_to_rgb(h, adjusted_s, adjusted_v)
            anchors.append((int(r * 255), int(g * 255), int(b * 255)))
    return _clustered_select(anchors, max(1, min(len(anchors), 4)))

def accent_preserving_low_color_palette(candidates: list[RGB], desired: int) -> list[RGB] | None:
    accents = dominant_accent_candidates(candidates)
    if not accents:
        return None
    anchors = dark_anchor_candidates(candidates)
    soft_neutrals = []
    for rgb in candidates:
        h, s, v = _hsv(rgb)
        if is_bright_white(rgb):
            continue
        if s < 0.22 and 0.24 <= v <= 0.82:
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

def muted_low_color_palette(candidates: list[RGB], desired: int) -> list[RGB]:
    muted = []
    for rgb in candidates:
        h, s, v = _hsv(rgb)
        if v < 0.16 or is_bright_white(rgb):
            continue
        s = min(s, 0.28)
        v = max(0.34, min(v, 0.78))
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        color = (int(r * 255), int(g * 255), int(b * 255))
        if color not in muted:
            muted.append(color)
    if not muted:
        muted = [(190, 175, 158), (145, 150, 155), (120, 112, 105), (100, 115, 125)]
    return _clustered_select(muted, desired) or _repeat_to_count(muted, desired)
