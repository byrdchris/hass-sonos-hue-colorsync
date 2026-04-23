# Sonos Hue Sync

This build focuses on two issues:

1. Fixing light changes not applying reliably
2. Exposing the extracted colors in Home Assistant

## What changed

- Signed Sonos artwork URLs before fetching them from Home Assistant
- Added error reporting to the palette sensor
- Added a palette sensor with:
  - hex colors
  - rgb colors
  - source artwork path
  - last error
- Switched the numeric config inputs to slider selectors

## Entities

- Switch: enable/disable sync
- Sensor: extracted palette

## Important note about slider text values

The selector now uses Home Assistant's number slider control. Whether the frontend shows an always-visible text field next to the slider depends on the current Home Assistant frontend behavior. The integration can request a slider, but it cannot fully control that widget rendering beyond the selector mode.
