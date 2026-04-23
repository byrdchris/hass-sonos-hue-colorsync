# Sonos Hue Sync

## v1.7.0

Fixes palette extraction not triggering when Sonos is already playing.

### Key changes

- Processes the current Sonos state on setup
- Processes the current Sonos state when enabled
- Processes the current Sonos state after options changes
- Adds `sonos_hue_sync.extract_now`
- Detects metadata/artwork changes while Sonos remains in `playing`
- Adds diagnostic attributes:
  - `last_track_key`
  - `last_processing_reason`
- Keeps HA-native light control only


## v1.8.0

Fixes artwork fetching for current Home Assistant versions:

- Uses `timedelta(seconds=300)` for `async_sign_path`
- Avoids re-signing media proxy artwork URLs that already include `token=`
- Adds explicit `empty_response` and HTTP status diagnostics in the palette sensor


## v1.9.0

Improves color distribution when a selected target is a Hue room/zone/group light.

### Changes

- Adds `expand_groups` option, enabled by default
- Tries to expand selected group light entities into individual light entities
- Uses HA group `entity_id` attributes when available
- Falls back to Home Assistant entity/device registry area matching when grouped entities do not expose members
- Palette sensor `resolved_lights` shows the actual light entities being targeted

### Why this matters

If Home Assistant treats `light.living_room` as one aggregate light, one color is applied to the whole group. This build attempts to resolve that group into the actual member lights so each light receives a different palette color.


## v1.10.0
- Clean diagnostics (final light state only)
- Improved option naming/descriptions (UI friendly)


## v1.11.0

Visual feedback improvements:

- Adds button entities:
  - Extract Now
  - Apply Last Palette
  - Test Rainbow
- Palette sensor state now shows the number of extracted colors
- Palette sensor attributes now include `palette_preview`
- Improves config/options field labels and descriptions
- Adds `sonos_hue_sync.test_rainbow`

## Native dashboard preview card

Add an Entities card with:

- Sonos Hue Sync Enabled
- Sonos Hue Sync Palette
- Extract Now
- Apply Last Palette
- Test Rainbow

The palette sensor attributes show:

- `hex_colors`
- `rgb_colors`
- `palette_preview`
- `resolved_lights`
- `last_error`

## Optional Markdown card

Home Assistant's Markdown card can display sensor attributes. Replace the entity id if yours differs.

```yaml
type: markdown
title: Sonos Hue Palette
content: |
  {% set p = state_attr('sensor.sonos_hue_sync_palette', 'palette_preview') %}
  {% if p %}
  {% for c in p %}
  **{{ c.index }}. {{ c.hex }}** → {{ c.assigned_light }}
  {% endfor %}
  {% else %}
  No palette extracted yet.
  {% endif %}
```


## v1.12.0

Fixes group resolution regression introduced during the visual-feedback pass.

### Changes

- More aggressive Hue aggregate detection
- Expands Hue `*_primary` and `*_ambient` grouped light helpers to physical lights in the same HA area
- Avoids targeting other aggregate/group helper lights when expansion is enabled
- `palette_preview` now shows actual final per-light assignments, not every extracted color repeated across a smaller target set
- `last_service_data` is generated from the final transition pass only


## v1.13.0

Removes hard-coded group-name handling.

### Changes

- No longer relies on entity names like `*_primary` or `*_ambient`
- Detects grouped lights using Home Assistant entity registry metadata first
- Uses direct `entity_id` group members when available
- Uses Hue unique IDs that indicate grouped lights, rooms, or zones
- Falls back to same-area physical light expansion for Hue aggregate entities
- Keeps selected physical bulbs from being expanded accidentally where possible
