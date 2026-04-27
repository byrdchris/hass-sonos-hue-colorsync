from __future__ import annotations

import colorsys
import hashlib
import math
from collections import Counter
from io import BytesIO

from colorthief import ColorThief
from PIL import Image, ImageFilter

from .const import (
    CONF_COLOR_ACCURACY_MODE,
    COLOR_ACCURACY_MODE_ALBUM,
    COLOR_ACCURACY_MODE_NATURAL,
    COLOR_ACCURACY_MODE_VIVID,
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

def _effective_color_config(config: dict | None) -> dict:
    effective = dict(config or {})
    mode = effective.get(CONF_COLOR_ACCURACY_MODE, COLOR_ACCURACY_MODE_NATURAL)
    if mode == COLOR_ACCURACY_MODE_VIVID:
        effective["filter_dull"] = True
        effective["filter_bright_white"] = True
        effective[CONF_WHITE_HANDLING] = WHITE_HANDLING_CONTEXTUAL
        effective[CONF_WHITE_FILTER_STRENGTH] = WHITE_FILTER_STRENGTH_STRONG
        effective.setdefault("palette_ordering", "vivid_first")
    elif mode == COLOR_ACCURACY_MODE_ALBUM:
        effective["filter_dull"] = False
        effective["filter_bright_white"] = True
        effective[CONF_WHITE_HANDLING] = WHITE_HANDLING_CONTEXTUAL
        effective[CONF_WHITE_FILTER_STRENGTH] = WHITE_FILTER_STRENGTH_GENTLE
    else:
        effective["filter_dull"] = True
        effective["filter_bright_white"] = True
        effective[CONF_WHITE_HANDLING] = WHITE_HANDLING_CONTEXTUAL
        effective[CONF_WHITE_FILTER_STRENGTH] = WHITE_FILTER_STRENGTH_BALANCED
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


def _repeat_to_count(colors: list[RGB], desired: int) -> list[RGB]:
    if not colors:
        return [(220, 198, 176)] * desired
    return [colors[idx % len(colors)] for idx in range(desired)]


def _monochrome_palette(image_bytes: bytes, desired: int, mode: str) -> list[RGB] | None:
    if mode == "disabled":
        return None
    if mode == "muted_accent":
        return _repeat_to_count([(190, 170, 145), (120, 135, 150), (155, 130, 115), (105, 110, 118)], desired)
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


def extract_palette_from_bytes(image_bytes: bytes, config: dict) -> list[RGB]:
    config = _effective_color_config(config)
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
        accent_palette = _accent_preserving_low_color_palette(candidates, desired)
        if accent_palette:
            return accent_palette[:desired]
        return _muted_low_color_palette(candidates, desired)[:desired]

    if config.get("filter_dull", True):
        filtered = [c for c in candidates if not is_dull(c)]
        candidates = filtered or candidates

    candidates = _apply_white_handling(candidates, config)

    perceptual = _rebalance_album_palette(candidates, image_bytes, desired, ordering)
    if perceptual:
        return perceptual[:desired]

    if ordering == "dominant_first":
        dominant = _dominant_select(candidates, desired)
        return dominant[:desired] or [(220, 198, 176)]

    clustered = _clustered_select(candidates, desired)
    return clustered[:desired] or [(220, 198, 176)]


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
