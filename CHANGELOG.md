# Changelog

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
