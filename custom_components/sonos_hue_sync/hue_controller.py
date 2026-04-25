from __future__ import annotations

from .applier import apply_assignments, clear_apply_cache
from .assignment import assign_colors, is_gradient_entity
from .const import ASSIGNMENT_STRATEGY_BALANCED, CONF_ASSIGNMENT_STRATEGY, CONF_EXPAND_GROUPS
from .resolver import resolve_targets

async def snapshot_scene(hass, selected_entities: list[str]) -> str:
    scene_id = "sonos_hue_sync_snapshot"
    await hass.services.async_call(
        "scene",
        "create",
        {"scene_id": scene_id, "snapshot_entities": selected_entities},
        blocking=True,
    )
    return f"scene.{scene_id}"

async def restore_scene(hass, scene_entity_id: str) -> None:
    await hass.services.async_call("scene", "turn_on", {"entity_id": scene_entity_id}, blocking=True)

def resolve_light_entities(hass, selected_entities: list[str], expand_groups: bool = True):
    result = resolve_targets(hass, selected_entities, expand_groups=expand_groups)
    return result.lights, result.source, result.skipped

def resolve_light_entities_detailed(hass, selected_entities: list[str], expand_groups: bool = True):
    return resolve_targets(hass, selected_entities, expand_groups=expand_groups)

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

    if not resolved:
        return [], [], resolver_source, skipped_lights

    strategy = config.get(CONF_ASSIGNMENT_STRATEGY, ASSIGNMENT_STRATEGY_BALANCED)
    transition = float(config.get("transition", 2))
    assignments = assign_colors(hass, resolved, palette, strategy)
    service_data_sent, apply_skipped = await apply_assignments(hass, assignments, strategy, transition)

    return resolved, service_data_sent, resolver_source, skipped_lights + apply_skipped
