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
