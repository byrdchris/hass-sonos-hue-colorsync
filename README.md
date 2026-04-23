# Sonos Hue Sync

## v1.6.0

Fixes the setup blocker caused by the accidental config entry version bump in v1.5.

### Key fixes

- Adds `async_migrate_entry`
- Keeps config flow `VERSION = 1`
- Migrates old `light_group` entries to `light_entities`
- Adds debug/info logging for:
  - setup
  - service registration
  - Sonos event listening
  - palette extraction
  - light service payloads

### Services

- `sonos_hue_sync.enable`
- `sonos_hue_sync.disable`
- `sonos_hue_sync.apply_last_palette`
- `sonos_hue_sync.test_color`

### Entities

- enable switch
- palette/diagnostics sensor
