from __future__ import annotations

import math

from homeassistant.helpers import entity_registry as er

from .const import (
    ASSIGNMENT_STRATEGY_ALTERNATING,
    ASSIGNMENT_STRATEGY_BALANCED,
    ASSIGNMENT_STRATEGY_BRIGHTNESS,
    ASSIGNMENT_STRATEGY_SEQUENTIAL,
)
from .palette import luminance

GRADIENT_HINTS = ("gradient", "signe", "play gradient", "lightstrip plus gradient")

def is_gradient_entity(hass, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)

    haystack = " ".join(
        str(x or "").lower()
        for x in (
            entity_id,
            state.attributes.get("friendly_name") if state else "",
            entry.name if entry else "",
            entry.original_name if entry else "",
            entry.unique_id if entry else "",
            state.attributes.get("model") if state else "",
        )
    )

    effects = state.attributes.get("effect_list") if state else []
    if isinstance(effects, list):
        haystack += " " + " ".join(str(e).lower() for e in effects)

    return any(hint in haystack for hint in GRADIENT_HINTS)

def _color_score(color: tuple[int, int, int]) -> float:
    r, g, b = [x / 255 for x in color]
    mx = max(r, g, b)
    mn = min(r, g, b)
    saturation = 0 if mx == 0 else (mx - mn) / mx
    return saturation * 0.65 + luminance(color) * 0.35

def _reorder_palette_for_strategy(palette: list[tuple[int, int, int]], strategy: str) -> list[tuple[int, int, int]]:
    if not palette:
        return palette
    if strategy == ASSIGNMENT_STRATEGY_SEQUENTIAL:
        return palette
    if strategy == ASSIGNMENT_STRATEGY_BRIGHTNESS:
        return sorted(palette, key=luminance, reverse=True)
    if strategy == ASSIGNMENT_STRATEGY_ALTERNATING:
        bright = sorted(palette, key=luminance, reverse=True)
        output = []
        left = 0
        right = len(bright) - 1
        while left <= right:
            output.append(bright[left])
            if left != right:
                output.append(bright[right])
            left += 1
            right -= 1
        return output

    # Balanced: strongest/most useful colors first, then spread by index.
    return sorted(palette, key=_color_score, reverse=True)

def assign_colors(hass, resolved_lights: list[str], palette: list[tuple[int, int, int]], strategy: str) -> dict[str, tuple[int, int, int]]:
    ordered_palette = _reorder_palette_for_strategy(palette, strategy)
    if not ordered_palette:
        return {}

    assignments: dict[str, tuple[int, int, int]] = {}
    gradient_lights = [light for light in resolved_lights if is_gradient_entity(hass, light)]
    normal_lights = [light for light in resolved_lights if light not in gradient_lights]

    accent_palette = sorted(ordered_palette, key=_color_score, reverse=True)
    for idx, light in enumerate(gradient_lights):
        assignments[light] = accent_palette[idx % len(accent_palette)]

    if strategy == ASSIGNMENT_STRATEGY_BALANCED and normal_lights:
        step = max(1, math.floor(len(ordered_palette) / max(1, min(len(normal_lights), len(ordered_palette)))))
        color_indexes = [(i * step) % len(ordered_palette) for i in range(len(normal_lights))]
    else:
        color_indexes = list(range(len(normal_lights)))

    for idx, light in enumerate(normal_lights):
        assignments[light] = ordered_palette[color_indexes[idx] % len(ordered_palette)]

    return assignments
