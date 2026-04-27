# Changelog

## v1.1.15

### Added
- Added **Update Lights Now** as a top-level manual apply action.
- Added simplified **White Handling** for guided Basic control.

### Changed
- Reverted from dynamic Basic/Advanced UI hiding to a stable single visible control surface.
- **Control Mode** now resolves precedence at apply time instead of rebuilding Home Assistant entities.
- Basic mode uses guided controls as the source of truth; Advanced (Custom) uses detailed tuning controls.
- Status diagnostics now expose effective control mode, brightness source, white-handling source, and ignored advanced controls.
- Shortened **Gradient Pattern** option labels to avoid column wrapping.

### Fixed
- Avoids Home Assistant UI instability caused by toggling Basic/Advanced visibility.
- Prevents Basic and Advanced settings from racing by resolving one effective configuration per apply cycle.

## v1.1.14

### Fixed
- Control Mode now changes the actual visible Home Assistant control surface instead of only storing a preference.
- Basic mode now loads only guided everyday controls; Advanced (Custom) loads the full tuning controls.

### Changed
- Control Mode changes are persisted immediately and trigger an integration reload so the entity list rebuilds for the selected mode.
- Options flow now uses mode-dependent schemas, so Basic and Advanced (Custom) show different configuration fields.

## v1.1.13

### Added
- Added **Control Mode** with **Basic** and **Advanced (Custom)** options.
- Added **Brightness Level** presets: **Low**, **Medium**, **High**, and **Maximum**.

### Changed
- Basic mode is now guided rather than bare-bones: users keep core everyday controls such as Color Accuracy Mode, Number of Colors, Transition Time, Brightness Level, Auto Rotate Colors, Auto Rotation Interval, Restore Delay, Health Check, Status, and Targets.
- Advanced (Custom) keeps the full tuning surface for palette ordering, distribution, gradient detail, white/neutral handling, fallback behavior, and per-brightness caps.
- Selecting a Brightness Level applies coordinated standard-light and gradient-light brightness caps while preserving Advanced (Custom) granular controls.

## v1.1.12

### Added
- Added **Color Accuracy Mode** with **Natural**, **Vivid**, and **Album Accurate** options.
- Added expanded `PROJECT_STATE.md` with current feature coverage, architecture notes, and release handoff requirements.

### Changed
- Consolidated the visible color-filtering UI so users tune overall extraction behavior from one friendly control instead of separate dull-color, white-handling, white-strength, and low-color switches/selects.
- Existing saved filter options remain tolerated for compatibility, but the selected Color Accuracy Mode now drives active extraction behavior.
- README was updated incrementally and prior changelog content was preserved.

## v1.1.11

### Added
- Improved album art color accuracy using perceptual extraction:
  - Edge-aware sampling
  - Saturation-based weighting
  - Neutral/background suppression
  - Reduced black/white dominance
  - Warm/accent color preservation

### Fixed
- Improved color matching for album art with large neutral backgrounds, heavy black areas, or small but visually important warm/accent details.

## v1.1.10

### Added
- Added **White Filtering Strength** with **Gentle**, **Balanced**, and **Strong** options.
- Added diagnostics/cache awareness for the selected white filtering strength.

### Changed
- Tightened the default balanced white filtering so pale blue-gray and low-saturation bright neutrals are treated as white-like colors.
- **Always Filter Whites** and contextual white suppression now use the selected filtering strength while preserving the empty-palette safeguard.

## v1.1.9

### Fixed
- Added an empty-palette safeguard for aggressive white filtering so all-white or mostly white artwork cannot collapse to an empty palette.
- Ensured Black & White Handling still has usable palette input after White Color Handling runs.

### Changed
- Clarified White Color Handling behavior for all-white, grayscale, and black-and-white album art.


## v1.1.8

### Added
- Added **Color Rotation Mode** with options for track-change rotation, timed auto-rotation, both, or no rotation.
- Added **White Color Handling** with contextual white suppression, aggressive white filtering, or allowing whites.

### Changed
- New tracks can now shift palette assignments so individual lights are not pinned to the same palette slot across albums.
- White/cream colors are now suppressed only when real colors are present by default, preserving grayscale/black-and-white album art behavior.
- Palette cache keys now include the selected White Color Handling mode.


## v1.1.7

### Improved
- Tightened Hue gradient detection with a model-based fallback for known Hue gradient devices, including Play gradient lightstrips and Play gradient tubes, when Home Assistant/aiohue capability metadata is incomplete.
- Added per-light gradient capability diagnostics showing detection source, model, model ID, and fallback reason.
- Clarified mixed-group handling so gradient-capable lights use true gradient updates while standard lights in the same Hue room or zone continue receiving normal color updates from the same palette.

### Changed
- Gradient fallback is now explicitly per-light: a failed gradient update falls back only for that light and does not affect the rest of the target group.

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
