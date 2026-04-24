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
