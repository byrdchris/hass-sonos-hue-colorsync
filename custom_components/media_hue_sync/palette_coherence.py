from __future__ import annotations

# Palette coherence subsystem. Manages hue clustering, dominant hue filtering, and vivid accent preservation.
# brief-code-commented-build: moderate block-level comments added for maintainability.

import colorsys
from .const import (
    CONF_PALETTE_COHERENCE,
    DEFAULT_PALETTE_COHERENCE,
    PALETTE_COHERENCE_BALANCED,
    PALETTE_COHERENCE_DOMINANT_ACCENT,
    PALETTE_COHERENCE_DOMINANT_ONLY,
    PALETTE_COHERENCE_NATURAL,
    PALETTE_COHERENCE_OFF,
    PALETTE_COHERENCE_STRICT,
)
from .models import RGB, CoherenceDiagnostics

def _hsv(rgb: RGB) -> tuple[float, float, float]:
    r, g, b = [x / 255 for x in rgb]
    return colorsys.rgb_to_hsv(r, g, b)

def _repeat_to_count(colors: list[RGB], desired: int) -> list[RGB]:
    if not colors:
        return [(220, 198, 176)] * desired
    return [colors[idx % len(colors)] for idx in range(desired)]

def hue_distance_degrees(hue_a: float, hue_b: float) -> float:
    """Compute circular hue distance in degrees for outlier detection."""
    diff = abs(hue_a - hue_b)
    return min(diff, 1.0 - diff) * 360.0

def apply_palette_coherence(palette: list[RGB], source_candidates: list[RGB], desired: int, config: dict) -> list[RGB]:
    """Remove isolated hue outliers without hard-coding any specific color family.

    Natural preserves the extraction, Balanced removes only weak outsiders,
    Dominant Colors Only keeps the cohesive look, and Dominant + Vivid
    Accent restores one or two strong intentional accent colors.
    """
    raw_mode = config.get(CONF_PALETTE_COHERENCE, DEFAULT_PALETTE_COHERENCE)
    legacy_aliases = {
        PALETTE_COHERENCE_OFF: PALETTE_COHERENCE_NATURAL,
        PALETTE_COHERENCE_STRICT: PALETTE_COHERENCE_DOMINANT_ONLY,
    }
    mode = legacy_aliases.get(raw_mode, raw_mode)
    diagnostics: CoherenceDiagnostics = {
        "mode": mode,
        "raw_mode": str(raw_mode),
        "applied": False,
        "removed_colors": [],
        "preserved_accent_colors": [],
        "dominant_hue_degrees": None,
        "dominant_cluster_score": None,
        "reason": None,
    }
    config["_palette_coherence_diagnostics"] = diagnostics

    if mode == PALETTE_COHERENCE_NATURAL or not palette:
        diagnostics["reason"] = "natural_preserved"
        return palette

    chromatic = []
    for idx, color in enumerate(palette):
        hue, saturation, value = _hsv(color)
        if saturation >= 0.24 and 0.16 <= value <= 0.96:
            # Earlier palette entries are more important because ordering already
            # reflects the selected Dominant/Vivid preference.
            score = (len(palette) - idx) * (0.55 + saturation) * (0.55 + value)
            chromatic.append((color, hue, saturation, value, score, idx))

    if len(chromatic) < 3:
        diagnostics["reason"] = "not_enough_chromatic_colors"
        return palette

    if mode == PALETTE_COHERENCE_BALANCED:
        cluster_radius, keep_radius, minimum_ratio = 100.0, 118.0, 0.50
    elif mode == PALETTE_COHERENCE_DOMINANT_ACCENT:
        cluster_radius, keep_radius, minimum_ratio = 90.0, 92.0, 0.42
    else:
        cluster_radius, keep_radius, minimum_ratio = 75.0, 85.0, 0.38

    best_hue = None
    best_score = -1.0
    total_score = sum(item[4] for item in chromatic) or 1.0
    for _color, hue, _sat, _value, _score, _idx in chromatic:
        score = sum(item[4] for item in chromatic if hue_distance_degrees(hue, item[1]) <= cluster_radius)
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
        if hue_distance_degrees(hue, best_hue) <= keep_radius:
            kept.append(color)
        else:
            removed.append(color)

    if not removed and mode not in (PALETTE_COHERENCE_BALANCED, PALETTE_COHERENCE_DOMINANT_ACCENT):
        diagnostics["reason"] = "no_outliers_found"
        diagnostics["dominant_hue_degrees"] = round(best_hue * 360.0, 1)
        diagnostics["dominant_cluster_score"] = round(best_score / total_score, 3)
        return palette

    # Restore vivid accents only for modes intended to preserve intentional
    # contrast colors. Dominant Colors Only intentionally keeps the cohesive look.
    accent_limit = 0
    if mode == PALETTE_COHERENCE_BALANCED:
        accent_limit = 1
    elif mode == PALETTE_COHERENCE_DOMINANT_ACCENT:
        accent_limit = 2

    preserved_accents: list[RGB] = []
    if accent_limit:
        accent_candidates = []
        accent_source = list(removed)
        for color in source_candidates:
            if color not in kept and color not in accent_source:
                accent_source.append(color)
        for color in accent_source:
            hue, saturation, value = _hsv(color)
            distance = hue_distance_degrees(hue, best_hue)
            if saturation >= 0.62 and value >= 0.34 and distance >= max(75.0, keep_radius - 8.0):
                # Prefer vivid, visible, already-extracted accent colors.
                accent_candidates.append((color, saturation * value * (distance / 180.0)))
        for color, _score in sorted(accent_candidates, key=lambda item: item[1], reverse=True):
            if len(preserved_accents) >= accent_limit:
                break
            if color not in preserved_accents:
                preserved_accents.append(color)
        if preserved_accents:
            kept = kept[: max(0, desired - len(preserved_accents))] + preserved_accents

    # Refill from source candidates that fit the dominant hue family so Color Count
    # remains stable without reintroducing weak isolated colors.
    for color in source_candidates:
        if len(kept) >= desired:
            break
        if color in kept or color in removed:
            continue
        hue, saturation, value = _hsv(color)
        if saturation < 0.20 or hue_distance_degrees(hue, best_hue) <= keep_radius:
            kept.append(color)

    result = _repeat_to_count(kept or palette, desired)[:desired]
    diagnostics.update({
        "applied": True,
        "removed_colors": ["#{:02X}{:02X}{:02X}".format(*color) for color in removed],
        "preserved_accent_colors": ["#{:02X}{:02X}{:02X}".format(*color) for color in preserved_accents],
        "dominant_hue_degrees": round(best_hue * 360.0, 1),
        "dominant_cluster_score": round(best_score / total_score, 3),
        "reason": "dominant_only" if mode == PALETTE_COHERENCE_DOMINANT_ONLY else "outliers_filtered_with_accent_policy",
    })
    return result
