# Sonos Hue Sync

## v1.5.0 changes

- Multiple light selection in setup and options flow
- Color mapping across multiple lights:
  - if colors > lights, use the first N colors
  - if lights > colors, repeat colors
- Diagnostic palette sensor now includes resolved target lights and last service payload
- New services:
  - `sonos_hue_sync.apply_last_palette`
  - `sonos_hue_sync.test_color`
- Backward compatible with older single-light config entries

## Gradient-capable Hue devices

This build treats each selected light entity as a standard Home Assistant light. If a Hue gradient strip is exposed as a single light entity through Home Assistant, this build will control it as a single light color target. True per-segment/multi-color control is not implemented here because that is not exposed as a standard Home Assistant light capability.

For best results with multiple colors, select multiple light entities or Hue room/zone grouped light entities.
