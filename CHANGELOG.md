# Changelog

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

