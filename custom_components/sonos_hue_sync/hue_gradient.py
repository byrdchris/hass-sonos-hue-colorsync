from __future__ import annotations

# Gradient support. Detects gradient-capable lights and builds native Hue gradient payloads with standard-light fallback.
# brief-code-commented-build: moderate block-level comments added for maintainability.

import logging
import random

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .hue_capabilities import gradient_capability_from_ha

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

def _linear_channel(value: int) -> float:
    """Convert an sRGB channel into linear light for perceptual luminance sorting."""
    channel = max(0, min(255, int(value))) / 255
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4

def _perceived_luminance(color: tuple[int, int, int]) -> float:
    """Return gamma-corrected relative luminance for visual dark/light ordering."""
    # Use WCAG/Rec. 709 coefficients on linearized sRGB channels so red, green,
    # and blue sort closer to how they appear to the eye than a raw RGB average.
    r, g, b = color
    return (0.2126 * _linear_channel(r)) + (0.7152 * _linear_channel(g)) + (0.0722 * _linear_channel(b))

def _gradient_sort_key(color: tuple[int, int, int]) -> tuple[float, float]:
    """Sort by luminance, then saturation, for stable visual ramps."""
    # Saturation is a deterministic tie-breaker when two colors have similar
    # luminance but one reads as a stronger gradient point.
    r, g, b = [max(0, min(255, int(v))) / 255 for v in color]
    mx = max(r, g, b)
    mn = min(r, g, b)
    saturation = 0 if mx == 0 else (mx - mn) / mx
    return (_perceived_luminance(color), saturation)

