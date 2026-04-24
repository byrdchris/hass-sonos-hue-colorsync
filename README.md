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


## v1.22.0

### Hue room/group resolution

Adds a third resolver path for Hue rooms/groups:

1. Use direct `entity_id` member list
2. Use Hue `lights` display-name list and map names to light entities by `friendly_name`
3. Use Home Assistant light target expansion helper
4. Fall back to same-area Hue expansion

This addresses timing cases where the Hue room state shows `lights` but the integration sees `entity_id` as empty during processing.

Diagnostics now show both:

```yaml
selected_entity_members:
  light.living_room:
    entity_id: [...]
    lights: [...]
```
