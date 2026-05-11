from __future__ import annotations

# Palette processing. Extracts album-art colors, suppresses low-value neutrals, handles white filtering, and preserves useful accent colors.
# brief-code-commented-build: moderate block-level comments added for maintainability.

import colorsys
import hashlib
import math
from collections import Counter
from io import BytesIO

from colorthief import ColorThief
from PIL import Image, ImageFilter

from .const import (
    CONF_ARTWORK_STYLE,
    CONF_COLOR_ACCURACY_MODE,
    CONF_NEUTRAL_TONE_HANDLING,
    CONF_COLOR_PURITY,
    CONF_PALETTE_COHERENCE,
    CONF_WHITE_LEVEL,
    DEFAULT_PALETTE_COHERENCE,
    PALETTE_COHERENCE_BALANCED,
    PALETTE_COHERENCE_OFF,
    PALETTE_COHERENCE_STRICT,
    COLOR_ACCURACY_MODE_ALBUM,
    COLOR_ACCURACY_MODE_NATURAL,
    COLOR_ACCURACY_MODE_VIVID,
    ARTWORK_STYLE_ADVANCED,
    ARTWORK_STYLE_ALBUM,
    ARTWORK_STYLE_AUTO,
    ARTWORK_STYLE_BOLD,
    ARTWORK_STYLE_CINEMATIC,
    ARTWORK_STYLE_GRAPHIC,
    ARTWORK_STYLE_MONOCHROME,
    ARTWORK_STYLE_NATURAL,
    ARTWORK_STYLE_PHOTOGRAPHY,
    ARTWORK_STYLE_SOFT,
    AUTO_STYLE_ACCURACY,
    AUTO_STYLE_AMBIENT,
    AUTO_STYLE_BALANCED,
    AUTO_STYLE_VIVID,
    CONF_AUTO_STYLE_BEHAVIOR,
    DEFAULT_ARTWORK_STYLE,
    DEFAULT_NEUTRAL_TONE_HANDLING,
    NEUTRAL_TONE_ADVANCED,
    NEUTRAL_TONE_ALLOW_WHITE,
    NEUTRAL_TONE_GRAPHIC,
    NEUTRAL_TONE_NATURAL,
    NEUTRAL_TONE_PRESERVE_CONTRAST,
    NEUTRAL_TONE_REDUCE_WHITES,
    NEUTRAL_TONE_WARM_AMBIENT,
    CONF_WHITE_HANDLING,
    CONF_WHITE_FILTER_STRENGTH,
    WHITE_FILTER_STRENGTH_BALANCED,
    WHITE_FILTER_STRENGTH_GENTLE,
    WHITE_FILTER_STRENGTH_STRONG,
    WHITE_HANDLING_ALWAYS_FILTER,
    WHITE_HANDLING_ALLOW,
    WHITE_HANDLING_CONTEXTUAL,
)

RGB = tuple[int, int, int]