def _dedupe_colors(colors: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """Keep palette order while removing exact duplicate RGB entries."""
    output: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for color in colors:
        rgb = tuple(int(v) for v in color)
        if rgb not in seen:
            seen.add(rgb)
            output.append(rgb)
    return output

def _select_luminance_spread(colors: list[tuple[int, int, int]], count: int) -> list[tuple[int, int, int]]:
    """Select colors spaced across the luminance range before final ordering."""
    # For low detail levels, especially two-point gradients, choose meaningful
    # dark/light anchors instead of simply taking the first N palette colors.
    unique = _dedupe_colors(colors)
    if len(unique) <= count:
        return unique

    ranked = sorted(unique, key=_gradient_sort_key)
    if count <= 2:
        return [ranked[0], ranked[-1]]

    selected: list[tuple[int, int, int]] = []
    last_index = len(ranked) - 1
    for idx in range(count):
        source_index = round((idx / (count - 1)) * last_index)
        color = ranked[source_index]
        if color not in selected:
            selected.append(color)

    # Fill any gaps caused by rounding collisions with the widest remaining
    # luminance candidates. This keeps the requested detail count when possible.
    if len(selected) < count:
        for color in ranked:
            if color not in selected:
                selected.append(color)
            if len(selected) >= count:
                break

    return selected[:count]

def _locked_ordered_gradient_points(
    colors: list[tuple[int, int, int]],
    point_count: int,
    order_mode: str,
) -> list[tuple[int, int, int]]:
    """Apply explicit gradient direction without adaptive anchor reselection.

    Auto Artwork Style may change the extracted palette, but an explicit
    dark/light gradient pattern is a layout choice. Keep the chosen palette
    anchors stable and only perform the final luminance ordering here.
    """
    unique = _dedupe_colors(colors)
    if not unique:
        unique = [(255, 255, 255)]

    # Use the full final palette for explicit ramps so the selected artwork
    # style cannot leave the gradient with only the first few assignment colors.
    # The user-selected direction is then applied as the final authoritative step.
    selected = _select_luminance_spread(unique, point_count)
    if len(selected) < point_count:
        selected = _repeat_to_count(selected, point_count)

    reverse = order_mode == "light_to_dark"
    return sorted(selected[:point_count], key=_gradient_sort_key, reverse=reverse)

def _ordered_gradient_points(
    colors: list[tuple[int, int, int]],
    point_count: int,
    order_mode: str,
) -> list[tuple[int, int, int]]:
    """Apply the final gradient ordering after selection and optional rotation."""
    if order_mode in ("dark_to_light", "light_to_dark"):
        return _locked_ordered_gradient_points(colors, point_count, order_mode)
    return _repeat_to_count(colors, point_count)

def gradient_palette_for_light(
    palette: list[tuple[int, int, int]],
    base_color: tuple[int, int, int],
    point_count: int,
    order_mode: str = "same_order",
    entity_id: str | None = None,
    track_key: str | None = None,
    rotation_offset: int = 0,
) -> list[tuple[int, int, int]]:
    """Create ordered gradient points.

    Ordered gradient modes are authoritative: dark-to-light and light-to-dark
    select perceptually spaced colors and apply their luminance sort as the
    final step, so detail changes and rotation cannot reverse the ramp.
    """
    point_count = max(2, min(5, int(point_count or 5)))

    base_palette = list(palette) if palette else [base_color]
    if not base_palette:
        base_palette = [base_color]

    # Explicit ramp modes are layout choices. Do not insert the per-light base
    # color before ordering, because that can make style changes appear to break
    # dark-to-light or light-to-dark direction.
    if order_mode in ("dark_to_light", "light_to_dark"):
        return _ordered_gradient_points(base_palette, point_count, order_mode)

    # Ensure base color exists in the source palette for offset/random modes.
    if base_color not in base_palette:
        base_palette.insert(0, base_color)

    if order_mode == "rotated_by_light":
        idx = base_palette.index(base_color) if base_color in base_palette else 0
        ordered = base_palette[idx:] + base_palette[:idx]
    elif order_mode == "random":
        ordered = list(base_palette)
        seed = f"{track_key or ''}|{entity_id or ''}|{base_color}"
        random.Random(seed).shuffle(ordered)
    else:
        ordered = list(base_palette)

    points = _repeat_to_count(ordered, point_count)
    if rotation_offset and len(points) > 1:
        rotation_offset = int(rotation_offset) % len(points)
        points = points[rotation_offset:] + points[:rotation_offset]
    return points

def _entity_looks_gradient(hass, entity_id: str) -> bool:
    return gradient_capability_from_ha(hass, entity_id).capable

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

def _is_near_white(color: tuple[int, int, int]) -> bool:
    # Guard against Hue exposing a default white representative color for
    # gradient lights when the active album palette contains no white.
    return min(color) >= 235 and (max(color) - min(color)) <= 24

def _gradient_representative_color(points: list[tuple[int, int, int]], order_mode: str) -> tuple[int, int, int]:
    """Choose a non-white base color to pair with the native gradient payload.

    Hue exposes one representative color for a gradient light. If only the
    gradient points are sent, some bridge/HA combinations report or retain a
    near-white representative even when the gradient itself has no white. Keep
    this representative anchored to the final gradient palette.
    """
    usable = [tuple(color) for color in points if not _is_near_white(tuple(color))]
    source = usable or [tuple(color) for color in points] or [(255, 255, 255)]
    ordered = sorted(source, key=_gradient_sort_key)
    if order_mode == "light_to_dark":
        return ordered[-1]
    if order_mode == "dark_to_light":
        return ordered[0]
    return ordered[len(ordered) // 2]

def _raw_gradient_payload(points: list[tuple[int, int, int]], transition_seconds: float, brightness: int = 255, representative_color: tuple[int, int, int] | None = None):
    representative_xy = rgb_to_xy(representative_color or _gradient_representative_color(points, "same_order"))
    return {
        "on": {"on": True},
        "dimming": {"brightness": max(1, min(100, int((brightness / 255) * 100)))},
        "dynamics": {"duration": int(float(transition_seconds or 0) * 1000)},
        "color": {"xy": {"x": representative_xy[0], "y": representative_xy[1]}},
        "gradient": {
            "points": [
                {"color": {"xy": {"x": rgb_to_xy(color)[0], "y": rgb_to_xy(color)[1]}}}
                for color in points
            ],
            "mode": "interpolated_palette",
        },
    }

def _model_gradient_payload(points: list[tuple[int, int, int]], transition_seconds: float, brightness: int = 255, representative_color: tuple[int, int, int] | None = None):
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
    update.dimming = DimmingFeaturePut(brightness=max(1, min(100, int((brightness / 255) * 100))))
    update.dynamics = DynamicsFeaturePut(duration=int(float(transition_seconds or 0) * 1000))
    representative = representative_color or _gradient_representative_color(points, "same_order")
    # Set the Hue light's representative/base color alongside the gradient.
    # This prevents Home Assistant from showing or retaining white when the
    # actual album palette contains no white.
    try:
        update.color = ColorFeaturePut(xy=ColorPoint(*rgb_to_xy(representative)))
    except Exception:
        pass
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
    brightness: int = 255,
    rotation_offset: int = 0,
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
    capability = gradient_capability_from_ha(hass, entity_id, gradient_info)

    diagnostics["hue_resource_id"] = resource_id
    diagnostics["hue_resource_name"] = _resource_name(resource)
    diagnostics["hue_gradient_info"] = str(gradient_info)
    diagnostics["gradient_capability"] = capability.as_dict()
    diagnostics["entity_looks_gradient"] = capability.capable
    diagnostics["gradient_detection_source"] = capability.source

    # Some HA/aiohue versions parse gradient data as invalid or incomplete
    # objects. Do not block attempts when the device registry model ID or a
    # strong product-name hint indicates a known Hue gradient product.
    if not capability.capable:
        diagnostics["gradient_error"] = "resource_has_no_gradient_feature"
        _LOGGER.debug("[gradient] %s failed: %s", entity_id, diagnostics)
        return False, diagnostics

    points = gradient_palette_for_light(palette, base_color, point_count, order_mode=order_mode, entity_id=entity_id, track_key=track_key, rotation_offset=rotation_offset)
    ordered_mode = order_mode in ("dark_to_light", "light_to_dark")
    effective_rotation_offset = 0 if ordered_mode else int(rotation_offset or 0)
    representative_color = _gradient_representative_color(points, order_mode)
    diagnostics["gradient_colors"] = [list(color) for color in points]
    diagnostics["gradient_points"] = len(points)
    diagnostics["gradient_order_mode"] = order_mode
    diagnostics["gradient_representative_color"] = list(representative_color)
    diagnostics["gradient_representative_color_source"] = "final_gradient_palette"
    diagnostics["gradient_representative_white_suppressed"] = bool(not _is_near_white(representative_color))
    diagnostics["gradient_rotation_offset"] = effective_rotation_offset
    diagnostics["gradient_rotation_suppressed"] = bool(ordered_mode)
    diagnostics["gradient_luminance_values"] = [round(_perceived_luminance(color), 6) for color in points]
    diagnostics["gradient_sort_basis"] = "gamma_corrected_relative_luminance"
    diagnostics["gradient_detail_selection"] = "ordered_luminance_spread" if ordered_mode else "palette_order"
    diagnostics["gradient_order_lock"] = bool(ordered_mode)
    diagnostics["gradient_order_lock_reason"] = "explicit_gradient_pattern" if ordered_mode else None
    diagnostics["gradient_brightness"] = brightness

    errors = []

    payload_kind = "aiohue_model"
    try:
        payload = _model_gradient_payload(points, transition, brightness=brightness, representative_color=representative_color)
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
