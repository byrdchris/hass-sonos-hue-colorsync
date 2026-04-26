# Changelog

## v2.3.15

### Changed
- Changed select-option config controls from dropdown mode to list mode where applicable.
- Improves dark-theme readability for selector fields.

### Notes
- This is a UI/UX-only patch. No color extraction, Hue control, fallback, or resolver behavior changed.

## v2.3.14

### Fixed
- Preferred direct Hue room/group `entity_id` members over same-area fallback.
- Prevented a frozen same-area fallback result from dropping direct Hue group members for the rest of a track.

### Added
- Added group expansion diagnostics:
  - `group_resolution`
  - `preview_group_resolution`

## v2.3.13

### Changed
- Rolled back to v2.3.7 as the stable baseline.
- Removed Album Art image entity and image platform setup.
- Kept fallback suppression logic from v2.3.12.

### Fixed
- Prevents transient artwork fetch failures from overwriting an existing useful palette with warm-neutral or generated fallback colors.
- Keeps standard-light Reapply Colors rotation behavior from v2.3.7.

### Diagnostics
- Keeps artwork fetch diagnostics.
- Adds/keeps `fallback_suppressed`.

## v2.3.6

### Fixed
- Reduced lag when several color apply events happen close together.
- Prevented overlapping full apply passes from stacking.
- Standard Hue/Home Assistant light service calls are now sent concurrently.

### Added
- Added `apply_queue_status` diagnostic field.

### Notes
- Gradient calls are still handled carefully through the Hue API, but standard lights no longer wait one-by-one behind each other.

## v2.3.5

### Changed
- **Reapply Colors** now rotates the current palette assignment across lights.
- True-gradient lights also receive rotated gradient point order when possible.

### Added
- Added `reapply_rotation_offset` diagnostic field.
- Added `gradient_rotation_offset` diagnostic field.

### Notes
- This does not re-extract album art. Use **Refresh Colors** for a fresh album-art extraction.

## v2.3.4

### Added
- Added **Current Artwork** image entity.
- Added fallback metadata polling while Sonos is playing.
- Added **AirPlay Metadata Check Interval** option.
- Added Sonos media/artwork diagnostics.

### Fixed
- Improves automatic updates when AirPlay/Sonos metadata changes do not reliably emit Home Assistant state events.

## v2.3.3

### Added
- Added **Artwork fallback behavior** option.
- Fallback modes:
  - Reuse last palette
  - Track-based colors
  - Warm neutral
  - Do nothing
- Added fallback diagnostics:
  - `artwork_fallback_mode`
  - `artwork_fallback_applied`

### Changed
- Artwork failures are now handled according to user preference instead of always using metadata fallback.

## v2.3.2

### Fixed
- Prevented empty Sonos artwork responses from stopping all light updates.
- Added fallback palette generation from track metadata when album art is unavailable.
- Reuses the previous palette when artwork fetch fails and a previous palette exists.
- Added image fetch diagnostics:
  - `last_image_fetch_status`
  - `last_image_fetch_candidates`

### Notes
- This addresses `last_palette_error: image_fetch_empty` and `last_error: no_palette_available`.

## v2.3.1

### Fixed
- Fixed raw option names appearing in the options flow for v2.3.0 controls.
- Added missing descriptions/help text for new brightness, exclusion, and restore-delay options.
- Runtime option changes now force reprocessing/reapply.
- Empty palette extraction falls back to the previous palette when available instead of leaving lights stale.
- Added `last_palette_error` diagnostic field.

### Notes
- This is a corrective patch for v2.3.0.

## v2.3.0

### Added
- Added **Minimum Brightness** control.
- Added **Maximum Brightness** control.
- Added **Gradient Brightness** control.
- Added **Excluded Lights** option.
- Added **Restore Delay** option.

### Changed
- Brightness is now clamped before light service calls.
- Gradient brightness is passed to Hue direct gradient control.
- Excluded lights are filtered after group expansion.
- Restore can now be delayed and cancelled if playback resumes.

## v2.2.1

### Fixed
- Improved low-color album art handling so mostly dark/neutral covers with strong accent colors no longer collapse into generic warm neutrals.
- Preserves real accent colors such as orange stars, logos, or text.
- Keeps usable dark anchors while still avoiding harsh bright whites.

### Notes
- This targets covers like black/navy artwork with orange or colored typography.

## v2.2.0

### Added
- Added MIT `LICENSE` file with attribution to Chris Byrd.
- Added **Health Check** button.
- Added `sonos_hue_sync.health_check` service.
- Health Check opens a Home Assistant persistent notification.
- Added Status diagnostics for timings, cache result, restore result, restore snapshot count, and health report.
- Expanded downloaded diagnostics with health and runtime troubleshooting data.

