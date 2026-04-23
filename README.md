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
