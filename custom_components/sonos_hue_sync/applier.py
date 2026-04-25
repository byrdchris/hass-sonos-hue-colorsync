from __future__ import annotations

import logging

from .assignment import is_gradient_entity
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

def _brightness_for_color(color: tuple[int, int, int]) -> int:
    return int(50 + luminance(color) * 205)

def build_service_data(state, color: tuple[int, int, int], transition: float) -> dict:
    brightness = _brightness_for_color(color)
    data = {"entity_id": state.entity_id, "brightness": brightness, "transition": transition}

    # Prefer rgb_color for Hue xy/rgb/hs lights. Avoid color_temp service keys
    # because some HA versions reject that key in light.turn_on validation.
    if any(_supports(state, mode) for mode in ("rgb", "xy", "hs", "rgbw", "rgbww", "color_temp")):
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
    sent: list[dict] = []
    skipped: list[dict] = []

    for entity_id, color in assignments.items():
        state = hass.states.get(entity_id)
        if state is None:
            skipped.append({"entity_id": entity_id, "reason": "missing_at_apply"})
            continue
        if state.state in ("unavailable", "unknown"):
            skipped.append({"entity_id": entity_id, "reason": f"{state.state}_at_apply"})
            continue

        gradient_aware = is_gradient_entity(hass, entity_id)
        true_gradient_enabled = bool((config or {}).get("true_gradient_mode", False))

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
            )
            if success:
                gradient_diag["assignment_strategy"] = strategy
                gradient_diag["gradient_aware"] = True
                gradient_diag["apply_reason"] = "true_gradient"
                gradient_diag["rgb_color"] = list(color)
                sent.append(gradient_diag)
                # Prevent immediate HA-native duplicate apply on the same target.
                _LAST_APPLIED[entity_id] = {
                    "rgb_color": list(color),
                    "brightness": _brightness_for_color(color),
                    "transition": transition,
                    "gradient": True,
                }
                continue

            # If direct Hue gradient failed, fall back to HA-native single color.
            skipped.append({
                "entity_id": entity_id,
                "reason": "true_gradient_fallback",
                "detail": gradient_diag.get("gradient_error"),
            })

        service_data = build_service_data(state, color, transition)
        apply_needed, reason = should_apply(entity_id, service_data)

        diagnostic_data = dict(service_data)
        diagnostic_data["assignment_strategy"] = strategy
        diagnostic_data["gradient_aware"] = gradient_aware
        diagnostic_data["true_gradient_mode"] = true_gradient_enabled
        diagnostic_data["apply_reason"] = reason
        if true_gradient_enabled and gradient_aware and "gradient_diag" in locals():
            diagnostic_data.update({
                key: value for key, value in gradient_diag.items()
                if key not in diagnostic_data
            })

        if not apply_needed:
            skipped.append({"entity_id": entity_id, "reason": "unchanged"})
            sent.append(diagnostic_data | {"skipped": True})
            continue

        _LOGGER.debug("[apply] light.turn_on %s", service_data)
        await hass.services.async_call("light", "turn_on", service_data, blocking=True)

        _LAST_APPLIED[entity_id] = dict(service_data)
        sent.append(diagnostic_data)

    return sent, skipped

def clear_apply_cache():
    _LAST_APPLIED.clear()
