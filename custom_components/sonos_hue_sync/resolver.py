from __future__ import annotations

import logging
from dataclasses import dataclass, field

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

COLOR_MODES = ("rgb", "xy", "hs", "rgbw", "rgbww", "color_temp")
GROUP_UNIQUE_ID_TOKENS = ("grouped_light", "grouped-light", "group", "room", "zone")

_LAST_GROUP_MEMBERS: dict[str, list[str]] = {}

@dataclass
class ResolveResult:
    lights: list[str]
    source: str
    skipped: list[dict] = field(default_factory=list)
    source_map: dict[str, str] = field(default_factory=dict)
    group_diagnostics: dict = field(default_factory=dict)

def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out

def _entry_area_id(hass, entry) -> str | None:
    if entry is None:
        return None
    if entry.area_id:
        return entry.area_id
    device_registry = dr.async_get(hass)
    if entry.device_id:
        device = device_registry.async_get(entry.device_id)
        if device and device.area_id:
            return device.area_id
    return None

def _supports_any_color(state) -> bool:
    modes = state.attributes.get("supported_color_modes") or []
    return any(mode in modes for mode in COLOR_MODES)

def _unique_id_looks_grouped(entry) -> bool:
    if entry is None or not entry.unique_id:
        return False
    unique_id = entry.unique_id.lower()
    return any(token in unique_id for token in GROUP_UNIQUE_ID_TOKENS)

def is_group_entity(hass, entity_id: str) -> bool:
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    state = hass.states.get(entity_id)
    if state is None:
        return False
    if state.attributes.get("is_hue_group") is True:
        return True
    if state.attributes.get("hue_type") in ("room", "zone", "group"):
        return True
    members = state.attributes.get("entity_id")
    if isinstance(members, list) and members:
        return True
    return bool(entry and entry.platform == "hue" and _unique_id_looks_grouped(entry))

def direct_member_lights(hass, entity_id: str, diagnostics: dict | None = None) -> list[str]:
    """Use direct members exactly as Home Assistant exposes them.

    Hue room/zone entities commonly expose the real member lights in their
    ``entity_id`` attribute. That list is more authoritative than registry area
    fallback and should be preferred whenever present.
    """
    state = hass.states.get(entity_id)
    if state is None:
        if diagnostics is not None:
            diagnostics[entity_id] = {
                "member_source": "selected_missing",
                "declared_members": [],
                "resolved_members": [],
                "missing_members": [],
                "skipped_members": [{"entity_id": entity_id, "reason": "selected_missing"}],
            }
        return []

    members = state.attributes.get("entity_id")
    if not isinstance(members, (list, tuple, set)) or not members:
        if diagnostics is not None:
            diagnostics[entity_id] = {
                "member_source": "no_entity_id_attribute",
                "declared_members": [],
                "resolved_members": [],
                "missing_members": [],
                "skipped_members": [],
            }
        return []

    declared = list(members)
    resolved: list[str] = []
    missing: list[str] = []
    skipped: list[dict] = []

    for member in declared:
        member_state = hass.states.get(member)
        if member_state is None:
            missing.append(member)
            skipped.append({"entity_id": member, "reason": "member_missing"})
            continue

        nested = member_state.attributes.get("entity_id")
        if isinstance(nested, (list, tuple, set)) and nested:
            resolved.extend(list(nested))
        else:
            resolved.append(member)

    resolved = _unique(resolved)
    if resolved:
        _LAST_GROUP_MEMBERS[entity_id] = resolved

    if diagnostics is not None:
        diagnostics[entity_id] = {
            "member_source": "entity_id_attribute",
            "declared_members": declared,
            "resolved_members": resolved,
            "missing_members": missing,
            "skipped_members": skipped,
        }

    return resolved

