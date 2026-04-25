# Changelog

## v2.0.2

### Added
- Added **Show Help** button.
- Added `sonos_hue_sync.show_help` service.
- Help opens as a Home Assistant persistent notification.
- Added expanded entity descriptions where Home Assistant supports them.

### Changed
- Improved control/help guidance for target selection, palette controls, assignment strategy, and troubleshooting.

### Notes
- Native Home Assistant hover tooltips still show entity names only. Use **Show Help** for richer guidance.

## v2.0.1

### Fixed
- Changing **Color Count** now forces fresh album-art extraction.
- **Extract Now** now bypasses palette cache.
- **Extract Now** forces light application even when state diffing would otherwise skip unchanged lights.
- Palette-affecting controls now force refresh:
  - Color Count
  - Filter Dull Colors
  - Filter Bright Whites
  - Black-and-White Album Handling
  - Handle Low-Color Album Art

## v2.0.0

### Added
- Resolver freeze per track.
- Target source map diagnostics.
- State diffing to skip unchanged light calls.
- Capability-aware light application.
- Cleaner module split:
  - `resolver.py`
  - `assignment.py`
  - `applier.py`
  - `hue_controller.py`

### Retained
- Runtime controls.
- Target Preview sensor.
- Palette sensor.
- Additional Hue groups.
- Additional member lights.
- Additive target handling.
- Monochrome and low-color album handling.
- Bright white filtering.
- HACS icon/package structure.
