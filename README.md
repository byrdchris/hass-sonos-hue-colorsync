# Sonos Hue Sync

Home Assistant custom integration that extracts colors from Sonos album art and applies them to Hue lights/groups.

## v1.19.0 features

- HA-native Sonos album-art palette extraction
- Hue room/group expansion
- Per-light color distribution
- Scene snapshot and restore
- Enable/disable switch
- Palette sensor with diagnostics
- Extract/apply/test buttons
- Palette clustering to reduce near-duplicate reds/pinks/browns
- Gradient-aware assignment, HA-native only
- Light assignment strategies:
  - Balanced
  - Sequential
  - Alternating bright/dim
  - Brightness order

## Notes

Gradient awareness does not create a true multi-segment gradient. It still uses Home Assistant `light.turn_on` and assigns one color per gradient entity.

For Home Assistant translation cache issues: restart HA and hard-refresh the frontend.


## v1.20.0

### Controls

Adds a Home Assistant select entity:

- **Assignment Strategy**

This appears on the integration device page alongside Extract Now, Apply Last Palette, Test Rainbow, and Enabled.

Changing the select immediately reapplies the last palette if one exists.

### Group diagnostics

The palette sensor now includes:

- `selected_entity_members`

This shows the direct `entity_id` member list exposed by selected Hue room/group entities, making it easier to confirm whether Home Assistant is exposing all bulbs in the group.


## v1.21.0

### Group resolution fix

- Uses Home Assistant's own light target expansion helper
- Still prefers the Hue group's live `entity_id` member attribute
- Improves `selected_entity_members` diagnostics so selected groups show an empty list instead of disappearing when no members are read
- Falls back to same-area Hue expansion only if direct members cannot be read


## v1.23.0

Regression fix after v1.22.

### Changes

- Does not process album art immediately during integration setup
  - avoids Hue group attributes being read before they are populated
- Removes `color_temp` service calls
  - uses `rgb_color` for neutral colors too
  - avoids `extra keys not allowed @ data['color_temp']`
- Reverts group resolver behavior to the last stable direct `entity_id` member path
- Keeps Assignment Strategy select entity from v1.20/v1.21

### Recommended test

After restart:
1. Wait for the Hue group state to show `entity_id`
2. Press **Extract Now**
3. Check:
   - `selected_entity_members`
   - `resolved_lights`
   - `last_error`


## v1.24.0

### Stabilized Hue group resolver

Fixes timing cases where a Hue room/group temporarily exposes an empty
`entity_id` member list.

Resolver order:

1. Retry direct group members briefly
2. Cache the last valid full direct member list
3. Use cached direct members if live members are temporarily empty
4. Fall back to area-based resolver only if no direct/cached members exist

This keeps all Hue room members instead of falling back to a partial area scan.


## v1.27.0

### Resolver reset

v1.26 failed to load because of a missing method. v1.27 is built from the last
stable resolver base and applies a simpler deterministic rule:

- If the selected Hue room/group exposes `entity_id`, use that list exactly.
- Do not filter direct group members through area/device metadata.
- This preserves Hue Play entities and any other valid members exposed by the group.
- Retry direct member reads for up to ~3 seconds before falling back.

### Important

If `light.living_room.entity_id` contains 9 lights, `resolved_lights` should
contain those same 9 lights.


## v1.28.0

### Resolver repair

Fixes v1.27 packaging error:

```text
name '_stabilized_resolve_light_entities' is not defined
```

v1.28 replaces the resolver with one clean path:

1. Use selected Hue group's live `entity_id` members exactly as exposed
2. Use cached direct members if available
3. Fall back to same-area Hue scan only if direct/cached members are unavailable

It does not filter Hue Play entities out of direct group members.


## v1.29.0

### Flicker reduction

Removes stepped crossfade.

Previous versions issued 5 repeated `light.turn_on` calls per light during one
album change. Hue/HA already supports transitions, so v1.29 now sends one
`light.turn_on` call per resolved light using the configured transition value.

This should reduce visible flicker during album changes and reduce service-call
chatter.


## v1.30.0

### Helper group resolution

If a selected Hue helper entity such as `light.living_room_primary` or
`light.living_room_ambient` has no direct members, the resolver now searches
for a parent light group with direct members.

Example:

- selected: `light.living_room_primary`
- parent found: `light.living_room`
- resolved targets: all members exposed by `light.living_room.entity_id`

The search is generic and is not hard-coded to Living Room.

### Transition

Ensures one `light.turn_on` call per resolved light.


## v1.31.0

### Explicit group expansion source

Adds a new options field:

- **Hue groups to expand**

Use this for real Hue room/zone/group entities such as:

- `light.living_room`
- `light.kitchen`
- `light.bedroom`

If this field is set, the integration expands those groups directly and ignores
helper entities such as:

- `light.living_room_primary`
- `light.living_room_ambient`

This avoids guessing parent groups from helper names and supports any group name.


## v1.32.0

### Edge-case hardening

Adds defensive handling for mixed and imperfect light selections:

- Deduplicates lights when multiple groups overlap
- Skips missing, unavailable, and unknown entities
- Keeps explicit selected entities if they cannot be expanded
- Tracks skipped lights and skip reasons in diagnostics
- Improves selected group diagnostics with:
  - state
  - friendly name
  - is_hue_group
  - hue_type
  - live entity members

New palette sensor diagnostic:

```yaml
skipped_lights:
  - entity_id: light.example
    reason: duplicate | missing | unavailable | unknown
```

This makes it safer to use multiple real Hue groups in **Hue groups to expand**.


## v1.33.0

### Member lights override

Adds a deterministic override for Hue groups that do not expose members reliably.

New options field:

- **Member lights override**

If populated, the integration uses those actual light entities directly and bypasses group expansion entirely.

Resolution priority is now:

1. Member lights override
2. Hue groups to expand
3. Hue lights / groups