# Resolve palette behavior from Color Accuracy Mode, Color Purity, and white controls.
# Color Purity is intentionally album-fidelity based: 100 preserves the album
# palette most closely, while 0 strongly favors saturated accent colors.
def _effective_color_config(config: dict | None) -> dict:
    effective = dict(config or {})

    # Artwork Style is the primary user-facing color intent. Legacy Advanced / Custom
    # is accepted only as a compatibility value; new UI choices use named outcomes.
    artwork_style = effective.get(CONF_ARTWORK_STYLE, DEFAULT_ARTWORK_STYLE)
    if artwork_style in (ARTWORK_STYLE_ADVANCED, None):
        artwork_style = ARTWORK_STYLE_NATURAL
        effective[CONF_ARTWORK_STYLE] = artwork_style
        effective["_advanced_overrides_active"] = True
    if artwork_style != ARTWORK_STYLE_AUTO:
        style_map = {
            ARTWORK_STYLE_NATURAL: (COLOR_ACCURACY_MODE_NATURAL, "65", "dominant_first", PALETTE_COHERENCE_BALANCED),
            ARTWORK_STYLE_ALBUM: (COLOR_ACCURACY_MODE_ALBUM, "90", "dominant_first", PALETTE_COHERENCE_BALANCED),
            ARTWORK_STYLE_GRAPHIC: (COLOR_ACCURACY_MODE_ALBUM, "20", "vivid_first", PALETTE_COHERENCE_STRICT),
            ARTWORK_STYLE_PHOTOGRAPHY: (COLOR_ACCURACY_MODE_NATURAL, "70", "dominant_first", PALETTE_COHERENCE_BALANCED),
            ARTWORK_STYLE_CINEMATIC: (COLOR_ACCURACY_MODE_NATURAL, "80", "dominant_first", PALETTE_COHERENCE_BALANCED),
            ARTWORK_STYLE_SOFT: (COLOR_ACCURACY_MODE_NATURAL, "80", "dominant_first", PALETTE_COHERENCE_OFF),
            ARTWORK_STYLE_BOLD: (COLOR_ACCURACY_MODE_VIVID, "20", "vivid_first", PALETTE_COHERENCE_STRICT),
            ARTWORK_STYLE_MONOCHROME: (COLOR_ACCURACY_MODE_ALBUM, "85", "dominant_first", PALETTE_COHERENCE_BALANCED),
        }
        mode, purity_value, ordering, coherence = style_map.get(artwork_style, style_map[ARTWORK_STYLE_NATURAL])
        effective[CONF_COLOR_ACCURACY_MODE] = mode
        effective[CONF_COLOR_PURITY] = purity_value
        effective["palette_ordering"] = ordering
        effective[CONF_PALETTE_COHERENCE] = coherence
        effective["_artwork_style_applied"] = artwork_style

    # Neutral Tone Handling combines white and black/white behavior. Legacy
    # Advanced / Custom maps to Natural because Home Assistant select states need
    # stable declared options.
    neutral_style = effective.get(CONF_NEUTRAL_TONE_HANDLING, DEFAULT_NEUTRAL_TONE_HANDLING)
    if neutral_style == NEUTRAL_TONE_ADVANCED:
        neutral_style = NEUTRAL_TONE_NATURAL
        effective[CONF_NEUTRAL_TONE_HANDLING] = neutral_style
        effective["_advanced_overrides_active"] = True
    if neutral_style != NEUTRAL_TONE_ADVANCED:
        neutral_map = {
            NEUTRAL_TONE_NATURAL: (WHITE_HANDLING_CONTEXTUAL, 50, "warm_neutral"),
            NEUTRAL_TONE_REDUCE_WHITES: (WHITE_HANDLING_ALWAYS_FILTER, 75, "warm_neutral"),
            NEUTRAL_TONE_PRESERVE_CONTRAST: (WHITE_HANDLING_ALLOW, 15, "grayscale"),
            NEUTRAL_TONE_WARM_AMBIENT: (WHITE_HANDLING_CONTEXTUAL, 35, "warm_neutral"),
            NEUTRAL_TONE_GRAPHIC: (WHITE_HANDLING_ALLOW, 15, "grayscale"),
            NEUTRAL_TONE_ALLOW_WHITE: (WHITE_HANDLING_ALLOW, 0, "disabled"),
        }
        white_mode, white_level_value, mono_mode = neutral_map.get(neutral_style, neutral_map[NEUTRAL_TONE_NATURAL])
        effective[CONF_WHITE_HANDLING] = white_mode
        effective[CONF_WHITE_LEVEL] = white_level_value
        effective["monochrome_mode"] = mono_mode
        effective["_neutral_tone_handling_applied"] = neutral_style

    # Monochrome guardrails are intentionally stronger than user-facing vivid or
    # warm modes. If Auto determined the source has no real chroma, preserve
    # grayscale identity instead of stacking legacy warm-neutral conversion with
    # Warm Ambient / Prefer Vivid behavior.
    if _is_monochrome_guard_active(effective):
        effective[CONF_COLOR_ACCURACY_MODE] = COLOR_ACCURACY_MODE_ALBUM
        effective[CONF_COLOR_PURITY] = "95"
        effective["palette_ordering"] = "dominant_first"
        effective[CONF_PALETTE_COHERENCE] = PALETTE_COHERENCE_OFF
        # Keep the neutral handling white behavior from the map above, but force
        # the monochrome path into safe low-chroma variants.
        effective["monochrome_mode"] = _monochrome_guardrail_palette_mode(effective)
        effective["_monochrome_guardrail_applied"] = True
        effective["_monochrome_guardrail_neutral_mode"] = effective.get(CONF_NEUTRAL_TONE_HANDLING)
        effective["_monochrome_guardrail_palette_mode"] = effective.get("monochrome_mode")

    mode = effective.get(CONF_COLOR_ACCURACY_MODE, COLOR_ACCURACY_MODE_NATURAL)
    # Accept both legacy numeric values and new preset string values. If a
    # display-only custom marker ever appears, fall back safely to Balanced.
    try:
        purity = int(effective.get(CONF_COLOR_PURITY, 65))
    except (TypeError, ValueError):
        purity = 65
    purity = max(0, min(100, purity))

    # Convert purity into filtering strength. Lower purity means more vivid,
    # saturated colors; higher purity leaves more low-saturation album tones.
    if purity >= 80:
        effective["filter_dull"] = False
        effective.setdefault("palette_ordering", "dominant_first")
    elif purity <= 35:
        effective["filter_dull"] = True
        effective.setdefault("palette_ordering", "vivid_first")
    else:
        effective["filter_dull"] = True

    if mode == COLOR_ACCURACY_MODE_ALBUM:
        effective["filter_dull"] = purity < 90
        effective.setdefault("palette_ordering", "dominant_first")
    elif mode == COLOR_ACCURACY_MODE_VIVID:
        effective["filter_dull"] = True
        effective.setdefault("palette_ordering", "vivid_first")

    # White Suppression maps to internal strength only when whites are being reduced.
    white_level = max(0, min(100, int(effective.get(CONF_WHITE_LEVEL, 50))))
    if white_level <= 20:
        effective[CONF_WHITE_FILTER_STRENGTH] = WHITE_FILTER_STRENGTH_GENTLE
        effective["filter_bright_white"] = False
    elif white_level >= 75:
        effective[CONF_WHITE_FILTER_STRENGTH] = WHITE_FILTER_STRENGTH_STRONG
        effective["filter_bright_white"] = True
    else:
        effective[CONF_WHITE_FILTER_STRENGTH] = WHITE_FILTER_STRENGTH_BALANCED
        effective["filter_bright_white"] = True
    return effective


def _hsv(rgb: RGB) -> tuple[float, float, float]:
    r, g, b = [x / 255 for x in rgb]
    return colorsys.rgb_to_hsv(r, g, b)


