from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass

from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

def rgb_to_xy(rgb: tuple[int, int, int]) -> tuple[float, float]:
    """Approximate sRGB to CIE 1931 xy conversion."""
    r, g, b = [x / 255 for x in rgb]

    def gamma(v: float) -> float:
        return ((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92

    r, g, b = gamma(r), gamma(g), gamma(b)

    x = r * 0.664511 + g * 0.154324 + b * 0.162028
    y = r * 0.283881 + g * 0.668433 + b * 0.047685
    z = r * 0.000088 + g * 0.072310 + b * 0.986039

    total = x + y + z
    if total == 0:
        return 0.3227, 0.3290

    return round(x / total, 4), round(y / total, 4)

def _repeat_to_count(colors: list[tuple[int, int, int]], count: int) -> list[tuple[int, int, int]]:
    if not colors:
        return [(255, 255, 255)] * count
    return [colors[idx % len(colors)] for idx in range(count)]

def gradient_palette_for_light(
    palette: list[tuple[int, int, int]],
    base_color: tuple[int, int, int],
    point_count: int,
) -> list[tuple[int, int, int]]:
    """Create ordered gradient points.

    Keep the assigned color as the first point so gradient behavior remains
    consistent with the selected assignment strategy, then fill with other
    palette colors.
    """
    point_count = max(2, min(5, int(point_count or 5)))

    ordered = [base_color]
    for color in palette:
        if color not in ordered:
            ordered.append(color)

    return _repeat_to_count(ordered, point_count)

def _walk_bridge_candidates(hass):
    hue_data = hass.data.get("hue")
    if not hue_data:
        return

    if isinstance(hue_data, dict):
        values = hue_data.values()
    else:
        values = [hue_data]

    for value in values:
        if value is None:
            continue
        if hasattr(value, "api"):
            yield value, getattr(value, "api")
        if hasattr(value, "bridge") and hasattr(value.bridge, "api"):
            yield value.bridge, value.bridge.api
        if isinstance(value, dict):
            for sub in value.values():
                if hasattr(sub, "api"):
                    yield sub, sub.api

def _iter_lights_controller(api):
    candidates = [
        getattr(api, "lights", None),
        getattr(getattr(api, "v2", None), "lights", None),
    ]
    for controller in candidates:
        if controller is not None:
            yield controller

def _controller_values(controller):
    for attr in ("values", "items"):
        obj = getattr(controller, attr, None)
        if callable(obj):
            try:
                values = obj()
                if attr == "items":
                    values = [item[1] for item in values]
                return list(values)
            except Exception:
                pass

    for attr in ("data", "_data", "items"):
        data = getattr(controller, attr, None)
        if isinstance(data, dict):
            return list(data.values())

    try:
        return list(controller)
    except Exception:
        return []

def _resource_name(resource) -> str:
    metadata = getattr(resource, "metadata", None)
    if metadata is not None:
        return str(getattr(metadata, "name", "") or "")
    if isinstance(resource, dict):
        metadata = resource.get("metadata") or {}
        return str(metadata.get("name", ""))
    return ""

def _resource_id(resource) -> str | None:
    if isinstance(resource, dict):
        return resource.get("id")
    return getattr(resource, "id", None)

def _resource_id_v1(resource) -> str | None:
    if isinstance(resource, dict):
        return resource.get("id_v1")
    return getattr(resource, "id_v1", None)

def _resource_supports_gradient(resource) -> bool:
    if isinstance(resource, dict):
        return bool(resource.get("gradient"))
    return getattr(resource, "gradient", None) is not None

def _match_hue_resource(hass, entity_id: str):
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    state = hass.states.get(entity_id)

    unique_id = str(entry.unique_id if entry and entry.unique_id else "")
    friendly_name = str(state.attributes.get("friendly_name", "") if state else "")

    for _bridge, api in _walk_bridge_candidates(hass) or []:
        for controller in _iter_lights_controller(api):
            for resource in _controller_values(controller):
                rid = _resource_id(resource)
                rid_v1 = _resource_id_v1(resource)
                name = _resource_name(resource)

                candidates = [str(x) for x in (rid, rid_v1) if x]
                if any(candidate and candidate in unique_id for candidate in candidates):
                    return controller, rid, resource

                if friendly_name and name and friendly_name.casefold() == name.casefold():
                    return controller, rid, resource

    return None, None, None

def _build_light_put(points: list[tuple[int, int, int]], transition_seconds: float):
    from aiohue.v2.models.feature import (
        ColorFeaturePut,
        ColorPoint,
        DimmingFeaturePut,
        DynamicsFeaturePut,
        GradientFeatureBase,
        GradientPoint,
        OnFeature,
    )
    from aiohue.v2.models.light import LightPut

    update = LightPut()
    update.on = OnFeature(on=True)
    update.dimming = DimmingFeaturePut(brightness=100)
    update.dynamics = DynamicsFeaturePut(duration=int(float(transition_seconds or 0) * 1000))
    update.gradient = GradientFeatureBase(
        points=[
            GradientPoint(color=ColorFeaturePut(xy=ColorPoint(*rgb_to_xy(color))))
            for color in points
        ]
    )
    return update

async def try_apply_gradient(
    hass,
    entity_id: str,
    palette: list[tuple[int, int, int]],
    base_color: tuple[int, int, int],
    point_count: int,
    transition: float,
) -> tuple[bool, dict]:
    """Try to apply true Hue gradient through HA's existing aiohue bridge.

    Returns (success, diagnostics). Failure is expected on unsupported lights or
    if Home Assistant internals differ; caller should fall back to HA-native.
    """
    diagnostics = {
        "entity_id": entity_id,
        "gradient_requested": True,
        "gradient_applied": False,
    }

    try:
        controller, resource_id, resource = _match_hue_resource(hass, entity_id)
        if controller is None or not resource_id:
            diagnostics["gradient_error"] = "hue_resource_not_found"
            return False, diagnostics

        if not _resource_supports_gradient(resource):
            diagnostics["gradient_error"] = "resource_has_no_gradient_feature"
            return False, diagnostics

        points = gradient_palette_for_light(palette, base_color, point_count)
        update = _build_light_put(points, transition)

        await controller.update(resource_id, update)

        diagnostics.update(
            {
                "gradient_applied": True,
                "hue_resource_id": resource_id,
                "gradient_colors": [list(color) for color in points],
                "gradient_points": len(points),
            }
        )
        return True, diagnostics

    except Exception as err:
        _LOGGER.debug("[gradient] failed for %s: %s", entity_id, err, exc_info=True)
        diagnostics["gradient_error"] = f"{type(err).__name__}: {err}"
        return False, diagnostics
