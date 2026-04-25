from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

TO_REDACT = {
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "client_secret",
    "source_image",
    "last_track_key",
}

def _safe_state(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    state = hass.states.get(entity_id)
    if state is None:
        return {"entity_id": entity_id, "state": "missing"}

    attrs = dict(state.attributes)
    # Keep useful light capability diagnostics; redact only obvious volatile/sensitive fields.
    for key in list(attrs):
        if key in TO_REDACT:
            attrs[key] = "REDACTED"

    return {
        "entity_id": entity_id,
        "state": state.state,
        "attributes": attrs,
        "last_changed": state.last_changed.isoformat() if state.last_changed else None,
        "last_updated": state.last_updated.isoformat() if state.last_updated else None,
    }

def _entity_registry_info(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is None:
        return {"entity_id": entity_id, "registry_entry": None}

    return {
        "entity_id": entity_id,
        "unique_id": entry.unique_id,
        "platform": entry.platform,
        "device_id": entry.device_id,
        "area_id": entry.area_id,
        "original_name": entry.original_name,
        "name": entry.name,
        "disabled": bool(entry.disabled_by),
        "hidden": bool(entry.hidden_by),
    }

def _device_registry_info(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entry = entity_registry.async_get(entity_id)
    if entry is None or not entry.device_id:
        return {"entity_id": entity_id, "device": None}

    device = device_registry.async_get(entry.device_id)
    if device is None:
        return {"entity_id": entity_id, "device": None}

    return {
        "entity_id": entity_id,
        "device_id": entry.device_id,
        "name": device.name,
        "name_by_user": device.name_by_user,
        "manufacturer": device.manufacturer,
        "model": device.model,
        "model_id": device.model_id,
        "sw_version": device.sw_version,
        "hw_version": device.hw_version,
        "area_id": device.area_id,
        "identifiers": [list(item) for item in device.identifiers],
        "connections": [list(item) for item in device.connections],
    }

def _hue_bridge_summary(hass: HomeAssistant) -> dict[str, Any]:
    bridges = []
    try:
        entries = hass.config_entries.async_entries("hue")
    except Exception as err:
        return {"error": f"{type(err).__name__}: {err}", "bridges": []}

    for entry in entries:
        runtime_data = getattr(entry, "runtime_data", None)
        api = getattr(runtime_data, "api", None) if runtime_data is not None else None
        lights_controller = None
        light_count = None

        if api is not None:
            lights_controller = getattr(api, "lights", None) or getattr(getattr(api, "v2", None), "lights", None)
            if lights_controller is not None:
                for attr in ("values", "items"):
                    method = getattr(lights_controller, attr, None)
                    if callable(method):
                        try:
                            values = list(method())
                            if attr == "items":
                                values = [item[1] for item in values]
                            light_count = len(values)
                            break
                        except Exception:
                            pass
                if light_count is None:
                    data = getattr(lights_controller, "data", None) or getattr(lights_controller, "_data", None)
                    if isinstance(data, dict):
                        light_count = len(data)

        bridges.append(
            {
                "entry_id": entry.entry_id,
                "title": entry.title,
                "state": str(entry.state),
                "has_runtime_data": runtime_data is not None,
                "runtime_type": type(runtime_data).__name__ if runtime_data is not None else None,
                "has_api": api is not None,
                "api_type": type(api).__name__ if api is not None else None,
                "lights_controller_type": type(lights_controller).__name__ if lights_controller is not None else None,
                "light_count_visible_to_runtime": light_count,
            }
        )

    return {"bridge_count": len(bridges), "bridges": bridges}

def _coordinator_snapshot(coordinator) -> dict[str, Any]:
    keys = [
        "enabled",
        "sonos_entity",
        "light_entities",
        "group_entities",
        "member_light_entities",
        "expansion_entities",
        "last_resolved_lights",
        "last_resolver_source",
        "last_resolver_source_map",
        "last_skipped_lights",
        "last_service_data",
        "last_error",
        "last_palette_error",
        "last_image_fetch_status",
        "last_image_fetch_candidates",
        "last_artwork_fallback_mode",
        "last_artwork_fallback_applied",
        "last_processing_reason",
        "runtime_assignment_strategy",
        "runtime_options",
        "last_palette",
        "last_timings",
        "last_cache_result",
        "last_restore_result",
        "last_restore_snapshot_count",
        "last_health_report",
    ]

    out = {}
    for key in keys:
        if hasattr(coordinator, key):
            out[key] = deepcopy(getattr(coordinator, key))

    try:
        out["config"] = deepcopy(coordinator.config)
    except Exception:
        out["config"] = {}

    return out

async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    selected_entities = []
    resolved_entities = []
    expansion_entities = []

    if coordinator is not None:
        selected_entities = list(getattr(coordinator, "light_entities", []) or [])
        selected_entities += list(getattr(coordinator, "group_entities", []) or [])
        selected_entities += list(getattr(coordinator, "member_light_entities", []) or [])
        expansion_entities = list(getattr(coordinator, "expansion_entities", []) or [])
        resolved_entities = list(getattr(coordinator, "last_resolved_lights", []) or [])

    entity_ids = []
    for entity_id in selected_entities + expansion_entities + resolved_entities:
        if entity_id and entity_id not in entity_ids:
            entity_ids.append(entity_id)

    data = {
        "integration": {
            "domain": DOMAIN,
            "entry_id": entry.entry_id,
            "title": entry.title,
            "version": "2.3.3",
        },
        "config_entry": {
            "data": deepcopy(dict(entry.data)),
            "options": deepcopy(dict(entry.options)),
        },
        "home_assistant": {
            "version": getattr(hass, "config", None) and getattr(hass.config, "version", None),
            "config_dir": "REDACTED",
        },
        "coordinator": _coordinator_snapshot(coordinator) if coordinator is not None else None,
        "hue": _hue_bridge_summary(hass),
        "entities": {
            entity_id: {
                "state": _safe_state(hass, entity_id),
                "entity_registry": _entity_registry_info(hass, entity_id),
                "device_registry": _device_registry_info(hass, entity_id),
            }
            for entity_id in entity_ids
        },
    }

    # Add Status/Targets entities by device if discoverable.
    try:
        registry = er.async_get(hass)
        for reg_entry in registry.entities.values():
            if reg_entry.platform == DOMAIN:
                entity_id = reg_entry.entity_id
                if entity_id not in data["entities"]:
                    data["entities"][entity_id] = {
                        "state": _safe_state(hass, entity_id),
                        "entity_registry": _entity_registry_info(hass, entity_id),
                        "device_registry": _device_registry_info(hass, entity_id),
                    }
    except Exception:
        pass

    return async_redact_data(data, TO_REDACT)