def luminance(rgb: RGB) -> float:
    r, g, b = [x / 255 for x in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


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


def _apply_white_handling(candidates: list[RGB], config: dict) -> list[RGB]:
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


def _rgb_distance(a: RGB, b: RGB) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def _hue_distance(a: RGB, b: RGB) -> float:
    ha, sa, _va = _hsv(a)
    hb, sb, _vb = _hsv(b)
    if sa < 0.18 or sb < 0.18:
        return abs(luminance(a) - luminance(b)) * 180
    diff = abs(ha - hb)
    return min(diff, 1 - diff) * 360


# Score colors by perceptual usefulness rather than raw area alone.
# Warm accents are promoted while flat neutrals, black, and harsh whites are reduced.
def _colorfulness_score(rgb: RGB) -> float:
    h, s, v = _hsv(rgb)
    lum = luminance(rgb)
    warm_accent = 0.20 if ((h <= 0.12 or h >= 0.90) and s >= 0.25 and 0.25 <= v <= 0.92) else 0.0
    skin_or_warm = 0.18 if (0.03 <= h <= 0.13 and 0.18 <= s <= 0.70 and 0.30 <= v <= 0.95) else 0.0
    neutral_penalty = -0.38 if s < 0.18 else 0.0
    near_black_penalty = -0.45 if v < 0.22 else 0.0
    near_white_penalty = -0.35 if v > 0.88 and s < 0.22 else 0.0
    return (s * 0.58) + (v * 0.18) + (lum * 0.10) + warm_accent + skin_or_warm + neutral_penalty + near_black_penalty + near_white_penalty


def _visual_score(rgb: RGB) -> float:
    return _colorfulness_score(rgb)


def _dominant_select(candidates: list[RGB], desired: int) -> list[RGB]:
    selected: list[RGB] = []
    for color in candidates:
        if color not in selected:
            selected.append(color)
        if len(selected) >= desired:
            break
    return selected[:desired]


def _clustered_select(candidates: list[RGB], desired: int) -> list[RGB]:
    if not candidates:
        return []
    ordered = sorted(candidates, key=_visual_score, reverse=True)
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
    ratio = _image_chroma_ratio(image_bytes)
    if ratio is None:
        return "full_color"
    if ratio < 0.035:
        return "monochrome"
    if ratio < 0.10:
        return "low_color"
    return "full_color"


def _is_monochrome_guard_active(config: dict | None) -> bool:
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


def _monochrome_guardrail_palette_mode(config: dict | None) -> str:
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


def _tint_warm_gray(value: int) -> RGB:
    """Return a warm off-white/greige, not a colored red/brown."""
    # The previous tint was too subtle on Hue devices and looked identical to
    # white. This keeps saturation low while making Warm Ambient visibly warmer.
    return (
        max(0, min(255, value + 16)),
        max(0, min(255, value + 7)),
        max(0, min(255, value - 16)),
    )


def _shape_monochrome_values(values: list[int], desired: int, mode: str) -> list[int]:
    """Adjust grayscale luminance stops for each Neutral Tone Handling mode."""
    if not values:
        values = [190, 150, 110]
    ordered = sorted(dict.fromkeys(values), reverse=True)
    if mode == "grayscale_reduce_whites":
        # Strongly cap bright neutrals so Reduce Whites visibly lowers white output.
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
        # Keep whites below the pure-white range so warm handling appears as a
        # warm neutral wash instead of the same Hue white state.
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


def _repeat_to_count(colors: list[RGB], desired: int) -> list[RGB]:
    if not colors:
        return [(220, 198, 176)] * desired
    return [colors[idx % len(colors)] for idx in range(desired)]


def _monochrome_palette(image_bytes: bytes, desired: int, mode: str) -> list[RGB] | None:
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
        shaped = _shape_monochrome_values(values, desired, mode)
        if mode == "warm_grayscale":
            return [_tint_warm_gray(value) for value in shaped[:desired]]
        return [(value, value, value) for value in shaped[:desired]]

    # Legacy warm-neutral mode remains available outside the Auto monochrome
    # guardrail for users who explicitly prefer warm neutral lighting.
    return _repeat_to_count([(225, 204, 178), (190, 170, 148), (150, 135, 122), (110, 100, 95)], desired)


def _dominant_accent_candidates(candidates: list[RGB]) -> list[RGB]:
    accents = []
    for rgb in candidates:
        _h, s, v = _hsv(rgb)
        if s >= 0.34 and 0.20 <= v <= 0.92 and not is_bright_white(rgb):
            accents.append(rgb)
    return _clustered_select(accents, max(1, min(len(accents), 6)))


def _dark_anchor_candidates(candidates: list[RGB]) -> list[RGB]:
    anchors = []
    for rgb in candidates:
        h, s, v = _hsv(rgb)
        if 0.08 <= v <= 0.34 and (s >= 0.08 or v >= 0.16):
            adjusted_v = max(v, 0.18)
            adjusted_s = min(max(s, 0.14), 0.42)
            r, g, b = colorsys.hsv_to_rgb(h, adjusted_s, adjusted_v)
            anchors.append((int(r * 255), int(g * 255), int(b * 255)))
    return _clustered_select(anchors, max(1, min(len(anchors), 4)))


def _accent_preserving_low_color_palette(candidates: list[RGB], desired: int) -> list[RGB] | None:
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


def _muted_low_color_palette(candidates: list[RGB], desired: int) -> list[RGB]:
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



def _graphic_poster_palette(image_bytes: bytes, desired: int, config: dict) -> list[RGB] | None:
    """Extract flat, high-contrast poster colors without inventing intermediates.

    This mode is for typography/pop-art covers where the important colors are
    large graphic blocks. It prioritizes area + saturation, preserves contrast,
    maps black into a usable dim accent, and suppresses small hue outliers.
    """
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((128, 128))
        pixels = list(img.getdata())
    except Exception:
        return None
    if not pixels:
        return None

    buckets: Counter[RGB] = Counter()
    for rgb in pixels:
        h, s, v = _hsv(rgb)
        # Quantize strongly so flat graphic regions remain flat instead of
        # splitting into many anti-aliased edge colors.
        bucket = tuple(max(0, min(255, int(round(c / 32) * 32))) for c in rgb)  # type: ignore[assignment]
        if v < 0.08:
            bucket = (16, 16, 16)
        elif v > 0.90 and s < 0.18:
            bucket = (240, 240, 224)
        buckets[bucket] += 1

    total = sum(buckets.values()) or 1
    scored: list[tuple[float, RGB, float, float, float]] = []
    for color, count in buckets.items():
        h, s, v = _hsv(color)
        area = count / total
        is_dark = v < 0.18
        is_light_neutral = v > 0.82 and s < 0.22
        is_graphic_red = (h <= 0.08 or h >= 0.94) and s >= 0.35 and 0.25 <= v <= 1.0
        is_bold_color = s >= 0.40 and 0.20 <= v <= 0.98
        # Area matters more than edge/interpolation for graphic art. Saturated
        # blocks and high-contrast anchors get a boost; tiny accents are ignored.
        score = area * 8.0
        if is_graphic_red:
            score *= 2.8
        elif is_bold_color:
            score *= 1.8
        elif is_light_neutral or is_dark:
            score *= 1.35
        else:
            score *= 0.75
        if area < 0.006 and not is_graphic_red:
            score *= 0.15
        scored.append((score, color, h, s, v))

    scored.sort(reverse=True, key=lambda item: item[0])
    chromatic = [item for item in scored if item[3] >= 0.28 and item[4] >= 0.18]
    darks = [item for item in scored if item[4] < 0.22]
    lights = [item for item in scored if item[4] > 0.78 and item[3] < 0.28]

    # If one hue family dominates the graphic colors, reject small unrelated hue
    # artifacts that often come from compression or anti-aliased typography.
    dominant_hue = None
    if chromatic:
        totals = []
        for _score, _color, hue, _s, _v in chromatic[:8]:
            totals.append((sum(score for score, _c, other_hue, _os, _ov in chromatic if _hue_distance_degrees(hue, other_hue) <= 45), hue))
        dominant_score, dominant_hue = max(totals, key=lambda item: item[0])
        chromatic_total = sum(item[0] for item in chromatic) or 1.0
        if dominant_score / chromatic_total >= 0.55:
            chromatic = [item for item in chromatic if _hue_distance_degrees(item[2], dominant_hue) <= 65]

    result: list[RGB] = []

    # Add saturated poster colors first, preserving flat block appearance.
    for _score, color, _h, _s, _v in chromatic:
        if all(_rgb_distance(color, existing) >= 35 for existing in result):
            result.append(color)
        if len(result) >= max(2, desired - 2):
            break

    # Black cannot render as a useful Hue color, so convert it to a dim version
    # of the dominant hue when possible; otherwise use deep warm charcoal.
    if darks and len(result) < desired:
        if dominant_hue is not None:
            r, g, b = colorsys.hsv_to_rgb(dominant_hue, 0.72, 0.24)
            dark_color = (int(r * 255), int(g * 255), int(b * 255))
        else:
            dark_color = (58, 42, 36)
        result.append(dark_color)

    # Preserve one light/off-white contrast anchor unless the user explicitly
    # asked to strongly reduce whites.
    if lights and len(result) < desired and config.get(CONF_WHITE_HANDLING) != WHITE_HANDLING_ALWAYS_FILTER:
        result.append(lights[0][1])

    # Fill remaining slots from scored major areas without allowing tiny outliers.
    for _score, color, _h, _s, _v in scored:
        if len(result) >= desired:
            break
        if color in result:
            continue
        if all(_rgb_distance(color, existing) >= 28 for existing in result):
            result.append(color)

    if not result:
        return None
    return _repeat_to_count(result, desired)[:desired]

def _weighted_image_candidates(image_bytes: bytes, desired: int) -> list[RGB]:
    """Build perceptual palette candidates from image pixels, not only dominant clusters.

    The weighting intentionally favors chroma, edges, warm/accent details, and de-emphasizes
    dominant low-saturation backgrounds. This fixes covers where gray/blue backdrops occupy
    most pixels but are not the visually important album-art colors.
    """
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((96, 96))
        edges = img.convert("L").filter(ImageFilter.FIND_EDGES)
        pixels = list(img.getdata())
        edge_pixels = list(edges.getdata())
    except Exception:
        return []

    if not pixels:
        return []

    buckets: Counter[RGB] = Counter()
    neutral_buckets: Counter[RGB] = Counter()
    for rgb, edge in zip(pixels, edge_pixels, strict=False):
        h, s, v = _hsv(rgb)
        if v < 0.06 or (v > 0.96 and s < 0.10):
            continue

        bucket = tuple(max(0, min(255, int(round(c / 16) * 16))) for c in rgb)  # type: ignore[assignment]
        edge_boost = 0.6 + min(edge / 255.0, 1.0) * 1.4
        chroma = max(s, 0.02)
        mid_luma = 1.0 - min(abs(v - 0.58) / 0.58, 1.0) * 0.35
        warm = 1.25 if (0.02 <= h <= 0.14 and 0.18 <= s <= 0.75 and 0.22 <= v <= 0.95) else 1.0
        red_accent = 1.25 if ((h <= 0.05 or h >= 0.92) and s >= 0.32 and 0.22 <= v <= 0.92) else 1.0
        neutral_penalty = 0.28 if s < 0.16 else 1.0
        dark_penalty = 0.35 if v < 0.18 else 1.0
        weight = int(100 * edge_boost * (0.25 + chroma) * mid_luma * warm * red_accent * neutral_penalty * dark_penalty)
        if weight <= 0:
            continue
        if s < 0.18:
            neutral_buckets[bucket] += weight
        else:
            buckets[bucket] += weight

    colorful = [rgb for rgb, _count in buckets.most_common(max(desired * 12, 24))]
    neutrals = [rgb for rgb, _count in neutral_buckets.most_common(max(desired * 4, 8))]
    selected = _clustered_select(colorful, max(desired, 6))

    # Allow at most one muted neutral/background support color after real colors.
    if selected and neutrals:
        selected.extend(_clustered_select(neutrals, 1))
    return selected[: max(desired * 2, desired)]


def _rebalance_album_palette(candidates: list[RGB], image_bytes: bytes, desired: int, ordering: str) -> list[RGB]:
    weighted = _weighted_image_candidates(image_bytes, desired)
    pool: list[RGB] = []
    for group in (weighted, candidates):
        for color in group:
            if color not in pool:
                pool.append(color)

    if not pool:
        return []

    # Suppress a dominant neutral if enough chromatic colors exist.
    chromatic = [c for c in pool if is_real_color(c) and not is_soft_or_bright_white(c)]
    if ordering != "dominant_first" and len(chromatic) >= max(2, min(desired, 3)):
        pool = chromatic + [c for c in pool if c not in chromatic and _hsv(c)[1] >= 0.12]

    if ordering == "dominant_first":
        # Preserve dominance, but replace excess neutral/black candidates with perceptual colors.
        dominant = _dominant_select(pool, desired)
        if sum(1 for c in dominant if is_real_color(c)) < min(2, desired) and chromatic:
            dominant = _clustered_select(chromatic + dominant, desired)
        return dominant[:desired]

    return _clustered_select(pool, desired)[:desired]


# Compute circular hue distance in degrees for outlier detection.
def _hue_distance_degrees(hue_a: float, hue_b: float) -> float:
    diff = abs(hue_a - hue_b)
    return min(diff, 1.0 - diff) * 360.0


# Remove isolated hue outliers without hard-coding any specific color family.
# Balanced removes only obvious outsiders; Strict keeps a more unified hue family.
def _apply_palette_coherence(palette: list[RGB], source_candidates: list[RGB], desired: int, config: dict) -> list[RGB]:
    mode = config.get(CONF_PALETTE_COHERENCE, DEFAULT_PALETTE_COHERENCE)
    diagnostics = {
        "mode": mode,
        "applied": False,
        "removed_colors": [],
        "dominant_hue_degrees": None,
        "dominant_cluster_score": None,
        "reason": None,
    }
    config["_palette_coherence_diagnostics"] = diagnostics

    if mode == PALETTE_COHERENCE_OFF or not palette:
        diagnostics["reason"] = "disabled"
        return palette

    chromatic = []
    for idx, color in enumerate(palette):
        hue, saturation, value = _hsv(color)
        if saturation >= 0.24 and 0.16 <= value <= 0.96:
            # Earlier palette entries are more important because ordering already
            # reflects the selected Dominant/Vivid preference.
            score = (len(palette) - idx) * (0.55 + saturation) * (0.55 + value)
            chromatic.append((color, hue, saturation, value, score))

    if len(chromatic) < 3:
        diagnostics["reason"] = "not_enough_chromatic_colors"
        return palette

    cluster_radius = 90.0 if mode == PALETTE_COHERENCE_BALANCED else 75.0
    keep_radius = 105.0 if mode == PALETTE_COHERENCE_BALANCED else 85.0
    minimum_ratio = 0.45 if mode == PALETTE_COHERENCE_BALANCED else 0.38

    best_hue = None
    best_score = -1.0
    total_score = sum(item[4] for item in chromatic) or 1.0
    for _color, hue, _sat, _value, _score in chromatic:
        score = sum(item[4] for item in chromatic if _hue_distance_degrees(hue, item[1]) <= cluster_radius)
        if score > best_score:
            best_score = score
            best_hue = hue

    if best_hue is None or (best_score / total_score) < minimum_ratio:
        diagnostics["reason"] = "multicolor_palette_preserved"
        diagnostics["dominant_cluster_score"] = round(best_score / total_score, 3)
        return palette

    kept: list[RGB] = []
    removed: list[RGB] = []
    for color in palette:
        hue, saturation, value = _hsv(color)
        if saturation < 0.20 or value < 0.16:
            kept.append(color)
            continue
        if _hue_distance_degrees(hue, best_hue) <= keep_radius:
            kept.append(color)
        else:
            removed.append(color)

    if not removed:
        diagnostics["reason"] = "no_outliers_found"
        diagnostics["dominant_hue_degrees"] = round(best_hue * 360.0, 1)
        diagnostics["dominant_cluster_score"] = round(best_score / total_score, 3)
        return palette

    # Refill from source candidates that fit the dominant hue family so Color Count
    # remains stable without reintroducing isolated colors.
    for color in source_candidates:
        if len(kept) >= desired:
            break
        if color in kept or color in removed:
            continue
        hue, saturation, value = _hsv(color)
        if saturation < 0.20 or _hue_distance_degrees(hue, best_hue) <= keep_radius:
            kept.append(color)

    result = _repeat_to_count(kept or palette, desired)[:desired]
    diagnostics.update({
        "applied": True,
        "removed_colors": ["#{:02X}{:02X}{:02X}".format(*color) for color in removed],
        "dominant_hue_degrees": round(best_hue * 360.0, 1),
        "dominant_cluster_score": round(best_score / total_score, 3),
        "reason": "outliers_removed",
    })
    return result


# Classify album art with local image statistics only. This keeps Auto Artwork
# Style offline and deterministic while avoiding per-track manual tuning.
def _detect_auto_artwork_style(image_bytes: bytes, config: dict) -> tuple[str, dict]:
    behavior = config.get(CONF_AUTO_STYLE_BEHAVIOR, AUTO_STYLE_BALANCED)
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        image.thumbnail((96, 96))
        pixels = list(image.getdata())
    except Exception:
        return ARTWORK_STYLE_ALBUM, {"detected_style": ARTWORK_STYLE_ALBUM, "confidence": "low", "reasons": ["image analysis failed"], "behavior": behavior}

    total = max(1, len(pixels))
    hsv_values = [_hsv(pixel) for pixel in pixels]
    saturations = [s for _h, s, _v in hsv_values]
    values = [v for _h, _s, v in hsv_values]
    luminances = [luminance(pixel) for pixel in pixels]

    avg_sat = sum(saturations) / total
    avg_value = sum(values) / total
    dark_ratio = sum(1 for _h, _s, v in hsv_values if v < 0.18) / total
    bright_ratio = sum(1 for _h, s, v in hsv_values if v > 0.86 and s < 0.20) / total
    neutral_ratio = sum(1 for _h, s, _v in hsv_values if s < 0.12) / total
    vivid_ratio = sum(1 for _h, s, v in hsv_values if s > 0.55 and 0.22 < v < 0.96) / total
    contrast = max(luminances) - min(luminances) if luminances else 0.0

    # Quantize to rough buckets to estimate flat graphic blocks and color diversity.
    buckets = Counter((r // 32, g // 32, b // 32) for r, g, b in pixels)
    top_bucket_ratio = buckets.most_common(1)[0][1] / total if buckets else 0.0
    dominant_bucket_ratio = sum(count for _bucket, count in buckets.most_common(4)) / total if buckets else 0.0
    diversity = len(buckets) / total

    reasons: list[str] = []
    scores = {
        ARTWORK_STYLE_ALBUM: 0.35,
        ARTWORK_STYLE_NATURAL: 0.25,
        ARTWORK_STYLE_GRAPHIC: 0.0,
        ARTWORK_STYLE_PHOTOGRAPHY: 0.0,
        ARTWORK_STYLE_CINEMATIC: 0.0,
        ARTWORK_STYLE_SOFT: 0.0,
        ARTWORK_STYLE_BOLD: 0.0,
        ARTWORK_STYLE_MONOCHROME: 0.0,
    }

    if neutral_ratio > 0.62 and avg_sat < 0.22:
        scores[ARTWORK_STYLE_MONOCHROME] += 1.15
        reasons.append("mostly grayscale or neutral")
    if contrast > 0.62 and (dark_ratio + bright_ratio) > 0.34 and dominant_bucket_ratio > 0.42:
        scores[ARTWORK_STYLE_GRAPHIC] += 1.1
        reasons.append("high contrast with large flat color areas")
    if dominant_bucket_ratio > 0.55 and diversity < 0.35:
        scores[ARTWORK_STYLE_GRAPHIC] += 0.55
        reasons.append("few dominant color blocks")
    if vivid_ratio > 0.24 and contrast > 0.45:
        scores[ARTWORK_STYLE_BOLD] += 0.85
        reasons.append("strong saturated colors")
    if diversity > 0.45 and avg_sat < 0.48 and neutral_ratio < 0.70:
        scores[ARTWORK_STYLE_PHOTOGRAPHY] += 0.75
        reasons.append("many smooth midtones")
    if dark_ratio > 0.28 and contrast > 0.40 and avg_value < 0.52:
        scores[ARTWORK_STYLE_CINEMATIC] += 0.70
        reasons.append("dark moody contrast")
    if avg_sat < 0.24 and contrast < 0.50:
        scores[ARTWORK_STYLE_SOFT] += 0.65
        reasons.append("low saturation, gentle contrast")

    if behavior == AUTO_STYLE_ACCURACY:
        scores[ARTWORK_STYLE_ALBUM] += 0.45
        scores[ARTWORK_STYLE_PHOTOGRAPHY] += 0.20
        reasons.append("auto behavior prefers accuracy")
    elif behavior == AUTO_STYLE_VIVID:
        scores[ARTWORK_STYLE_BOLD] += 0.45
        scores[ARTWORK_STYLE_GRAPHIC] += 0.25
        reasons.append("auto behavior prefers vivid lighting")
    elif behavior == AUTO_STYLE_AMBIENT:
        scores[ARTWORK_STYLE_SOFT] += 0.45
        scores[ARTWORK_STYLE_NATURAL] += 0.25
        reasons.append("auto behavior prefers ambient lighting")

    # Hard monochrome protection: vivid preference should not turn true
    # black-and-white artwork into red/pink/brown. Strong neutral metrics win
    # over poster/vivid scoring and route into the monochrome pipeline.
    monochrome_guard = (
        avg_sat <= 0.18
        and neutral_ratio >= 0.56
        and vivid_ratio <= 0.02
        and diversity <= 0.08
    )
    if monochrome_guard:
        scores[ARTWORK_STYLE_MONOCHROME] += 1.25
        reasons.append("monochrome guardrail preserved grayscale tones")

    detected = max(scores, key=scores.get)
    ordered_scores = sorted(scores.values(), reverse=True)
    margin = ordered_scores[0] - (ordered_scores[1] if len(ordered_scores) > 1 else 0)
    confidence = "high" if margin >= 0.55 else "medium" if margin >= 0.25 else "low"
    if detected in (ARTWORK_STYLE_ALBUM, ARTWORK_STYLE_NATURAL) and not reasons:
        reasons.append("defaulted to general album-art handling")

    diagnostics = {
        "enabled": True,
        "detected_style": detected,
        "confidence": confidence,
        "reasons": reasons[:6],
        "behavior": behavior,
        "metrics": {
            "average_saturation": round(avg_sat, 3),
            "average_brightness": round(avg_value, 3),
            "dark_ratio": round(dark_ratio, 3),
            "bright_neutral_ratio": round(bright_ratio, 3),
            "neutral_ratio": round(neutral_ratio, 3),
            "vivid_ratio": round(vivid_ratio, 3),
            "contrast": round(contrast, 3),
            "top_color_block_ratio": round(top_bucket_ratio, 3),
            "dominant_color_block_ratio": round(dominant_bucket_ratio, 3),
            "color_diversity": round(diversity, 3),
        },
        "monochrome_guardrail": bool(monochrome_guard),
        "scores": {key: round(value, 3) for key, value in scores.items()},
    }
    return detected, diagnostics



def _clamp_channel(value: float) -> int:
    """Clamp a computed color channel into the Hue-safe RGB range."""
    return int(max(0, min(255, round(value))))


def _color_to_hex(color: RGB) -> str:
    """Format an RGB tuple for diagnostics without depending on public helpers."""
    return "#{:02X}{:02X}{:02X}".format(*color)


def _shape_auto_behavior_color(color: RGB, behavior: str) -> RGB:
    """Apply the Auto Style Behavior preference as a visible final palette pass.

    Auto detection chooses the artwork type. This pass makes the user's behavior
    preference authoritative enough to see in Home Assistant without letting it
    break monochrome guardrails or explicit neutral handling.
    """
    h, s, v = _hsv(color)

    if behavior == AUTO_STYLE_AMBIENT:
        # Ambient should visibly soften poster/high-contrast output: brighten
        # very dark colors, lower harsh whites, and reduce chroma while keeping
        # the same general hue family.
        if v < 0.30:
            v = 0.30 + (v * 0.28)
        else:
            v = 0.48 + ((v - 0.48) * 0.55)
        v = max(0.30, min(0.78, v))
        s = min(0.42, s * 0.50)
        if s < 0.10:
            # Give neutral whites a slight room-light warmth instead of leaving
            # them as stark white, especially when Reduce Whites is active.
            h = 0.10
            s = max(s, 0.08)
    elif behavior == AUTO_STYLE_VIVID:
        # Vivid should produce a clear difference: lift usable dark colors and
        # increase saturation, but avoid turning true whites into neon colors.
        if s >= 0.12:
            s = min(0.95, max(0.34, s * 1.45))
            v = max(0.22, min(0.98, v * 1.06))
        else:
            v = max(0.28, min(0.88, v * 0.92))
    elif behavior == AUTO_STYLE_ACCURACY:
        # Accuracy should reduce the most stylized/vivid outcomes and keep the
        # palette closer to the artwork's extracted luminance relationships.
        s = min(s, 0.72)
        if v < 0.16:
            v = 0.16
        elif v > 0.92 and s < 0.18:
            v = 0.90
    else:
        return color

    r, g, b = colorsys.hsv_to_rgb(h, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return (_clamp_channel(r * 255), _clamp_channel(g * 255), _clamp_channel(b * 255))



def _dedupe_rgb_preserve_order(colors: list[RGB]) -> list[RGB]:
    """Remove duplicate RGB colors while keeping the generated palette order."""
    output: list[RGB] = []
    seen: set[RGB] = set()
    for color in colors:
        rgb = tuple(int(max(0, min(255, channel))) for channel in color)  # type: ignore[assignment]
        if rgb not in seen:
            seen.add(rgb)
            output.append(rgb)
    return output

def _apply_auto_style_behavior_to_palette(palette: list[RGB], config: dict, desired: int) -> list[RGB]:
    """Make Auto Style Behavior a visible second-stage modifier.

    Earlier builds used the behavior mainly as a classifier bias. That could be
    too subtle after Graphic / Poster or other strong styles won detection. This
    keeps detection intact while shaping the final palette in a way users can see.
    """
    behavior = config.get(CONF_AUTO_STYLE_BEHAVIOR, AUTO_STYLE_BALANCED)
    selected_style = config.get("_selected_artwork_style")
    if selected_style != ARTWORK_STYLE_AUTO or behavior == AUTO_STYLE_BALANCED or not palette:
        config["_auto_style_behavior_diagnostics"] = {
            "applied": False,
            "behavior": behavior,
            "reason": "balanced_or_manual_style",
        }
        return palette[:desired]

    # Keep hard monochrome protection in control of true black-and-white art.
    # Neutral Tone Handling remains responsible for grayscale/white behavior.
    if config.get("_monochrome_guardrail_applied"):
        config["_auto_style_behavior_diagnostics"] = {
            "applied": False,
            "behavior": behavior,
            "reason": "monochrome_guardrail_preserved_neutral_identity",
        }
        return palette[:desired]

    before = palette[:desired]
    shaped = [_shape_auto_behavior_color(color, behavior) for color in before]
    shaped = _repeat_to_count(_dedupe_rgb_preserve_order(shaped), desired)[:desired]
    config["_auto_style_behavior_diagnostics"] = {
        "applied": True,
        "behavior": behavior,
        "detected_style": config.get("_auto_artwork_style_detected", config.get(CONF_ARTWORK_STYLE)),
        "strength": "strong" if behavior in (AUTO_STYLE_AMBIENT, AUTO_STYLE_VIVID) else "moderate",
        "before": [_color_to_hex(color) for color in before],
        "after": [_color_to_hex(color) for color in shaped],
        "reason": "final_palette_behavior_shaping",
    }
    return shaped

def _prepare_palette_config_for_image(image_bytes: bytes, config: dict) -> dict:
    # Auto style changes only the effective extraction config; the user-selected
    # option remains Auto in Home Assistant. Diagnostics expose the detected style.
    prepared = dict(config or {})
    selected_style = prepared.get(CONF_ARTWORK_STYLE, DEFAULT_ARTWORK_STYLE)
    if selected_style == ARTWORK_STYLE_AUTO:
        detected, diagnostics = _detect_auto_artwork_style(image_bytes, prepared)
        prepared["_selected_artwork_style"] = ARTWORK_STYLE_AUTO
        prepared[CONF_ARTWORK_STYLE] = detected
        prepared["_auto_artwork_style_diagnostics"] = diagnostics
        prepared["_auto_artwork_style_detected"] = detected
    elif selected_style == ARTWORK_STYLE_ADVANCED:
        prepared["_selected_artwork_style"] = selected_style
        prepared[CONF_ARTWORK_STYLE] = ARTWORK_STYLE_NATURAL
        prepared["_advanced_overrides_active"] = True
    else:
        prepared["_selected_artwork_style"] = selected_style
        prepared["_auto_artwork_style_diagnostics"] = {"enabled": False}
    return prepared


# Extract the final Hue-ready palette from album art.
# Combines quantization, perceptual scoring, filtering, fallback handling, and ordering.
def extract_palette_from_bytes(image_bytes: bytes, config: dict) -> list[RGB]:
    prepared_config = _prepare_palette_config_for_image(image_bytes, config)
    config.clear()
    config.update(prepared_config)
    effective_config = _effective_color_config(config)
    config.clear()
    config.update(effective_config)
    desired = int(config.get("color_count", 3))
    color_class = _image_color_class(image_bytes)
    if _is_monochrome_guard_active(config):
        config["_monochrome_guardrail_applied"] = True
        guard_mode = config.get("monochrome_mode", _monochrome_guardrail_palette_mode(config))
        mono = _monochrome_palette(image_bytes, desired, guard_mode)
        if mono:
            config["_artwork_style_diagnostics"] = {
                "mode": "monochrome_guardrail",
                "algorithm": "safe_neutral_tone_handling_with_visible_white_shaping",
                "neutral_tone_handling": config.get(CONF_NEUTRAL_TONE_HANDLING),
                "palette_mode": guard_mode,
                "white_behavior": "brightness_and_color_temperature_shaped_for_neutral_art",
                "result": ["#{:02X}{:02X}{:02X}".format(*color) for color in mono[:desired]],
            }
            return _apply_auto_style_behavior_to_palette(mono[:desired], config, desired)
    if color_class == "monochrome":
        mono = _monochrome_palette(image_bytes, desired, config.get("monochrome_mode", "warm_neutral"))
        if mono:
            return _apply_auto_style_behavior_to_palette(mono[:desired], config, desired)

    ct = ColorThief(BytesIO(image_bytes))
    candidates = ct.get_palette(color_count=max(desired * 6, 20), quality=3)
    ordering = config.get("palette_ordering", "vivid_first")

    if config.get(CONF_ARTWORK_STYLE) in (ARTWORK_STYLE_GRAPHIC, ARTWORK_STYLE_BOLD):
        graphic = _graphic_poster_palette(image_bytes, desired, config)
        if graphic:
            config["_artwork_style_diagnostics"] = {
                "mode": config.get(CONF_ARTWORK_STYLE),
                "algorithm": "graphic_poster_flat_color_blocks",
                "result": ["#{:02X}{:02X}{:02X}".format(*color) for color in graphic],
            }
            return _apply_auto_style_behavior_to_palette(graphic[:desired], config, desired)

    if color_class == "low_color" and config.get("low_color_handling", True) and ordering != "dominant_first":
        accent_palette = _accent_preserving_low_color_palette(candidates, desired)
        if accent_palette:
            return _apply_auto_style_behavior_to_palette(accent_palette[:desired], config, desired)
        return _apply_auto_style_behavior_to_palette(_muted_low_color_palette(candidates, desired)[:desired], config, desired)

    if config.get("filter_dull", True):
        filtered = [c for c in candidates if not is_dull(c)]
        candidates = filtered or candidates

    candidates = _apply_white_handling(candidates, config)

    perceptual = _rebalance_album_palette(candidates, image_bytes, desired, ordering)
    if perceptual:
        palette = perceptual[:desired]
    elif ordering == "dominant_first":
        dominant = _dominant_select(candidates, desired)
        palette = dominant[:desired] or [(220, 198, 176)]
    else:
        clustered = _clustered_select(candidates, desired)
        palette = clustered[:desired] or [(220, 198, 176)]

    coherent = _apply_palette_coherence(palette, candidates, desired, config)
    return _apply_auto_style_behavior_to_palette(coherent, config, desired)


def rgb_to_hex(rgb: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def fallback_palette_from_metadata(metadata: str, desired: int) -> list[RGB]:
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


def warm_neutral_fallback_palette(desired: int) -> list[RGB]:
    desired = max(1, int(desired or 3))
    base = [(255, 214, 170), (220, 190, 150), (180, 160, 130), (130, 115, 100)]
    return _repeat_to_count(base, desired)[:desired]
