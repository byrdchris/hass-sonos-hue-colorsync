from __future__ import annotations

# Palette processing orchestrator and facade. Extracts album-art colors,
# suppresses low-value neutrals, handles white filtering, and preserves useful accent colors.
# brief-code-commented-build: moderate block-level comments added for maintainability.

import colorsys
import hashlib
from collections import Counter
from io import BytesIO

from colorthief import ColorThief
from PIL import Image, ImageFilter

from .const import (
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
    COLOR_ACCURACY_MODE_ALBUM,
    COLOR_ACCURACY_MODE_NATURAL,
    COLOR_ACCURACY_MODE_VIVID,
    CONF_ARTWORK_STYLE,
    CONF_COLOR_ACCURACY_MODE,
    CONF_COLOR_PURITY,
    CONF_NEUTRAL_TONE_HANDLING,
    CONF_PALETTE_COHERENCE,
    CONF_WHITE_FILTER_STRENGTH,
    CONF_WHITE_HANDLING,
    CONF_WHITE_LEVEL,
    DEFAULT_ARTWORK_STYLE,
    DEFAULT_NEUTRAL_TONE_HANDLING,
    NEUTRAL_TONE_ADVANCED,
    NEUTRAL_TONE_ALLOW_WHITE,
    NEUTRAL_TONE_GRAPHIC,
    NEUTRAL_TONE_NATURAL,
    NEUTRAL_TONE_PRESERVE_CONTRAST,
    NEUTRAL_TONE_REDUCE_WHITES,
    NEUTRAL_TONE_WARM_AMBIENT,
    PALETTE_COHERENCE_BALANCED,
    PALETTE_COHERENCE_DOMINANT_ACCENT,
    PALETTE_COHERENCE_DOMINANT_ONLY,
    PALETTE_COHERENCE_NATURAL,
    PALETTE_COHERENCE_OFF,
    WHITE_FILTER_STRENGTH_BALANCED,
    WHITE_FILTER_STRENGTH_GENTLE,
    WHITE_FILTER_STRENGTH_STRONG,
    WHITE_HANDLING_ALLOW,
    WHITE_HANDLING_ALWAYS_FILTER,
    WHITE_HANDLING_CONTEXTUAL,
)
from .models import RGB
from .palette_auto_style import (
    apply_auto_style_behavior_to_palette,
    clamp_channel,
    color_to_hex,
    dedupe_rgb_preserve_order,
    detect_auto_artwork_style,
    final_palette_guardrails,
    image_is_neutral_heavy_from_diagnostics,
    prepare_palette_config_for_image,
    shape_auto_behavior_color,
    should_downgrade_low_confidence_auto,
)
from .palette_coherence import (
    apply_palette_coherence,
    hue_distance_degrees,
)
from .palette_neutral import (
    accent_preserving_low_color_palette,
    apply_white_handling,
    dark_anchor_candidates,
    dominant_accent_candidates,
    image_chroma_ratio,
    image_color_class,
    is_bright_white,
    is_dull,
    is_monochrome_guard_active,
    is_real_color,
    is_soft_or_bright_white,
    luminance,
    monochrome_guardrail_palette_mode,
    monochrome_palette,
    muted_low_color_palette,
    shape_monochrome_values,
    tint_warm_gray,
    _clustered_select,
    _colorfulness_score,
    _hsv,
    _hue_distance,
    _repeat_to_count,
    _rgb_distance,
)

# Backwards-compatible aliases for private helper symbols
_hsv = _hsv
_rgb_distance = _rgb_distance
_hue_distance = _hue_distance
_hue_distance_degrees = hue_distance_degrees
_colorfulness_score = _colorfulness_score
_visual_score = _colorfulness_score
_clustered_select = _clustered_select
_image_chroma_ratio = image_chroma_ratio
_image_color_class = image_color_class
_is_monochrome_guard_active = is_monochrome_guard_active
_monochrome_guardrail_palette_mode = monochrome_guardrail_palette_mode
_tint_warm_gray = tint_warm_gray
_shape_monochrome_values = shape_monochrome_values
_monochrome_palette = monochrome_palette
_repeat_to_count = _repeat_to_count
_dominant_accent_candidates = dominant_accent_candidates
_dark_anchor_candidates = dark_anchor_candidates
_accent_preserving_low_color_palette = accent_preserving_low_color_palette
_muted_low_color_palette = muted_low_color_palette
_apply_palette_coherence = apply_palette_coherence
_detect_auto_artwork_style = detect_auto_artwork_style
_should_downgrade_low_confidence_auto = should_downgrade_low_confidence_auto
_image_is_neutral_heavy_from_diagnostics = image_is_neutral_heavy_from_diagnostics
_final_palette_guardrails = final_palette_guardrails
_clamp_channel = clamp_channel
_color_to_hex = color_to_hex
_shape_auto_behavior_color = shape_auto_behavior_color
_dedupe_rgb_preserve_order = dedupe_rgb_preserve_order
_apply_auto_style_behavior_to_palette = apply_auto_style_behavior_to_palette
_prepare_palette_config_for_image = prepare_palette_config_for_image
_apply_white_handling = apply_white_handling


