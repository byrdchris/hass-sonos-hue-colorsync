from __future__ import annotations

# Auto artwork style classifier and auto-style behavior modifier.
# brief-code-commented-build: moderate block-level comments added for maintainability.

import colorsys
from collections import Counter
from io import BytesIO
from PIL import Image

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
    AUTO_STYLE_ACCURACY,
    AUTO_STYLE_AMBIENT,
    AUTO_STYLE_BALANCED,
    AUTO_STYLE_EXPRESSIVE,
    AUTO_STYLE_VIVID,
    CONF_ARTWORK_STYLE,
    CONF_AUTO_STYLE_BEHAVIOR,
    CONF_NEUTRAL_TONE_HANDLING,
    DEFAULT_ARTWORK_STYLE,
    NEUTRAL_TONE_WARM_AMBIENT,
)
from .models import RGB, AutoStyleDiagnostics, FinalPaletteGuardrails
from .palette_neutral import luminance

def _hsv(rgb: RGB) -> tuple[float, float, float]:
    r, g, b = [x / 255 for x in rgb]
    return colorsys.rgb_to_hsv(r, g, b)

def _repeat_to_count(colors: list[RGB], desired: int) -> list[RGB]:
    if not colors:
        return [(220, 198, 176)] * desired
    return [colors[idx % len(colors)] for idx in range(desired)]

def clamp_channel(value: float) -> int:
    """Clamp a computed color channel into the Hue-safe RGB range."""
    return int(max(0, min(255, round(value))))

def color_to_hex(color: RGB) -> str:
    """Format an RGB tuple for diagnostics without depending on public helpers."""
    return "#{:02X}{:02X}{:02X}".format(*color)

def dedupe_rgb_preserve_order(colors: list[RGB]) -> list[RGB]:
    """Remove duplicate RGB colors while keeping the generated palette order."""
    output: list[RGB] = []
    seen: set[RGB] = set()
    for color in colors:
        rgb = tuple(int(max(0, min(255, channel))) for channel in color)  # type: ignore[assignment]
        if rgb not in seen:
            seen.add(rgb)
            output.append(rgb)
    return output

