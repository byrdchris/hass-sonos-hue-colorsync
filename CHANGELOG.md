# Changelog

## v1.0.0

First stable public release.

### Added

- Sonos album-art color extraction.
- Philips Hue light, room, and zone targeting.
- Hue gradient light support with configurable gradient detail and color ordering.
- Runtime controls for:
  - Sync enabled
  - Number of colors
  - Transition time
  - Minimum brightness
  - Maximum brightness
  - Gradient brightness
  - Color distribution mode
  - Black & white album handling
  - Harsh white reduction
  - Dull color filtering
  - Low-color artwork stabilization
  - Artwork fallback behavior
  - Restore delay
- Reapply Colors action to rotate the current palette across selected lights.
- Refresh Colors action to re-extract colors from current Sonos artwork.
- Target preview diagnostics.
- Palette/status diagnostics.
- Artwork fetch diagnostics for Sonos/AirPlay reliability.
- Fallback suppression so transient artwork failures do not overwrite an existing useful palette.
- HACS-ready custom integration packaging.

### Fixed

- Hue room/group member resolution now prefers direct Home Assistant `entity_id` membership before same-area fallback.
- Additional member lights are additive with selected Hue rooms/groups.
- Duplicate targets are skipped safely.
- Standard lights and true-gradient lights both participate in color rotation.
- Image entity experiment removed to keep the integration stable.

### Notes

Earlier v2.x builds are treated as pre-release/internal development history.
