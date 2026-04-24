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


## v1.25.0

### Delayed group retry

Adds a one-time delayed retry after fallback/cached group resolution.

When the integration has to use fallback group resolution, it now:

1. Applies the palette immediately using the best available members
2. Waits about 3 seconds
3. Re-checks the selected Hue group for direct `entity_id` members
4. Reapplies the same palette once if it finds a larger/better member list

Diagnostics now include:

```yaml
delayed_retry_pending:
```


## v1.26.0

### Group member cache from live group state

The integration now listens to selected Hue group/light entities and caches their
direct `entity_id` members whenever Home Assistant publishes them.

This means a full group member list can be captured before a Sonos track change,
then reused if the group briefly reports an empty member list during palette
application.

Diagnostics now show:

```yaml
selected_entity_members:
  light.living_room:
    live_entity_id: [...]
    cached_entity_id: [...]
    effective_entity_id: [...]
```