def detect_auto_artwork_style(image_bytes: bytes, config: dict) -> tuple[str, dict]:
    """Classify album art with local image statistics only.

    Keeps Auto Artwork Style offline and deterministic while avoiding
    per-track manual tuning.
    """
    behavior = config.get(CONF_AUTO_STYLE_BEHAVIOR, AUTO_STYLE_BALANCED)
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        image.thumbnail((96, 96))
        pixels = list(image.getdata())
    except Exception:
        return ARTWORK_STYLE_ALBUM, {
            "detected_style": ARTWORK_STYLE_ALBUM,
            "confidence": "low",
            "reasons": ["image analysis failed"],
            "behavior": behavior,
        }

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
    elif behavior == AUTO_STYLE_EXPRESSIVE:
        if vivid_ratio > 0.10:
            scores[ARTWORK_STYLE_BOLD] += 0.22
        elif neutral_ratio > 0.45 or avg_sat < 0.25:
            scores[ARTWORK_STYLE_SOFT] += 0.18
        else:
            scores[ARTWORK_STYLE_NATURAL] += 0.16
        reasons.append("auto intensity is expressive")

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

    diagnostics: AutoStyleDiagnostics = {
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

def should_downgrade_low_confidence_auto(detected: str, diagnostics: dict, behavior: str) -> bool:
    """Return true when Auto should avoid a strong stylized preset."""
    if not diagnostics or diagnostics.get("confidence") != "low":
        return False
    if diagnostics.get("monochrome_guardrail"):
        return False
    if behavior in (AUTO_STYLE_VIVID, AUTO_STYLE_AMBIENT):
        return False
    return detected not in (ARTWORK_STYLE_ALBUM, ARTWORK_STYLE_NATURAL)

def image_is_neutral_heavy_from_diagnostics(diagnostics: dict | None) -> bool:
    """Identify artwork where Warm Ambient is appropriate."""
    metrics = (diagnostics or {}).get("metrics") or {}
    try:
        neutral_ratio = float(metrics.get("neutral_ratio", 0.0))
        bright_neutral_ratio = float(metrics.get("bright_neutral_ratio", 0.0))
        average_saturation = float(metrics.get("average_saturation", 1.0))
        vivid_ratio = float(metrics.get("vivid_ratio", 0.0))
    except (TypeError, ValueError):
        return False
    return (neutral_ratio >= 0.35 or bright_neutral_ratio >= 0.18) and average_saturation <= 0.36 and vivid_ratio <= 0.18

def final_palette_guardrails(palette: list[RGB], config: dict, desired: int) -> list[RGB]:
    """Apply safety checks after all palette processing."""
    if not palette:
        return palette
    diagnostics = config.get("_auto_artwork_style_diagnostics") or {}
    detected = config.get("_auto_artwork_style_detected")
    neutral_mode = config.get(CONF_NEUTRAL_TONE_HANDLING)
    guard: FinalPaletteGuardrails = {
        "applied": False,
        "reason": "not_needed",
        "detected_style": detected,
        "confidence": diagnostics.get("confidence"),
        "neutral_tone_handling": neutral_mode,
    }

    if neutral_mode == NEUTRAL_TONE_WARM_AMBIENT and not image_is_neutral_heavy_from_diagnostics(diagnostics):
        original = palette[:desired]
        corrected: list[RGB] = []
        for color in original:
            h, s, v = _hsv(color)
            if (h <= 0.12 or h >= 0.94) and s < 0.55 and v < 0.62:
                s = min(s, 0.42)
                v = max(v, 0.16)
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                corrected.append((clamp_channel(r * 255), clamp_channel(g * 255), clamp_channel(b * 255)))
            else:
                corrected.append(color)
        palette = _repeat_to_count(dedupe_rgb_preserve_order(corrected), desired)[:desired]
        guard.update({
            "applied": True,
            "reason": "warm_ambient_skipped_for_non_neutral_artwork",
            "before": [color_to_hex(c) for c in original],
            "after": [color_to_hex(c) for c in palette],
        })

    config["_final_palette_guardrails"] = guard
    return palette[:desired]

def shape_auto_behavior_color(color: RGB, behavior: str) -> RGB:
    """Apply the Auto Style Behavior preference as a visible final palette pass."""
    h, s, v = _hsv(color)

    if behavior == AUTO_STYLE_AMBIENT:
        if v < 0.30:
            v = 0.30 + (v * 0.28)
        else:
            v = 0.48 + ((v - 0.48) * 0.55)
        v = max(0.30, min(0.78, v))
        s = min(0.42, s * 0.50)
        if s < 0.10:
            h = 0.10
            s = max(s, 0.08)
    elif behavior == AUTO_STYLE_VIVID:
        if s >= 0.12:
            s = min(0.95, max(0.34, s * 1.45))
            v = max(0.22, min(0.98, v * 1.06))
        else:
            v = max(0.28, min(0.88, v * 0.92))
    elif behavior == AUTO_STYLE_ACCURACY:
        s = min(s, 0.68)
        if v < 0.16:
            v = 0.16
        elif v > 0.92 and s < 0.18:
            v = 0.90
    elif behavior == AUTO_STYLE_EXPRESSIVE:
        if s >= 0.12:
            s = min(0.82, max(s, s * 1.18))
            v = max(0.18, min(0.94, v * 1.04))
        elif v < 0.35:
            v = min(0.48, v * 1.18 + 0.04)
    else:
        return color

    r, g, b = colorsys.hsv_to_rgb(h, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return (clamp_channel(r * 255), clamp_channel(g * 255), clamp_channel(b * 255))

def apply_auto_style_behavior_to_palette(palette: list[RGB], config: dict, desired: int) -> list[RGB]:
    """Make Auto Style Behavior a visible second-stage modifier."""
    behavior = config.get(CONF_AUTO_STYLE_BEHAVIOR, AUTO_STYLE_BALANCED)
    selected_style = config.get("_selected_artwork_style")
    if selected_style != ARTWORK_STYLE_AUTO or behavior == AUTO_STYLE_BALANCED or not palette:
        config["_auto_style_behavior_diagnostics"] = {
            "applied": False,
            "behavior": behavior,
            "reason": "balanced_or_manual_style",
        }
        return palette[:desired]

    if config.get("_monochrome_guardrail_applied"):
        config["_auto_style_behavior_diagnostics"] = {
            "applied": False,
            "behavior": behavior,
            "reason": "monochrome_guardrail_preserved_neutral_identity",
        }
        return palette[:desired]

    before = palette[:desired]
    shaped = [shape_auto_behavior_color(color, behavior) for color in before]
    shaped = _repeat_to_count(dedupe_rgb_preserve_order(shaped), desired)[:desired]
    config["_auto_style_behavior_diagnostics"] = {
        "applied": True,
        "behavior": behavior,
        "detected_style": config.get("_auto_artwork_style_detected", config.get(CONF_ARTWORK_STYLE)),
        "strength": "strong" if behavior in (AUTO_STYLE_AMBIENT, AUTO_STYLE_VIVID) else "moderate",
        "before": [color_to_hex(color) for color in before],
        "after": [color_to_hex(color) for color in shaped],
        "reason": "final_palette_behavior_shaping",
    }
    return shaped

def prepare_palette_config_for_image(image_bytes: bytes, config: dict) -> dict:
    prepared = dict(config or {})
    selected_style = prepared.get(CONF_ARTWORK_STYLE, DEFAULT_ARTWORK_STYLE)
    if selected_style == ARTWORK_STYLE_AUTO:
        detected, diagnostics = detect_auto_artwork_style(image_bytes, prepared)
        behavior = prepared.get(CONF_AUTO_STYLE_BEHAVIOR, AUTO_STYLE_BALANCED)
        applied_style = detected
        if should_downgrade_low_confidence_auto(detected, diagnostics, behavior):
            applied_style = ARTWORK_STYLE_ALBUM
            diagnostics = dict(diagnostics)
            diagnostics["applied_style"] = applied_style
            diagnostics["classifier_style"] = detected
            diagnostics["confidence_fallback_applied"] = True
            diagnostics.setdefault("reasons", [])
            diagnostics["reasons"] = list(diagnostics["reasons"])[:5] + ["low-confidence Auto used album-accurate handling"]
        else:
            diagnostics = dict(diagnostics)
            diagnostics["applied_style"] = applied_style
            diagnostics["confidence_fallback_applied"] = False
        prepared["_selected_artwork_style"] = ARTWORK_STYLE_AUTO
        prepared[CONF_ARTWORK_STYLE] = applied_style
        prepared["_auto_artwork_style_diagnostics"] = diagnostics
        prepared["_auto_artwork_style_detected"] = applied_style
        prepared["_auto_artwork_style_classifier_detected"] = detected
    elif selected_style == ARTWORK_STYLE_ADVANCED:
        prepared["_selected_artwork_style"] = selected_style
        prepared[CONF_ARTWORK_STYLE] = ARTWORK_STYLE_NATURAL
        prepared["_advanced_overrides_active"] = True
    else:
        prepared["_selected_artwork_style"] = selected_style
        prepared["_auto_artwork_style_diagnostics"] = {"enabled": False}
    return prepared