def _find_parent_group_for_helper(hass, entity_id: str) -> tuple[str | None, list[str]]:
    candidates = []
    selected_state = hass.states.get(entity_id)
    selected_name = str(selected_state.attributes.get("friendly_name", "")).casefold() if selected_state else ""

    for group_entity in hass.states.async_entity_ids("light"):
        if group_entity == entity_id:
            continue

        members = direct_member_lights(hass, group_entity)
        if not members:
            continue

        if entity_id.startswith(group_entity + "_"):
            candidates.append((len(group_entity), group_entity, members))
            continue

        group_state = hass.states.get(group_entity)
        group_name = str(group_state.attributes.get("friendly_name", "")).casefold() if group_state else ""
        if group_name and selected_name.startswith(group_name):
            candidates.append((len(group_name), group_entity, members))

    if not candidates:
        return None, []

    _, parent, members = sorted(candidates, reverse=True)[0]
    _LAST_GROUP_MEMBERS[parent] = members
    return parent, members

def _same_area_physical_lights(hass, source_entity_id: str) -> list[str]:
    registry = er.async_get(hass)
    source_entry = registry.async_get(source_entity_id)
    source_area = _entry_area_id(hass, source_entry)
    if not source_area:
        return []

    candidates: list[str] = []
    for entry in registry.entities.values():
        if entry.domain != "light" or entry.entity_id == source_entity_id:
            continue
        state = hass.states.get(entry.entity_id)
        if state is None:
            continue
        if state.attributes.get("is_hue_group") is True:
            continue
        if state.attributes.get("hue_type") in ("room", "zone", "group"):
            continue
        if state.attributes.get("entity_id"):
            continue
        if not _supports_any_color(state):
            continue
        if _entry_area_id(hass, entry) == source_area:
            candidates.append(entry.entity_id)
    return _unique(candidates)

def _clean_lights(hass, lights: list[str]) -> tuple[list[str], list[dict]]:
    cleaned: list[str] = []
    skipped: list[dict] = []
    seen = set()

    for light in lights:
        if light in seen:
            skipped.append({"entity_id": light, "reason": "duplicate"})
            continue
        seen.add(light)

        state = hass.states.get(light)
        if state is None:
            skipped.append({"entity_id": light, "reason": "missing"})
            continue
        if state.state in ("unavailable", "unknown"):
            skipped.append({"entity_id": light, "reason": state.state})
            continue

        cleaned.append(light)

    return cleaned, skipped

def resolve_targets(hass, selected_entities: list[str], expand_groups: bool = True) -> ResolveResult:
    resolved: list[str] = []
    source_parts: list[str] = []
    source_map: dict[str, str] = {}
    skipped: list[dict] = []
    group_diagnostics: dict = {}

    for entity_id in selected_entities:
        state = hass.states.get(entity_id)
        if state is None:
            skipped.append({"entity_id": entity_id, "reason": "selected_missing"})
            continue
        if state.state in ("unavailable", "unknown"):
            skipped.append({"entity_id": entity_id, "reason": f"selected_{state.state}"})
            continue

        expanded: list[str] = []
        source = f"{entity_id}:selected_entity"

        if expand_groups:
            direct = direct_member_lights(hass, entity_id, diagnostics=group_diagnostics)
            if direct:
                expanded = direct
                source = f"{entity_id}:direct_entity_id_members"
            elif _LAST_GROUP_MEMBERS.get(entity_id):
                expanded = _LAST_GROUP_MEMBERS[entity_id]
                source = f"{entity_id}:cached_direct_entity_id_members"
            else:
                parent, parent_members = _find_parent_group_for_helper(hass, entity_id)
                if parent_members:
                    expanded = parent_members
                    source = f"{entity_id}:parent_group:{parent}"
                elif is_group_entity(hass, entity_id):
                    area_members = _same_area_physical_lights(hass, entity_id)
                    if area_members:
                        expanded = area_members
                        source = f"{entity_id}:same_area_hue_group_fallback"

        if expanded:
            _LOGGER.debug("[resolver] %s expanded to %s via %s", entity_id, expanded, source)
            resolved.extend(expanded)
            for member in expanded:
                source_map[member] = source
        else:
            resolved.append(entity_id)
            source_map[entity_id] = source

        source_parts.append(source)

    cleaned, clean_skipped = _clean_lights(hass, resolved)
    skipped.extend(clean_skipped)

    # Ensure source map only contains final clean lights.
    source_map = {light: source_map.get(light, "unknown") for light in cleaned}

    return ResolveResult(
        lights=cleaned,
        source=", ".join(source_parts) if source_parts else "selected_entities",
        skipped=skipped,
        source_map=source_map,
        group_diagnostics=group_diagnostics,
    )
