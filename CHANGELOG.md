# v1.2.15

- Made **Auto Style Behavior** materially affect the final palette instead of only biasing Auto Artwork Style classification.
- **Prefer Ambient** now visibly softens high-contrast Graphic / Poster palettes by lowering saturation, reducing harsh white/dark jumps, and lifting very dark colors.
- **Prefer Vivid** now applies stronger saturation and contrast shaping while still respecting neutral/monochrome guardrails.
- **Prefer Accuracy** now reduces the most stylized Auto behavior and keeps extracted luminance relationships closer to the artwork.
- Added diagnostics showing Auto Style Behavior before/after palette shaping, behavior strength, and whether the pass was applied or skipped.
- Fixed explicit **Dark to Light** / **Light to Dark** gradient ordering after Artwork Style changes by selecting gradient anchors from the full final palette and sorting by luminance after style processing.
- Ordered gradients now ignore per-light assignment base colors and rotation offsets so the selected gradient direction remains authoritative.
- Updated docs and project state for the current v1.2.x baseline.

# v1.2.14

- Fixed Neutral Tone Handling appearing unchanged on white/gray album art.
- Added visible white shaping for monochrome guardrail palettes.
- Reduce Whites now lowers bright neutral output more aggressively.
- Warm Ambient now uses a stronger but still safe warm-neutral tint.
- Standard Hue light applies can use color temperature for monochrome neutral palettes so whites visibly change instead of round-tripping as the same Hue white.
- Updated diagnostics to identify brightness and color-temperature shaping for neutral artwork.

# v1.2.13

- Fixed Neutral Tone Handling while Auto monochrome guardrails are active.
- Preserved grayscale protection for true monochrome artwork while allowing Neutral Tone Handling to change the resulting palette.
- Added safe monochrome variants for Reduce Whites, Preserve Contrast, Warm Ambient, Graphic / Poster, and Allow Pure White.
- Updated diagnostics to show the guardrail palette mode and neutral handling used.
- Validation: Python compile and JSON parse checks passed.

# v1.2.12

- Added monochrome guardrails for Auto Artwork Style.
- Prevented **Prefer Vivid**, **Warm Ambient**, and legacy warm-neutral handling from stacking on true black-and-white or grayscale artwork.
- Auto now preserves grayscale palettes when diagnostics show high neutral ratio, near-zero vivid color, and very low color diversity.
- Added diagnostics for monochrome guardrail detection and palette preservation.
- Updated Help & Guide, README, PROJECT_STATE, manifest, and documentation notes.

# v1.2.11

- Locked explicit **Dark to Light** and **Light to Dark** gradient ordering so Auto Artwork Style cannot destabilize the gradient flow on track changes.
- Changed ordered gradient detail handling from adaptive luminance-spread reselection to stable palette-anchor ordering followed by final perceptual luminance sorting.
- Kept rotation suppressed for ordered gradient modes.
- Added diagnostics for ordered gradient lock state and reason.
- Updated Help & Guide, README, PROJECT_STATE, manifest, and translations.

# v1.2.10

- Added **Auto** Artwork Style for per-track album-art style detection without cloud or AI services.
- Added **Auto Style Behavior** to bias Auto toward Balanced, Accuracy, Vivid, or Ambient results.
- Added **Monochrome Accent** artwork style for grayscale and black-and-white album art.
- Removed **Advanced / Custom** from visible Artwork Style and Neutral Tone Handling choices while preserving legacy values internally.
- Expanded Help & Guide and documentation to explain every artwork style, auto detection behavior, and troubleshooting guidance.
- Added diagnostics for detected artwork style, confidence, reasons, image statistics, and advanced override compatibility handling.

# v1.2.9


- Fixed restore reliability when **Enable Sync** is turned off. Sync Off now restores the captured light snapshot immediately instead of waiting for Restore Delay.
- Fixed delayed restore cancellation so only a real resumed playback/apply run cancels a pending playback-stop restore.
- Added clearer restore diagnostics: pending, restored, cancelled with reason, no snapshot, and failed states.
- Kept Restore Delay behavior for normal pause/stop playback, but prevented unrelated options/buttons while not playing from cancelling restore.
- Updated README, Help & Guide, CHANGELOG, and PROJECT_STATE.

# v1.2.8

- Added **Artwork Style** as the primary color interpretation control.
- Added **Neutral Tone Handling** to combine white, black, grayscale, and neutral behavior into one friendly setting.
- Added **Graphic / Poster** extraction for typography-heavy, high-contrast, and flat-color album art. This reduces invented/interpolated colors such as purple/pastel drift on red/black/white artwork.
- Kept older color controls available as Advanced / Custom behavior; no color-processing capability was removed.
- Updated Help & Guide, README, translations, diagnostics, and project state for the simplified color model.

