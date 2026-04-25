from __future__ import annotations

import logging
import random

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

GRADIENT_HINTS = ("gradient", "signe", "play gradient", "lightstrip plus gradient")

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
    order_mode: str = "same_order",
    entity_id: str | None = None,
    track_key: str | None = None,
) -> list[tuple[int, int, int]]:
    """Create ordered gradient points.

    Modes:
    - same_order: every gradient light receives the same color order.
    - rotated_by_light: each light starts from its assigned/base color.
    - random: deterministic random shuffle per track/light so it changes per track
      but does not reshuffle repeatedly during the same track.
    """
    point_count = max(2, min(5, int(point_count or 5)))

    base_palette = list(palette) if palette else [base_color]
    if not base_palette:
        base_palette = [base_color]

    # Ensure base color exists in the source palette.
    if base_color not in base_palette:
        base_palette.insert(0, base_color)

    if order_mode == "rotated_by_light":
        idx = base_palette.index(base_color) if base_color in base_palette else 0
        ordered = base_palette[idx:] + base_palette[:idx]
    elif order_mode == "random":
        ordered = list(base_palette)
        seed = f"{track_key or ''}|{entity_id or ''}|{base_color}"
        random.Random(seed).shuffle(ordered)
        # Keep the assigned color included and preferably visible.
        if base_color in ordered and ordered[0] == base_color and len(ordered) > 1:
            pass
    else:
        ordered = list(base_palette)

    return _repeat_to_count(ordered, point_count)

