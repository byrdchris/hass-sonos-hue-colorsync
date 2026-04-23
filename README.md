# Sonos Hue Sync

Home Assistant custom integration that reads Sonos album art, extracts a palette, and applies it to Hue lights.

## Included in this build

- UI setup via config flow
- UI edits after setup via options flow
- Change Sonos entity after setup
- Change light target after setup
- Enable/disable service calls
- Enable/disable dashboard switch entity
- Restore prior scene when disabled or playback stops
- HSV dull-color filtering
- Brightness scaling from luminance
- White handling with color temperature
- Crossfade-style stepped transitions

## Install

Copy `custom_components/sonos_hue_sync` into your Home Assistant config directory or install with HACS as a custom repository.

## Entities and services

This integration creates a switch entity per config entry:
- `switch.sonos_hue_sync_enabled`

Services:
- `sonos_hue_sync.enable`
- `sonos_hue_sync.disable`

## Notes

Options flow is under:
Settings → Devices & Services → Sonos Hue Sync → Configure
