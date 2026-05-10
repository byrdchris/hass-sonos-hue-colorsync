from __future__ import annotations

# Light apply helpers. Converts palette assignments into Home Assistant light service payloads for standard lights.
# brief-code-commented-build: moderate block-level comments added for maintainability.

import asyncio
import logging

from .hue_capabilities import gradient_capability_from_ha
from .palette import luminance
from .hue_gradient import try_apply_gradient

_LOGGER = logging.getLogger(__name__)

COLOR_MODES = ("rgb", "xy", "hs", "rgbw", "rgbww", "color_temp")
_LAST_APPLIED: dict[str, dict] = {}

def _supports(state, mode: str) -> bool:
    modes = state.attributes.get("supported_color_modes") or []
    return mode in modes

def _color_distance(a: list[int] | tuple[int, int, int] | None, b: list[int] | tuple[int, int, int] | None) -> int:
    if not a or not b:
        return 999
    return max(abs(int(a[i]) - int(b[i])) for i in range(3))

def _clamp_brightness(value: int, config: dict | None = None, gradient_aware: bool = False) -> int:
    config = config or {}
    min_brightness = int(config.get("min_brightness", 30))
    max_brightness = int(config.get("max_brightness", 255))
    if max_brightness < min_brightness:
        max_brightness = min_brightness
    if gradient_aware and config.get("gradient_brightness") is not None:
        max_brightness = min(max_brightness, int(config.get("gradient_brightness", max_brightness)))
    return max(min_brightness, min(max_brightness, int(value)))


def _is_neutral_rgb(color: tuple[int, int, int]) -> bool:
    # Treat near-grayscale RGB values as neutral tones. Hue reports these as whites,
    # so visible differences need brightness and color-temperature shaping.
    r, g, b = color
    return max(color) - min(color) <= 28


def _neutral_color_temperature(config: dict | None) -> int | None:
    # For monochrome guardrail palettes, use color temperature where possible so
    # Neutral Tone Handling visibly changes whites instead of only changing RGB
    # values that Hue normalizes back to white.
    config = config or {}
    if not config.get("_monochrome_guardrail_applied"):
        return None
    mode = config.get("neutral_tone_handling")
    if mode == "warm_ambient":
        return 3000
    if mode == "preserve_contrast":
        return 4200
    if mode == "graphic":
        return 5000
    if mode == "allow_pure_white":
        return 6500
    if mode == "reduce_whites":
        return 3700
    return 4600


def _brightness_for_color(color: tuple[int, int, int], config: dict | None = None) -> int:
    # Use stronger brightness shaping for monochrome artwork. RGB grays all map
    # to a white-ish Hue chromaticity, so reducing or preserving whites must be
    # visible through brightness as well as through palette values.
    base = int(50 + luminance(color) * 205)
    config = config or {}
    if not config.get("_monochrome_guardrail_applied") or not _is_neutral_rgb(color):
        return base
    mode = config.get("neutral_tone_handling")
    lum = luminance(color)
    if mode == "reduce_whites":
        return int(55 + lum * 115)
    if mode == "preserve_contrast":
        return int(45 + lum * 195)
    if mode == "warm_ambient":
        return int(60 + lum * 125)
    if mode == "graphic":
        return int(35 + lum * 210)
    if mode == "allow_pure_white":
        return int(70 + lum * 185)
    return int(55 + lum * 145)

def build_service_data(state, color: tuple[int, int, int], transition: float, config: dict | None = None, gradient_aware: bool = False) -> dict:
    brightness = _clamp_brightness(_brightness_for_color(color, config), config, gradient_aware)
    data = {"entity_id": state.entity_id, "brightness": brightness, "transition": transition}

    # For monochrome guardrail palettes, color_temp makes white/gray handling
    # visible on Hue bulbs. Plain rgb grays often round-trip through Hue as the
    # same white chromaticity, making the UI look unchanged.
    neutral_kelvin = _neutral_color_temperature(config) if _is_neutral_rgb(color) else None
    if neutral_kelvin and _supports(state, "color_temp"):
        data["color_temp_kelvin"] = int(neutral_kelvin)
        data["neutral_tone_color_temperature"] = int(neutral_kelvin)
    elif any(_supports(state, mode) for mode in ("rgb", "xy", "hs", "rgbw", "rgbww", "color_temp")):
        data["rgb_color"] = list(color)

    return data

def should_apply(entity_id: str, call_data: dict, rgb_tolerance: int = 6, brightness_tolerance: int = 4) -> tuple[bool, str]:
    previous = _LAST_APPLIED.get(entity_id)
    if previous is None:
        return True, "first_apply"

    if _color_distance(previous.get("rgb_color"), call_data.get("rgb_color")) > rgb_tolerance:
        return True, "color_changed"

    if abs(int(previous.get("brightness", 0)) - int(call_data.get("brightness", 0))) > brightness_tolerance:
        return True, "brightness_changed"

    if float(previous.get("transition", 0)) != float(call_data.get("transition", 0)):
        return True, "transition_changed"

    return False, "unchanged"