def _effective_color_config(config: dict | None) -> dict:
    """Resolve palette behavior from Color Accuracy Mode, Color Purity, and white controls."""
    effective = dict(config or {})

    artwork_style = effective.get(CONF_ARTWORK_STYLE, DEFAULT_ARTWORK_STYLE)
    user_palette_coherence = effective.get(CONF_PALETTE_COHERENCE)
    if artwork_style in (ARTWORK_STYLE_ADVANCED, None):
        artwork_style = ARTWORK_STYLE_NATURAL
        effective[CONF_ARTWORK_STYLE] = artwork_style
        effective["_advanced_overrides_active"] = True
    if artwork_style != ARTWORK_STYLE_AUTO:
        style_map = {
            ARTWORK_STYLE_NATURAL: (COLOR_ACCURACY_MODE_NATURAL, "65", "dominant_first", PALETTE_COHERENCE_BALANCED),
            ARTWORK_STYLE_ALBUM: (COLOR_ACCURACY_MODE_ALBUM, "90", "dominant_first", PALETTE_COHERENCE_DOMINANT_ACCENT),
            ARTWORK_STYLE_GRAPHIC: (COLOR_ACCURACY_MODE_ALBUM, "20", "vivid_first", PALETTE_COHERENCE_DOMINANT_ONLY),
            ARTWORK_STYLE_PHOTOGRAPHY: (COLOR_ACCURACY_MODE_NATURAL, "70", "dominant_first", PALETTE_COHERENCE_BALANCED),
            ARTWORK_STYLE_CINEMATIC: (COLOR_ACCURACY_MODE_NATURAL, "80", "dominant_first", PALETTE_COHERENCE_BALANCED),
            ARTWORK_STYLE_SOFT: (COLOR_ACCURACY_MODE_NATURAL, "80", "dominant_first", PALETTE_COHERENCE_NATURAL),
            ARTWORK_STYLE_BOLD: (COLOR_ACCURACY_MODE_VIVID, "20", "vivid_first", PALETTE_COHERENCE_DOMINANT_ACCENT),
            ARTWORK_STYLE_MONOCHROME: (COLOR_ACCURACY_MODE_ALBUM, "85", "dominant_first", PALETTE_COHERENCE_BALANCED),
        }
        mode, purity_value, ordering, coherence = style_map.get(artwork_style, style_map[ARTWORK_STYLE_NATURAL])
        effective[CONF_COLOR_ACCURACY_MODE] = mode
        effective[CONF_COLOR_PURITY] = purity_value
        effective["palette_ordering"] = ordering
        effective[CONF_PALETTE_COHERENCE] = user_palette_coherence or coherence
        effective["_artwork_style_applied"] = artwork_style

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

    if is_monochrome_guard_active(effective):
        effective[CONF_COLOR_ACCURACY_MODE] = COLOR_ACCURACY_MODE_ALBUM
        effective[CONF_COLOR_PURITY] = "95"
        effective["palette_ordering"] = "dominant_first"
        effective[CONF_PALETTE_COHERENCE] = PALETTE_COHERENCE_OFF
        effective["monochrome_mode"] = monochrome_guardrail_palette_mode(effective)
        effective["_monochrome_guardrail_applied"] = True
        effective["_monochrome_guardrail_neutral_mode"] = effective.get(CONF_NEUTRAL_TONE_HANDLING)
        effective["_monochrome_guardrail_palette_mode"] = effective.get("monochrome_mode")

    mode = effective.get(CONF_COLOR_ACCURACY_MODE, COLOR_ACCURACY_MODE_NATURAL)
    try:
        purity = int(effective.get(CONF_COLOR_PURITY, 65))
    except (TypeError, ValueError):
        purity = 65
    purity = max(0, min(100, purity))

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


def _dominant_select(candidates: list[RGB], desired: int) -> list[RGB]:
    selected: list[RGB] = []
    for color in candidates:
        if color not in selected:
            selected.append(color)
        if len(selected) >= desired:
            break
    return selected[:desired]