## v1.2.7

- Replaced the separate Auto Rotate Colors switch behavior with a single Color Rotation selector: Off, On Track Change, Continuous, and Track Change and Continuous.
- Removed Auto Rotate Colors from the active entity/control surface and options form to avoid unclear dependency behavior. Existing stored values remain preserved for compatibility but no longer override Color Rotation.
- Made Color Rotation authoritative: Off disables all rotation, On Track Change rotates only on new tracks, Continuous rotates on the timer, and Track Change and Continuous does both.
- Added rotation diagnostics showing effective mode, track-change status, continuous status, legacy value handling, and ordered-gradient rotation suppression.
- Updated Help & Guide, README, translations, and PROJECT_STATE for the clarified rotation model.

## v1.2.6

- Replaced the Color Purity number slider with a named Color Purity Preset select while preserving the same underlying numeric behavior and old saved custom values.
- Added preset choices: Balanced, Album Accurate, Soft / Ambient, Vivid, and Bold / High Contrast.
- Preserved legacy custom Color Purity values as Custom / Existing until the user chooses a preset.
- Refreshed the Help & Guide notification with the latest v1.2.x controls, gradient behavior, diagnostics, target model, and troubleshooting notes.
- Updated README, translations, and PROJECT_STATE for the preset-based UI.

## v1.2.5

- Fixed Dark to Light and Light to Dark gradient ordering so explicit gradient ramps are applied as the final ordering step.
- Suppressed color rotation for ordered gradient patterns to prevent detail-level changes or auto-rotation from reversing the ramp.
- Changed ordered gradient sorting to gamma-corrected perceptual luminance with saturation tie-breaking.
- Improved Gradient Detail Level behavior by selecting colors across the dark/light range before sorting, especially for two-point gradients.
- Added diagnostics for gradient luminance values, sort basis, detail selection, and rotation suppression.

## v1.2.4

- Added **Palette Coherence** select with Off, Balanced, and Strict options.
- Palette Coherence removes isolated hue outliers universally, without tying behavior to a specific color family.
- Added diagnostics for coherence mode, dominant hue family, cluster score, and removed outlier colors.
- Palette cache keys now include Palette Coherence so tuning changes reprocess artwork correctly.
- Preserved v1.2.3 gradient pattern options including Dark to Light and Light to Dark.

## v1.2.3

- Added gradient pattern options for Dark to Light and Light to Dark.
- Gradient ordering now uses perceived luminance for smoother brightness ramps.
- Updated labels, descriptions, README, and project state for the new gradient modes.

## v1.2.2

- Fixed config-flow import failure caused by a syntax error in the coordinator effective-configuration block.
- Preserved v1.2.1 UI label and description fixes for Color Purity, White Handling, and White Suppression.
- No intended behavior changes.

## v1.2.1

- Fixed option form labels for Color Purity, White Handling, and White Suppression so Home Assistant no longer falls back to internal field names.
- Added complete descriptions for all visible configuration fields.
- Renamed White Level to White Suppression for clearer user-facing behavior.
- Removed remaining Basic / Advanced diagnostic language from active runtime reporting.
- No behavior changes to palette extraction or Hue apply logic.

## v1.2.0

- Corrected packaged metadata/version references so diagnostics and release docs report v1.2.0 consistently.

- Removed Basic / Advanced control mode to avoid confusing Home Assistant UI behavior.
- Added **Color Purity** slider:
  - `0` keeps only strong saturated colors.
  - `100` follows album art colors most closely.
- Added **White Level** slider so white/light-neutral suppression remains separate from color purity.
- Kept **White Handling** as a distinct control for Natural / Reduce Whites / Allow Whites behavior.
- Removed redundant user-facing white controls and brightness presets from the UI surface.
- Preserved v1.1.16 restore-on-disable behavior and commented code standard.
- Updated README and PROJECT_STATE.md without replacing release history.

# Changelog
## v1.1.16

### Added
- Added explicit restore snapshots when **Enable Sync** is turned on, before any light changes are applied.
- Added per-light restore diagnostics including attempted restores, restored-on count, restored-off count, skipped lights, and failures.
- Added bundled integration icon and logo assets at both the integration and repository roots to improve Home Assistant/HACS display behavior.

### Changed
- **Sync disabled** restore now uses the captured per-light state as the source of truth, including lights that were originally off.
- Renamed the primary switch display name from **Sync Active** to **Enable Sync** for clearer UI language.

### Fixed
- Fixes cases where lights that were off before sync could remain on after disabling sync.
- Improves restore reliability when sync is enabled but stopped before the first full palette apply.
- Reduces the chance of Home Assistant showing “icon not available” for the custom integration.


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