async def apply_assignments(hass, assignments: dict[str, tuple[int, int, int]], strategy: str, transition: float, palette=None, config=None) -> tuple[list[dict], list[dict]]:
    """Apply color assignments.

    True Hue gradient calls are still awaited per-light because they use the
    Hue bridge API directly. Standard Home Assistant light.turn_on calls are
    batched concurrently afterward, so non-gradient lights no longer wait behind
    each other one-by-one.
    """
    sent: list[dict] = []
    skipped: list[dict] = []
    pending_native: list[tuple[str, dict, dict]] = []

    for entity_id, color in assignments.items():
        state = hass.states.get(entity_id)
        if state is None:
            skipped.append({"entity_id": entity_id, "reason": "missing_at_apply"})
            continue
        if state.state in ("unavailable", "unknown"):
            skipped.append({"entity_id": entity_id, "reason": f"{state.state}_at_apply"})
            continue

        gradient_capability = gradient_capability_from_ha(hass, entity_id)
        gradient_aware = bool(gradient_capability.capable)
        true_gradient_enabled = bool((config or {}).get("true_gradient_mode", False))
        gradient_diag = None

        if true_gradient_enabled and gradient_aware and palette:
            success, gradient_diag = await try_apply_gradient(
                hass,
                entity_id,
                list(palette),
                color,
                int((config or {}).get("gradient_color_points", 5)),
                transition,
                order_mode=(config or {}).get("gradient_order_mode", "same_order"),
                track_key=(config or {}).get("_track_key"),
                brightness=_clamp_brightness(_brightness_for_color(color, config), config, True),
                rotation_offset=(config or {}).get("_rotation_offset", 0),
            )
            if success:
                gradient_diag["assignment_strategy"] = strategy
                gradient_diag["gradient_aware"] = True
                gradient_diag["gradient_detection_source"] = gradient_capability.source
                gradient_diag["gradient_capability"] = gradient_capability.as_dict()
                gradient_diag["apply_mode"] = "true_gradient"
                gradient_diag["apply_reason"] = "true_gradient"
                gradient_diag["rgb_color"] = list(color)
                sent.append(gradient_diag)
                _LAST_APPLIED[entity_id] = {
                    "rgb_color": list(color),
                    "brightness": _clamp_brightness(_brightness_for_color(color, config), config, gradient_aware),
                    "transition": transition,
                    "gradient": True,
                }
                continue

            skipped.append({
                "entity_id": entity_id,
                "reason": "true_gradient_fallback",
                "detail": gradient_diag.get("gradient_error") if gradient_diag else None,
                "gradient_detection_source": gradient_capability.source,
                "gradient_capability": gradient_capability.as_dict(),
            })

        service_data = build_service_data(state, color, transition, config=config, gradient_aware=gradient_aware)
        apply_needed, reason = should_apply(entity_id, service_data)

        diagnostic_data = dict(service_data)
        diagnostic_data["assignment_strategy"] = strategy
        diagnostic_data["gradient_aware"] = gradient_aware
        diagnostic_data["gradient_detection_source"] = gradient_capability.source
        diagnostic_data["gradient_capability"] = gradient_capability.as_dict()
        diagnostic_data["true_gradient_mode"] = true_gradient_enabled
        diagnostic_data["apply_mode"] = "standard_color_fallback" if gradient_diag else "standard_color"
        diagnostic_data["apply_reason"] = reason
        diagnostic_data["assignment_rotation_offset"] = int((config or {}).get("_rotation_offset", 0) or 0)
        if gradient_diag:
            diagnostic_data.update({
                key: value for key, value in gradient_diag.items()
                if key not in diagnostic_data
            })

        if not apply_needed:
            skipped.append({"entity_id": entity_id, "reason": "unchanged"})
            sent.append(diagnostic_data | {"skipped": True})
            continue

        pending_native.append((entity_id, service_data, diagnostic_data))

    if pending_native:
        async def _call_light_turn_on(entity_id: str, service_data: dict, diagnostic_data: dict):
            _LOGGER.debug("[apply] light.turn_on %s", service_data)
            await hass.services.async_call("light", "turn_on", service_data, blocking=True)
            _LAST_APPLIED[entity_id] = dict(service_data)
            return diagnostic_data

        results = await asyncio.gather(
            *[_call_light_turn_on(entity_id, data, diag) for entity_id, data, diag in pending_native],
            return_exceptions=True,
        )

        for (entity_id, _, diagnostic_data), result in zip(pending_native, results, strict=False):
            if isinstance(result, Exception):
                skipped.append({
                    "entity_id": entity_id,
                    "reason": "service_call_failed",
                    "detail": f"{type(result).__name__}: {result}",
                })
                diagnostic_data["apply_error"] = f"{type(result).__name__}: {result}"
                sent.append(diagnostic_data)
            else:
                sent.append(result)

    return sent, skipped

def clear_apply_cache():
    _LAST_APPLIED.clear()
