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
