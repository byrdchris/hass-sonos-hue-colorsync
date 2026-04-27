# Changelog

## v1.1.6

### Changed
- Increased the internal **Auto Rotate Colors** safety buffer from 0.75 seconds to 2.0 seconds to better account for Hue bridge, Home Assistant service-call, group, and gradient update latency.
- Auto-rotation now more conservatively extends the effective cycle time when **Transition Time** plus the safety buffer is longer than the configured **Auto Rotation Interval**.

### Improved
- Strengthened shared light-apply coordination so normal palette applies, manual rotation, auto-rotation, and test lighting do not stack overlapping Hue updates.
- Updated diagnostics and documentation to describe configured interval, effective cycle time, hold time, transition time, and safety buffer behavior more clearly.

## v1.1.5

### Changed
- Set **Dominant Colors First** as the default palette ordering for new installs.
- Set **Sync Active** to start off after Home Assistant restarts or HACS upgrades.

## v1.1.4

### Changed
- Refined **Auto Rotate Colors** timing so **Auto Rotation Interval** is treated as the total cycle time between rotation starts.
- Reserved the current **Transition Time** plus a small internal safety buffer inside each auto-rotation cycle to avoid overlapping Hue updates.
- Auto-rotation timing now wakes and recalculates immediately when interval or transition settings change.

### Added
- Added auto-rotation diagnostics for configured interval, transition time, safety buffer, calculated hold time, effective cycle time, active-update waiting, and last rotation timestamps.

## v1.1.3

### Added
- Added **Auto Rotation Interval** slider to control how often **Auto Rotate Colors** cycles the current palette.

### Changed
- Auto-rotation timing now updates immediately when **Auto Rotation Interval** changes while auto-rotation is already running.
- Diagnostics now show the active auto-rotation interval from the user setting.


## v1.1.2

### Added
- Added **Palette Ordering** select with **Vivid Colors First** and **Dominant Colors First** modes.
- Added diagnostics showing the active palette ordering mode.

### Changed
- **Number of Colors** now works with **Dominant Colors First** as the top N dominant usable album-art colors.
- Palette cache keys now include palette-affecting extraction options so cached colors do not mask ordering/filter changes.
- Updated README, Help & Guide, and Home Assistant labels/descriptions to explain Palette Ordering, Color Distribution Mode, and Gradient Pattern as separate controls.

## v1.1.1

### Added
- Added **Auto Rotate Colors** switch to automatically cycle the current palette while music is playing.

### Changed
- Auto rotation reuses the existing **Rotate Colors** path, including the current **Transition Time** setting for smooth fades.

## v1.1.0

### Added
- Minimum Brightness control for standard light updates.
- Maximum Brightness control for standard light updates.
- Gradient Brightness control for supported gradient lights.
- Excluded Lights selector so selected lights can be protected even when they are members of a selected Hue room or zone.
- Restore Delay control to wait before restoring the previous scene after playback stops.
- Restore-delay cancellation when playback resumes before the delay expires.
- Diagnostics fields for brightness limits, excluded lights, restore delay, and restore result.
- GitHub Actions release workflow that publishes a clean `.tar.gz` archive for version tags.

### Changed
- Reframed the post-v1.0 roadmap as the v1.1 release line.
- Renamed the primary control entity to **Sync Active** for clearer Home Assistant UI behavior.
- Cleaned README to present the integration as a public HACS-ready project without legacy development history.

### Fixed
- Enforced excluded-light filtering after Hue group expansion.
- Updated diagnostics and manifest version metadata to v1.1.0.

## v1.0.1

Initial stable public baseline.

### Included
- Sonos album-art color extraction.
- Philips Hue light, room, zone, and gradient-aware color application.
- Scene snapshot and restore when sync stops.
- Event-driven Sonos playback tracking with fallback polling for less reliable artwork/metadata cases.
- Palette caching, dull/white filtering, low-color stabilization, artwork fallback protection, and diagnostic sensors.
