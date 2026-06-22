from __future__ import annotations

# Hue service bridge. Resolves target lights, snapshots original state, applies RGB palettes, and restores previous scenes.
# brief-code-commented-build: moderate block-level comments added for maintainability.

from .applier import apply_assignments, clear_apply_cache
from .assignment import assign_colors, is_gradient_entity
from .const import ASSIGNMENT_STRATEGY_BALANCED, CONF_ASSIGNMENT_STRATEGY, CONF_EXPAND_GROUPS, CONF_EXCLUDE_LIGHT_ENTITIES
from .resolver import resolve_targets

async def snapshot_scene(hass, selected_entities: list[str]) -> dict:
    """Snapshot current light state for later restore, including off lights."""
    scene_id = "media_hue_sync_snapshot"
    clean_entities = [entity_id for entity_id in selected_entities if entity_id]
    entities: dict[str, dict] = {}
    for entity_id in clean_entities:
        state = hass.states.get(entity_id)
        if state is None:
            entities[entity_id] = {"state": "unavailable", "attributes": {}}
            continue
        attrs = dict(state.attributes or {})
        entities[entity_id] = {
            "state": state.state,
            "attributes": {
                "brightness": attrs.get("brightness"),
                "color_mode": attrs.get("color_mode"),
                "rgb_color": attrs.get("rgb_color"),
                "xy_color": attrs.get("xy_color"),
                "color_temp_kelvin": attrs.get("color_temp_kelvin"),
                "effect": attrs.get("effect"),
            },
        }
    scene_entity_id = None
    if clean_entities:
        await hass.services.async_call(
            "scene",
            "create",
            {"scene_id": scene_id, "snapshot_entities": clean_entities},
            blocking=True,
        )
        scene_entity_id = f"scene.{scene_id}"
    return {"scene_entity_id": scene_entity_id, "entities": entities}


def _snapshot_count(snapshot) -> int:
    if isinstance(snapshot, dict):
        return len(snapshot.get("entities", {}) or {})
    return 1 if snapshot else 0


async def restore_scene(hass, snapshot) -> dict:
    """Restore snapshot. Supports previous scene-id string snapshots too."""
    result = {
        "attempted": 0,
        "restored_on": 0,
        "restored_off": 0,
        "skipped": 0,
        "failed": [],
        "used_scene_fallback": False,
    }
    if not snapshot:
        return result
    if isinstance(snapshot, str):
        await hass.services.async_call("scene", "turn_on", {"entity_id": snapshot}, blocking=True)
        result["attempted"] = 1
        result["used_scene_fallback"] = True
        return result
    for entity_id, stored in (snapshot.get("entities", {}) or {}).items():
        result["attempted"] += 1
        original_state = stored.get("state")
        attrs = stored.get("attributes", {}) or {}
        try:
            if original_state in ("off", "unavailable", "unknown"):
                await hass.services.async_call("light", "turn_off", {"entity_id": entity_id}, blocking=True)
                result["restored_off"] += 1
                continue
            if original_state != "on":
                result["skipped"] += 1
                continue
            data = {"entity_id": entity_id}
            if attrs.get("brightness") is not None:
                data["brightness"] = attrs.get("brightness")
            color_mode = attrs.get("color_mode")
            if color_mode == "color_temp" and attrs.get("color_temp_kelvin") is not None:
                data["color_temp_kelvin"] = attrs.get("color_temp_kelvin")
            elif attrs.get("rgb_color") is not None:
                data["rgb_color"] = list(attrs.get("rgb_color"))
            elif attrs.get("xy_color") is not None:
                data["xy_color"] = list(attrs.get("xy_color"))
            effect = attrs.get("effect")
            if effect not in (None, "off"):
                data["effect"] = effect
            await hass.services.async_call("light", "turn_on", data, blocking=True)
            result["restored_on"] += 1
        except Exception as err:
            result["failed"].append({"entity_id": entity_id, "error": str(err)})
    return result

def resolve_light_entities(hass, selected_entities: list[str], expand_groups: bool = True):
    result = resolve_targets(hass, selected_entities, expand_groups=expand_groups)
    return result.lights, result.source, result.skipped

def resolve_light_entities_detailed(hass, selected_entities: list[str], expand_groups: bool = True):
    return resolve_targets(hass, selected_entities, expand_groups=expand_groups)


def _rotate_assignment_values(assignments: dict[str, tuple[int, int, int]], offset: int):
    """Rotate assigned colors across the same light order without re-resolving targets."""
    if not assignments or not offset:
        return assignments

    keys = list(assignments.keys())
    values = list(assignments.values())
    if len(values) < 2:
        return assignments

    offset = int(offset) % len(values)
    if offset == 0:
        return assignments

    rotated_values = values[offset:] + values[:offset]
    return dict(zip(keys, rotated_values))

async def apply_palette(hass, selected_entities: list[str], palette: list[tuple[int, int, int]], config: dict):
    if config.get("_frozen_resolved_lights"):
        resolved = list(config["_frozen_resolved_lights"])
        resolver_source = config.get("_frozen_resolver_source", "frozen_per_track")
        skipped_lights = list(config.get("_frozen_skipped_lights", []))
    else:
        result = resolve_targets(
            hass,
            selected_entities,
            expand_groups=config.get(CONF_EXPAND_GROUPS, True),
        )
        resolved = result.lights
        resolver_source = result.source
        skipped_lights = result.skipped

    excluded = set(config.get(CONF_EXCLUDE_LIGHT_ENTITIES, []) or [])
    if excluded:
        before = list(resolved)
        resolved = [entity_id for entity_id in resolved if entity_id not in excluded]
        for entity_id in before:
            if entity_id in excluded:
                skipped_lights.append({"entity_id": entity_id, "reason": "excluded_by_user"})

    if not resolved:
        return [], [], resolver_source, skipped_lights

    strategy = config.get(CONF_ASSIGNMENT_STRATEGY, ASSIGNMENT_STRATEGY_BALANCED)
    transition = float(config.get("transition", 2))
    assignments = assign_colors(hass, resolved, palette, strategy)
    rotation_offset = int(config.get("_rotation_offset", 0) or 0)
    if rotation_offset:
        assignments = _rotate_assignment_values(assignments, rotation_offset)

    service_data_sent, apply_skipped = await apply_assignments(hass, assignments, strategy, transition, palette=palette, config=config)

    return resolved, service_data_sent, resolver_source, skipped_lights + apply_skipped
