# Changelog

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