def _entity_looks_gradient(hass, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    haystack = " ".join(str(x or "").lower() for x in (
        entity_id,
        state.attributes.get("friendly_name") if state else "",
        entry.name if entry else "",
        entry.original_name if entry else "",
        entry.unique_id if entry else "",
        state.attributes.get("model") if state else "",
    ))
    effects = state.attributes.get("effect_list") if state else []
    if isinstance(effects, list):
        haystack += " " + " ".join(str(e).lower() for e in effects)
    return any(hint in haystack for hint in GRADIENT_HINTS)

def _walk_bridge_candidates(hass):
    """Find Home Assistant Hue bridge runtime objects.

    Modern Home Assistant stores the HueBridge object on the config entry's
    runtime_data. Older/alternate layouts may also expose bridge-ish objects in
    hass.data["hue"]. Return pairs of (bridge_or_owner, api).
    """
    results = []

    # Current HA path: ConfigEntry.runtime_data is HueBridge and has .api.
    try:
        for entry in hass.config_entries.async_entries("hue"):
            bridge = getattr(entry, "runtime_data", None)
            if bridge is not None and hasattr(bridge, "api"):
                results.append((bridge, bridge.api))
    except Exception:
        pass

    # Older/fallback discovery through hass.data.
    hue_data = hass.data.get("hue")
    if hue_data:
        values = hue_data.values() if isinstance(hue_data, dict) else [hue_data]
        for value in values:
            if value is None:
                continue
            if hasattr(value, "api"):
                results.append((value, getattr(value, "api")))
            if hasattr(value, "bridge") and hasattr(value.bridge, "api"):
                results.append((value.bridge, value.bridge.api))
            if isinstance(value, dict):
                for sub in value.values():
                    if hasattr(sub, "api"):
                        results.append((sub, sub.api))

    # Deduplicate by object id.
    seen = set()
    unique = []
    for bridge, api in results:
        key = (id(bridge), id(api))
        if key not in seen:
            seen.add(key)
            unique.append((bridge, api))

    return unique

def _iter_lights_controller(api):
    candidates = [
        getattr(api, "lights", None),
        getattr(getattr(api, "v2", None), "lights", None),
    ]
    return [controller for controller in candidates if controller is not None]

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

def _resource_gradient_info(resource):
    if isinstance(resource, dict):
        return resource.get("gradient")
    return getattr(resource, "gradient", None)

def _device_identifiers(hass, entity_id: str) -> list[str]:
    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entry = registry.async_get(entity_id)
    if not entry or not entry.device_id:
        return []
    device = device_registry.async_get(entry.device_id)
    if not device:
        return []

    values = []
    for domain, identifier in device.identifiers:
        values.append(str(identifier))
    for connection_type, connection_value in device.connections:
        values.append(str(connection_value))
    return values

def _match_hue_resource(hass, entity_id: str):
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    state = hass.states.get(entity_id)

    unique_id = str(entry.unique_id if entry and entry.unique_id else "")
    device_identifiers = _device_identifiers(hass, entity_id)
    friendly_name = str(state.attributes.get("friendly_name", "") if state else "")
    entity_fragments = [
        entity_id,
        unique_id,
        friendly_name,
        *device_identifiers,
    ]
    entity_fragments = [frag.casefold() for frag in entity_fragments if frag]

    attempted = []

    for bridge, api in _walk_bridge_candidates(hass):
        for controller in _iter_lights_controller(api):
            for resource in _controller_values(controller):
                rid = _resource_id(resource)
                rid_v1 = _resource_id_v1(resource)
                name = _resource_name(resource)

                resource_fragments = [
                    str(rid or ""),
                    str(rid_v1 or ""),
                    str(name or ""),
                ]
                resource_fragments = [frag.casefold() for frag in resource_fragments if frag]

                attempted.append(
                    {
                        "id": rid,
                        "id_v1": rid_v1,
                        "name": name,
                        "gradient": str(_resource_gradient_info(resource)),
                    }
                )

                # Strong direct matching.
                for resource_frag in resource_fragments:
                    for entity_frag in entity_fragments:
                        if resource_frag and resource_frag in entity_frag:
                            return bridge, controller, rid, resource, attempted
                        if entity_frag and entity_frag in resource_frag:
                            return bridge, controller, rid, resource, attempted

                # Friendly name matching with normalized punctuation.
                norm_entity_name = "".join(ch for ch in friendly_name.casefold() if ch.isalnum())
                norm_resource_name = "".join(ch for ch in name.casefold() if ch.isalnum())
                if norm_entity_name and norm_resource_name and norm_entity_name == norm_resource_name:
                    return bridge, controller, rid, resource, attempted

    return None, None, None, None, attempted

def _raw_gradient_payload(points: list[tuple[int, int, int]], transition_seconds: float):
    return {
        "on": {"on": True},
        "dimming": {"brightness": 100},
        "dynamics": {"duration": int(float(transition_seconds or 0) * 1000)},
        "gradient": {
            "points": [
                {"color": {"xy": {"x": rgb_to_xy(color)[0], "y": rgb_to_xy(color)[1]}}}
                for color in points
            ],
            "mode": "interpolated_palette",
        },
    }

def _model_gradient_payload(points: list[tuple[int, int, int]], transition_seconds: float):
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

async def _try_update(bridge, controller, resource_id: str, payload):
    # Prefer Home Assistant HueBridge wrapper when available because it applies
    # HA's expected error handling.
    if bridge is not None and hasattr(bridge, "async_request_call"):
        await bridge.async_request_call(controller.update, resource_id, payload)
    else:
        await controller.update(resource_id, payload)

async def try_apply_gradient(
    hass,
    entity_id: str,
    palette: list[tuple[int, int, int]],
    base_color: tuple[int, int, int],
    point_count: int,
    transition: float,
    order_mode: str = "same_order",
    track_key: str | None = None,
) -> tuple[bool, dict]:
    diagnostics = {
        "entity_id": entity_id,
        "gradient_requested": True,
        "gradient_applied": False,
    }

    bridge, controller, resource_id, resource, attempted = _match_hue_resource(hass, entity_id)

    if controller is None or not resource_id:
        diagnostics["gradient_error"] = "hue_resource_not_found"
        diagnostics["gradient_match_attempts"] = attempted[:20]
        diagnostics["hue_bridge_count"] = len(_walk_bridge_candidates(hass))
        _LOGGER.debug("[gradient] %s failed: %s", entity_id, diagnostics)
        return False, diagnostics

    gradient_info = _resource_gradient_info(resource)
    looks_gradient = _entity_looks_gradient(hass, entity_id)

    diagnostics["hue_resource_id"] = resource_id
    diagnostics["hue_resource_name"] = _resource_name(resource)
    diagnostics["hue_gradient_info"] = str(gradient_info)
    diagnostics["entity_looks_gradient"] = looks_gradient

    # Some HA/aiohue versions parse gradient data as invalid dicts. Do not block
    # attempts on parsed model quality when the entity itself looks like a
    # gradient device.
    if gradient_info is None and not looks_gradient:
        diagnostics["gradient_error"] = "resource_has_no_gradient_feature"
        _LOGGER.debug("[gradient] %s failed: %s", entity_id, diagnostics)
        return False, diagnostics

    points = gradient_palette_for_light(palette, base_color, point_count, order_mode=order_mode, entity_id=entity_id, track_key=track_key)
    diagnostics["gradient_colors"] = [list(color) for color in points]
    diagnostics["gradient_points"] = len(points)
    diagnostics["gradient_order_mode"] = order_mode

    errors = []

    payload_kind = "aiohue_model"
    try:
        payload = _model_gradient_payload(points, transition)
        await _try_update(bridge, controller, resource_id, payload)
        diagnostics["gradient_applied"] = True
        diagnostics["gradient_payload_kind"] = payload_kind
        _LOGGER.debug("[gradient] %s applied via %s", entity_id, payload_kind)
        return True, diagnostics
    except Exception as err:
        errors.append(f"{payload_kind}: {type(err).__name__}: {err}")
        _LOGGER.debug("[gradient] %s %s failed: %s", entity_id, payload_kind, err, exc_info=True)

    diagnostics["gradient_error"] = " | ".join(errors)
    return False, diagnostics
