from __future__ import annotations

from typing import Any
from homeassistant.core import HomeAssistant

from .hue_capabilities import gradient_capability_from_ha

def hue_bridge_summary(hass: HomeAssistant) -> dict[str, Any]:
    bridges = []
    try:
        entries = hass.config_entries.async_entries("hue")
    except Exception as err:
        return {"ok": False, "error": f"{type(err).__name__}: {err}", "bridge_count": 0, "bridges": []}

    for entry in entries:
        runtime_data = getattr(entry, "runtime_data", None)
        api = getattr(runtime_data, "api", None) if runtime_data is not None else None
        bridges.append({
            "title": entry.title,
            "state": str(entry.state),
            "has_runtime_data": runtime_data is not None,
            "has_api": api is not None,
            "api_type": type(api).__name__ if api is not None else None,
        })

    return {"ok": any(b["has_api"] for b in bridges), "bridge_count": len(bridges), "bridges": bridges}

def _exists(hass: HomeAssistant, entity_id: str | None) -> bool:
    return bool(entity_id and hass.states.get(entity_id) is not None)

def _capabilities(hass: HomeAssistant, entity_ids: list[str]) -> dict[str, Any]:
    missing, unavailable, gradient_like, color_capable = [], [], [], []
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state is None:
            missing.append(entity_id)
            continue
        if state.state in ("unknown", "unavailable"):
            unavailable.append(entity_id)
        attrs = state.attributes
        gradient_capability = gradient_capability_from_ha(hass, entity_id)
        if gradient_capability.capable:
            gradient_like.append({
                "entity_id": entity_id,
                "source": gradient_capability.source,
                "model": gradient_capability.model,
                "model_id": gradient_capability.model_id,
            })
        modes = attrs.get("supported_color_modes") or []
        if any(mode in modes for mode in ("xy", "rgb", "hs")):
            color_capable.append(entity_id)
    return {
        "selected_count": len(entity_ids),
        "missing": missing,
        "unavailable": unavailable,
        "gradient_like": gradient_like,
        "color_capable": color_capable,
        "all_exist": not missing,
        "all_available": not unavailable,
    }

def build_health_report(hass: HomeAssistant, coordinator) -> dict[str, Any]:
    config = getattr(coordinator, "config", {}) if coordinator else {}
    selected = []
    for key in ("light_entities", "group_entities", "member_light_entities"):
        selected.extend(list(config.get(key, []) or []))
    resolved = list(getattr(coordinator, "last_resolved_lights", []) or [])
    service_data = list(getattr(coordinator, "last_service_data", []) or [])
    skipped = list(getattr(coordinator, "last_skipped_lights", []) or [])
    gradient_requested = [x for x in service_data if x.get("gradient_requested")]
    gradient_success = [x for x in gradient_requested if x.get("gradient_applied")]
    gradient_fallback = [x for x in skipped if x.get("reason") == "true_gradient_fallback"]
    sonos_entity = config.get("sonos_entity")
    sonos_state = hass.states.get(sonos_entity) if sonos_entity else None
    caps = _capabilities(hass, selected + resolved)
    hue = hue_bridge_summary(hass)
    last_error = getattr(coordinator, "last_error", None) if coordinator else None

    checks = {
        "integration_loaded": coordinator is not None,
        "sync_enabled": bool(getattr(coordinator, "enabled", False)) if coordinator else False,
        "sonos_entity_exists": _exists(hass, sonos_entity),
        "sonos_state": sonos_state.state if sonos_state else None,
        "selected_targets_exist": caps["all_exist"],
        "selected_targets_available": caps["all_available"],
        "resolved_any_lights": len(resolved) > 0,
        "last_run_had_error": bool(last_error),
        "hue_bridge_reachable": hue["ok"],
        "true_gradient_enabled": bool(config.get("true_gradient_mode", False)),
        "gradient_success_count": len(gradient_success),
        "gradient_fallback_count": len(gradient_fallback),
    }

    severity = "ok"
    if last_error or not checks["hue_bridge_reachable"] or not checks["selected_targets_exist"]:
        severity = "error"
    elif skipped or gradient_fallback or not checks["resolved_any_lights"]:
        severity = "warning"

    return {
        "severity": severity,
        "checks": checks,
        "hue": hue,
        "sonos": {
            "entity_id": sonos_entity,
            "exists": checks["sonos_entity_exists"],
            "state": checks["sonos_state"],
            "media_title": sonos_state.attributes.get("media_title") if sonos_state else None,
            "media_artist": sonos_state.attributes.get("media_artist") if sonos_state else None,
        },
        "targets": {
            "selected": selected,
            "resolved": resolved,
            "resolver_source": getattr(coordinator, "last_resolver_source", None) if coordinator else None,
            "resolver_source_map": getattr(coordinator, "last_resolver_source_map", {}) if coordinator else {},
            "capabilities": caps,
        },
        "processing": {
            "last_error": last_error,
            "last_processing_reason": getattr(coordinator, "last_processing_reason", None) if coordinator else None,
            "last_palette_count": len(getattr(coordinator, "last_palette", []) or []) if coordinator else 0,
            "runtime_options": getattr(coordinator, "runtime_options", {}) if coordinator else {},
            "timings": getattr(coordinator, "last_timings", {}) if coordinator else {},
            "cache_result": getattr(coordinator, "last_cache_result", None) if coordinator else None,
            "restore_last_result": getattr(coordinator, "last_restore_result", None) if coordinator else None,
            "restore_snapshot_count": getattr(coordinator, "last_restore_snapshot_count", 0) if coordinator else 0,
        },
        "gradient": {
            "enabled": bool(config.get("true_gradient_mode", False)),
            "detail_level": config.get("gradient_color_points"),
            "pattern": config.get("gradient_order_mode"),
            "requested_count": len(gradient_requested),
            "success_count": len(gradient_success),
            "fallback_count": len(gradient_fallback),
            "last_gradient_entities": [x.get("entity_id") for x in gradient_requested],
        },
        "skipped_lights": skipped,
    }

def format_health_message(report: dict[str, Any]) -> str:
    checks = report.get("checks", {})
    gradient = report.get("gradient", {})
    targets = report.get("targets", {})
    processing = report.get("processing", {})
    mark = lambda v: "✅" if v else "⚠️"
    return f"""## Sonos Hue Sync Health Check

### Overall
- Status: **{report.get("severity", "unknown").upper()}**
- Sync enabled: {mark(checks.get("sync_enabled"))}
- Hue bridge reachable: {mark(checks.get("hue_bridge_reachable"))}
- Sonos entity found: {mark(checks.get("sonos_entity_exists"))}
- Selected targets exist: {mark(checks.get("selected_targets_exist"))}
- Resolved lights: **{len(targets.get("resolved", []))}**

### Gradient
- True Gradient enabled: **{gradient.get("enabled")}**
- Gradient pattern: **{gradient.get("pattern")}**
- Gradient successes: **{gradient.get("success_count")}**
- Gradient fallbacks: **{gradient.get("fallback_count")}**

### Last run
- Last processing reason: **{processing.get("last_processing_reason")}**
- Last error: **{processing.get("last_error")}**
- Cache result: **{processing.get("cache_result")}**
- Timings: `{processing.get("timings")}`

### Next troubleshooting step
If anything is marked with a warning, use:

**Settings → Devices & services → Sonos Hue Sync → three-dot menu → Download diagnostics**
"""
