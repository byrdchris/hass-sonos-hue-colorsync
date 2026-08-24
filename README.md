# Media Hue Sync

[![CI](https://github.com/byrdchris/hass-sonos-hue-colorsync/actions/workflows/ci.yaml/badge.svg)](https://github.com/byrdchris/hass-sonos-hue-colorsync/actions/workflows/ci.yaml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Media Hue Sync** is a Home Assistant custom integration that extracts intelligent color palettes from active **Sonos** album artwork and dynamically applies immersive lighting scenes to **Philips Hue** lights, rooms, zones, and native gradient fixtures.

---

## What's New in v1.4.0

- **Modular Architecture**: Rebuilt core extraction, neutral guardrails, circular hue coherence, and lifecycle management into clean, maintainable subsystems.
- **Async Event Loop Offloading**: Heavy image quantization and GaussianBlur filtering are safely offloaded to Home Assistant worker threads (`async_add_executor_job`) to prevent UI or event loop latency.
- **Concurrent Gradient Updates**: Multi-channel Hue gradient lights (Signe, Gradient strips, Play tubes) are now dispatched concurrently alongside standard bulbs.
- **Automated CI/CD Test Pipeline**: Continuous integration with GitHub Actions running Hassfest validation, HACS compliance checks, and a comprehensive 24-test suite across Python 3.11, 3.12, and 3.13.
- **Release Packaging Standards**: Standardized release archives to `media_hue_sync_${TAG}.tar.gz` and `media_hue_sync.zip` for automated HACS distribution.

*(See [CHANGELOG.md](CHANGELOG.md) for complete historical release notes.)*

---

## Key Features

- **Intelligent Palette Extraction**: Analyzes album art using perceptual color extraction, edge detection, and local image statistics.
- **Auto Artwork Style**: Automatically detects whether cover art is graphic/poster, photographic, cinematic, vivid, or monochrome, adjusting color balance on the fly.
- **Palette Coherence**: Harmonizes room lighting to the dominant color family while preserving vibrant intentional accents (e.g. vibrant magenta pops on cyan covers).
- **Monochrome Guardrails & White Shaping**: Prevents grayscale and black-and-white album covers from drifting into unwanted red, pink, or brownish tints on physical bulbs.
- **Native Hue Gradient Support**: Generates native multi-point gradient payloads for Hue Signe lamps, Play gradient lightstrips, and Play gradient tubes with perceptual luminance sorting (*Dark to Light*, *Light to Dark*).
- **Gradient Neutral Suppression**: Prevents Hue gradient fixtures from rendering dull neutral stops as harsh white.
- **Scene Snapshot & Graceful Restore**: Automatically captures the previous state of all lights (brightness, color temperature, RGB, and on/off states) and restores the room when music stops or sync is turned off.
- **Smart Color Rotation**: Shifts color assignments across fixtures on track changes, continuously on a timer, or both.

---

## Artwork Styles Guide

| Style | Description | Best For |
| :--- | :--- | :--- |
| **Auto** *(Default)* | Dynamically analyzes local image statistics per track to select the optimal style. | Mixed playlists & varied music libraries. |
| **Album Accurate** | Preserves extracted artwork tones closely, including muted and background colors. | Acoustic, classical, and subtle artwork. |
| **Ambient** | Softens contrast, reduces harsh saturation jumps, and produces gentle background lighting. | Relaxed listening, dinner parties, and evening playlists. |
| **Vivid** | Boosts color energy, saturation, and subject separation across lights. | Electronic, pop, and dance music. |
| **High Contrast** | Emphasizes saturated color blocks and dark anchors while suppressing compression artifacts. | Typography, pop-art, and flat graphic artwork. |
| **Monochrome / Neutral** | Enforces clean grayscale, warm-neutral, or contrast-shaped lighting without rainbow casts. | Black-and-white photography and acoustic album covers. |

---

## Supported Hardware

- **Sonos Media Players**: Any Sonos speaker or player configured in Home Assistant.
- **Philips Hue Lights**:
  - Standard White & Color Ambiance bulbs and lightstrips.
  - Hue Rooms and Zones (with automatic group member expansion).
  - Native Hue Gradient devices: **Hue Signe lamps**, **Hue Play Gradient Lightstrips**, **Hue Play Gradient Tubes**, and **Gradient Ambiance Lightstrips**.

---

## Installation with HACS

1. Open **HACS** in Home Assistant.
2. Go to **Integrations** → click the three dots in the top-right corner → select **Custom repositories**.
3. Add repository URL:
   ```text
   https://github.com/byrdchris/hass-sonos-hue-colorsync
   ```
4. Set category to **Integration** and click **Add**.
5. Find **Media Hue Sync**, click **Download**, and restart Home Assistant.
6. In Home Assistant, go to **Settings → Devices & Services → Add Integration** → search for **Media Hue Sync**.

---

## Configuration & Home Assistant Entities

Configuration is managed directly through the Home Assistant UI (Config & Options Flow):

### Core Controls & Entities
* **Switches**:
  * `Enable Sync`: Primary toggle for continuous media tracking and light synchronization.
  * `Distribute Across Group Lights`: Expands selected Hue rooms/zones into individual physical fixtures.
  * `Enable True Gradient`: Activates native multi-color gradient payloads for supported gradient lights.
  * `Cache Album Colors`: Caches extracted palettes in memory to eliminate repeat extraction latency.
* **Selects**:
  * `Artwork Style`: Choose between *Auto*, *Album Accurate*, *Ambient*, *Vivid*, *High Contrast*, and *Monochrome / Neutral*.
  * `Auto Intensity`: Controls how assertively Auto mode shapes the palette (*Subtle*, *Balanced*, *Expressive*).
  * `Neutral Tone Handling`: Controls white and grayscale rendering (*Natural*, *Reduce Whites*, *Warm Neutral*, *Preserve Contrast*).
  * `Palette Coherence`: Determines color harmony (*Natural*, *Balanced*, *Dominant Colors Only*, *Dominant + Vivid Accent*).
  * `Color Rotation`: Controls color shifting (*Off*, *On Track Change*, *Continuous*, *Track Change & Continuous*).
  * `Color Distribution Mode`: Assigns colors across fixtures (*Balanced*, *Alternating*, *Sequential*, *Brightness*).
  * `Gradient Pattern`: Sets multi-point gradient ordering (*Same Order*, *Offset*, *Random*, *Dark to Light*, *Light to Dark*).
  * `Gradient Neutral Suppression`: Prevents neutral stops from rendering as white on gradient lamps (*Auto*, *Strong*, *Keep Artwork Whites*, *Off*).
* **Buttons**:
  * `Update Lights Now`: Immediately applies current settings without requiring continuous sync.
  * `Refresh Colors`: Re-fetches and applies the active track's palette.
  * `Rotate Colors`: Rotates the palette one step across target fixtures.
  * `Health Check`: Runs an on-demand diagnostic check and displays a notification report.
* **Sensors**:
  * `Status / Palette`: Exposes active palette hex codes, RGB values, timings, guardrails, and restore states.
  * `Target Preview`: Displays resolved physical light entities, expanded groups, and excluded lights.

---

## Behavior & Scene Restoration

1. **When Playback Starts**: Media Hue Sync captures a snapshot of all target lights (including brightness, color, and on/off states).
2. **While Music Plays**: Colors are extracted and applied based on your configured artwork style and distribution mode.
3. **When Playback Stops / Pauses**: If `Restore Delay` is set, the integration waits for the delay before cleanly restoring your original lighting scene. If playback resumes during the delay, the restore is cancelled seamlessly.
4. **When Sync is Turned Off**: Lights are restored immediately from the captured snapshot.

---

## Automated Testing

Media Hue Sync includes an automated test suite covering unit tests and a 55-cover synthetic palette regression test:

```bash
# Run full test suite
pytest tests/ -v

# Run deterministic palette regression checks
python3 tests/test_palette_regression.py
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