### Notes
- This is primarily a diagnostics and supportability release.

## v2.1.8

### Fixed
- Fixed Options/Config flow crash introduced in v2.1.7.
- Added missing Gradient Pattern constants to config flow imports.

### Notes
- This resolves:
  - `Config flow could not be loaded: 500 Internal Server Error`
  - `NameError: name 'GRADIENT_ORDER_MODES' is not defined`

## v2.1.7

### Added
- Added **Gradient Pattern** control for True Gradient Mode.
- Gradient pattern options:
  - Same order on every gradient light
  - Offset per light
  - Random order
- Gradient diagnostics now include `gradient_order_mode`.

### Changed
- Default gradient ordering is now same-order for a more coordinated look across multiple gradient lights.
- Offset per light preserves the previous varied/rotated behavior.
- Random order is deterministic per track and light so it changes between tracks without flickering during a track.

## v2.1.6

### Changed
- Added Download Diagnostics instructions to the in-app Help & Guide notification.
- Added diagnostics guidance to README troubleshooting documentation.
- Updated Help & Guide descriptions to mention diagnostics.

### Notes
- Diagnostics are available from Home Assistant's Devices & Services menu for the Sonos Hue Sync config entry.

## v2.1.5

### Added
- Added Home Assistant diagnostics support.
- Diagnostics can be downloaded from the Sonos Hue Sync config entry in Devices & Services.
- Diagnostics include:
  - integration config/options
  - runtime coordinator state
  - selected/resolved target entities
  - light state and capability attributes
  - entity/device registry metadata
  - Hue bridge runtime summary
  - gradient diagnostics and last service data

### Notes
- Sensitive fields such as tokens and source artwork URLs are redacted.

## v2.1.4

### Fixed
- True Gradient Mode now builds the Hue gradient payload without the unsupported `mode` argument for this Home Assistant/aiohue version.
- Removed the raw dictionary fallback through `controller.update`, because this aiohue path expects dataclass model payloads.

### Notes
- This addresses:
  - `GradientFeatureBase.__init__() got an unexpected keyword argument 'mode'`
  - `asdict() should be called on dataclass instances`

## v2.1.3

### Fixed
- True Gradient Mode now discovers Home Assistant Hue bridge runtime objects through Hue config entry `runtime_data`.
- Uses the Home Assistant HueBridge request wrapper when available.
- Adds `hue_bridge_count` to gradient diagnostics when no matching Hue resource is found.

### Notes
- This addresses cases where `gradient_match_attempts` was empty because the integration was looking in `hass.data["hue"]` instead of the Hue config entry runtime data.

## v2.1.2

### Added
- Expanded gradient resource matching using entity unique ID, device identifiers, friendly name, Hue V1 path fragments, and normalized names.
- Adds gradient match attempts to diagnostics when a Hue resource cannot be found.
- Includes gradient fallback diagnostics in `last_service_data`, not only `skipped_lights`.

### Changed
- Renamed UI entities for clearer product-level naming:
  - Palette → Status
  - Target Preview → Targets
  - Extract Now → Refresh Colors
  - Apply Last Palette → Reapply Colors
  - Test Rainbow → Test Lighting
  - Show Help → Help & Guide
  - Assignment Strategy → Color Distribution Mode
  - Gradient Color Points → Gradient Detail Level

### Notes
- True Gradient remains experimental. If it still reports `hue_resource_not_found`, the new diagnostics should show which Hue resources were discovered.

## v2.1.1

### Fixed
- Cleaned up **Gradient Color Points** labels/descriptions in UI translations.
- Improved True Gradient Mode diagnostics.
- Attempts direct Hue gradient update even when Home Assistant/aiohue exposes gradient metadata as an invalid or empty parsed object, as long as the entity looks like a gradient light.
- Adds raw-dictionary fallback payload after aiohue model payload failure.

### Notes
- True Gradient Mode remains experimental and still falls back to normal Home Assistant single-color control when direct gradient update fails.

## v2.1.0

### Added
- Experimental **True Gradient Mode** for Hue gradient-capable lights.
- **Gradient Color Points** control.
- Direct Hue/aiohue gradient application using Home Assistant's existing Hue bridge connection when available.
- HA-native fallback when direct gradient application fails.

### Notes
- Default is off.
- Normal lights continue using Home Assistant `light.turn_on`.
- Gradient lights use multiple palette colors only when True Gradient Mode is enabled and the Hue resource can be matched.

## v2.0.3

### Fixed
- Assignment strategy changes now affect gradient-aware lights, including Signe gradient lamps.
- Gradient-aware lights still receive assignment priority, but now use the selected strategy's palette order instead of a fixed accent palette.

### Notes
- This fixes cases where changing assignment strategy appeared to update regular Hue lights but not Signe/gradient lights.