def _graphic_poster_palette(image_bytes: bytes, desired: int, config: dict) -> list[RGB] | None:
    """Extract flat, high-contrast poster colors without inventing intermediates."""
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
        _h, s, v = _hsv(rgb)
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

    dominant_hue = None
    if chromatic:
        totals = []
        for _score, _color, hue, _s, _v in chromatic[:8]:
            totals.append((sum(score for score, _c, other_hue, _os, _ov in chromatic if hue_distance_degrees(hue, other_hue) <= 45), hue))
        dominant_score, dominant_hue = max(totals, key=lambda item: item[0])
        chromatic_total = sum(item[0] for item in chromatic) or 1.0
        if dominant_score / chromatic_total >= 0.55:
            chromatic = [item for item in chromatic if hue_distance_degrees(item[2], dominant_hue) <= 65]

    result: list[RGB] = []

    for _score, color, _h, _s, _v in chromatic:
        if all(_rgb_distance(color, existing) >= 35 for existing in result):
            result.append(color)
        if len(result) >= max(2, desired - 2):
            break

    if darks and len(result) < desired:
        if dominant_hue is not None:
            r, g, b = colorsys.hsv_to_rgb(dominant_hue, 0.72, 0.24)
            dark_color = (int(r * 255), int(g * 255), int(b * 255))
        else:
            dark_color = (58, 42, 36)
        result.append(dark_color)

    if lights and len(result) < desired and config.get(CONF_WHITE_HANDLING) != WHITE_HANDLING_ALWAYS_FILTER:
        result.append(lights[0][1])

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
    """Build perceptual palette candidates from image pixels."""
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

    chromatic = [c for c in pool if is_real_color(c) and not is_soft_or_bright_white(c)]
    if ordering != "dominant_first" and len(chromatic) >= max(2, min(desired, 3)):
        pool = chromatic + [c for c in pool if c not in chromatic and _hsv(c)[1] >= 0.12]

    if ordering == "dominant_first":
        dominant = _dominant_select(pool, desired)
        if sum(1 for c in dominant if is_real_color(c)) < min(2, desired) and chromatic:
            dominant = _clustered_select(chromatic + dominant, desired)
        return dominant[:desired]

    return _clustered_select(pool, desired)[:desired]


def extract_palette_from_bytes(image_bytes: bytes, config: dict) -> list[RGB]:
    """Extract the final Hue-ready palette from album art bytes."""
    prepared_config = prepare_palette_config_for_image(image_bytes, config)
    config.clear()
    config.update(prepared_config)
    effective_config = _effective_color_config(config)
    config.clear()
    config.update(effective_config)
    desired = int(config.get("color_count", 3))
    color_class = image_color_class(image_bytes)

    if is_monochrome_guard_active(config):
        config["_monochrome_guardrail_applied"] = True
        guard_mode = config.get("monochrome_mode", monochrome_guardrail_palette_mode(config))
        mono = monochrome_palette(image_bytes, desired, guard_mode)
        if mono:
            config["_artwork_style_diagnostics"] = {
                "mode": "monochrome_guardrail",
                "algorithm": "safe_neutral_tone_handling_with_visible_white_shaping",
                "neutral_tone_handling": config.get(CONF_NEUTRAL_TONE_HANDLING),
                "palette_mode": guard_mode,
                "white_behavior": "brightness_and_color_temperature_shaped_for_neutral_art",
                "result": ["#{:02X}{:02X}{:02X}".format(*color) for color in mono[:desired]],
            }
            return final_palette_guardrails(apply_auto_style_behavior_to_palette(mono[:desired], config, desired), config, desired)

    if color_class == "monochrome":
        mono = monochrome_palette(image_bytes, desired, config.get("monochrome_mode", "warm_neutral"))
        if mono:
            return final_palette_guardrails(apply_auto_style_behavior_to_palette(mono[:desired], config, desired), config, desired)

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
            return final_palette_guardrails(apply_auto_style_behavior_to_palette(graphic[:desired], config, desired), config, desired)

    if color_class == "low_color" and config.get("low_color_handling", True) and ordering != "dominant_first":
        accent_palette = accent_preserving_low_color_palette(candidates, desired)
        if accent_palette:
            return final_palette_guardrails(apply_auto_style_behavior_to_palette(accent_palette[:desired], config, desired), config, desired)
        return final_palette_guardrails(apply_auto_style_behavior_to_palette(muted_low_color_palette(candidates, desired)[:desired], config, desired), config, desired)

    if config.get("filter_dull", True):
        filtered = [c for c in candidates if not is_dull(c)]
        candidates = filtered or candidates

    candidates = apply_white_handling(candidates, config)

    perceptual = _rebalance_album_palette(candidates, image_bytes, desired, ordering)
    if perceptual:
        palette = perceptual[:desired]
    elif ordering == "dominant_first":
        dominant = _dominant_select(candidates, desired)
        palette = dominant[:desired] or [(220, 198, 176)]
    else:
        clustered = _clustered_select(candidates, desired)
        palette = clustered[:desired] or [(220, 198, 176)]

    coherent = apply_palette_coherence(palette, candidates, desired, config)
    return final_palette_guardrails(apply_auto_style_behavior_to_palette(coherent, config, desired), config, desired)


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
