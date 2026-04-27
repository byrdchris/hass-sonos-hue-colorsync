# Sonos Hue Sync

Sonos Hue Sync is a Home Assistant custom integration that extracts colors from the currently playing Sonos album art and applies them to Philips Hue lights, rooms, zones, and supported gradient lights.

The integration is designed for Home Assistant installations running in container mode and is installable through HACS as a custom repository.

## Features

- Extracts color palettes from Sonos album artwork.
- Applies album-inspired colors to Philips Hue lights.
- Supports individual Hue lights, Hue rooms, Hue zones, and expanded group members.
- Supports gradient-aware Hue lighting with true-gradient mode where supported.
- Restores the previous lighting scene when playback stops or sync is turned off.
- Includes AirPlay/Sonos artwork fallback handling to reduce flicker and bad palette overwrites.
- Provides Home Assistant controls, diagnostics, health checks, and target previews.
- Optional **Auto Rotate Colors** mode cycles the active palette while music is playing, with a user-adjustable interval.
- Palette ordering can prioritize either vivid visual variety or the most dominant album-art colors first.

## Requirements

- Home Assistant, current release recommended.
- Home Assistant running in container mode is supported.
- HACS installed.
- Home Assistant Sonos integration configured.
- Home Assistant Philips Hue integration configured.
- At least one Sonos `media_player` entity.
- At least one Hue light, room, or zone.

## Installation with HACS

1. Open **HACS**.
2. Go to **Integrations**.
3. Open the menu in the upper-right corner.
4. Select **Custom repositories**.
5. Add this repository URL:

   ```text
   https://github.com/byrdchris/hass-sonos-hue-colorsync
   ```

6. Set the category to **Integration**.
7. Install **Sonos Hue Sync**.
8. Restart Home Assistant.
9. Go to **Settings → Devices & services → Add integration**.
10. Search for **Sonos Hue Sync** and complete setup.

## Configuration

Configuration is handled through the Home Assistant UI. YAML is not required.

During setup and in options, you can configure:

- **Sonos Entity**: the Sonos speaker to monitor.
- **Light Targets**: Hue lights, rooms, or zones to control.
- **Additional Hue Groups**: optional extra Hue groups to expand.
- **Additional Member Lights**: optional direct lights to include.
- **Excluded Lights**: lights that should never be controlled, even if included through a selected room or zone.
- **Number of Colors**: palette size from 1 to 10.
- **Palette Ordering**: choose whether the extracted palette favors vivid, visually distinct colors or keeps the most dominant album-art colors first.
- **Transition Time**: fade time for light changes.
- **Minimum Brightness**: lower brightness limit for standard lights.
- **Maximum Brightness**: upper brightness limit for standard lights.
- **Gradient Brightness**: upper brightness limit for supported gradient lights.
- **Restore Delay**: wait time before restoring the previous scene after playback stops.
- **Filter Dull Colors**: removes dull or gray-heavy colors.
- **Filter Harsh Whites**: avoids overly bright white palette entries.
- **Stabilize Low-Color Art**: improves behavior for simple or monochrome album art.
- **Black & White Handling**: controls how monochrome artwork is translated into light colors.
- **Artwork Fallback**: controls what happens when Sonos artwork is missing or unavailable.
- **Color Distribution Mode**: controls how the extracted palette is assigned across multiple lights. Use **Sequential** if you want lights to follow the selected Palette Ordering directly.
- **Enable True Gradient**: uses supported Hue gradient behavior when available.
- **Auto Rotate Colors**: automatically cycles the current palette while music is playing.
- **Auto Rotation Interval**: total cycle time between automatic rotation starts, adjustable from 1 to 60 seconds. Transition Time is treated as the fade portion of the cycle, with an internal safety buffer to avoid overlapping Hue updates.
- **Gradient Detail Level**: controls the number of gradient points.
- **Gradient Order Mode**: controls gradient ordering across lights.
- **Cache Album Colors**: stores album palettes for faster repeat playback.
- **Distribute Across Group Lights**: expands supported Hue groups to their member lights.
- **AirPlay Poll Interval**: fallback polling interval for metadata/artwork cases that do not emit reliable events.

UI labels are intentionally friendly. Internal configuration names are not shown in the Home Assistant interface.

## Home Assistant Controls

### Switches

- **Sync Active**: primary on/off control.
- **Filter Dull Colors**
- **Filter Harsh Whites**
- **Stabilize Low-Color Art**
- **Cache Album Colors**
- **Distribute Across Group Lights**
- **Enable True Gradient**
- **Auto Rotate Colors**

### Selects

- **Palette Ordering**
- **Color Distribution Mode**
- **Black & White Handling**
- **Artwork Fallback**
- **Gradient Order Mode**

### Numbers

- **Number of Colors**
- **Transition Time**
- **Minimum Brightness**
- **Maximum Brightness**
- **Gradient Brightness**
- **Gradient Detail Level**
- **Restore Delay**
- **Auto Rotation Interval**

### Buttons

- **Refresh Colors**: extracts and applies the current track palette.
- **Rotate Colors**: rotates the current palette across selected lights.
- **Test Lighting**: applies a test palette.
- **Health Check**: runs a connectivity and configuration check.
- **Help & Guide**: opens a persistent notification with usage guidance.

### Sensors

- **Status / Palette**: palette, media, apply, restore, and runtime diagnostics.
- **Target Preview**: resolved light targets and group-expansion diagnostics.

## Behavior

When the selected Sonos entity starts playing, the integration snapshots the current selected Hue lighting state, extracts a palette from the current album art, and applies the palette to the configured Hue targets.

When playback stops, pauses, or the primary sync control is turned off, the integration restores the previous lighting scene. If **Restore Delay** is set and playback resumes before the delay expires, the pending restore is cancelled.

Excluded lights are removed after group expansion. This means a light can be part of a selected Hue room or zone and still be protected from control.

When **Auto Rotate Colors** is enabled, the integration periodically reuses the same internal path as **Rotate Colors**. It does not recompute the palette. The current **Transition Time** value controls the fade. **Auto Rotation Interval** is treated as the total cycle time between rotation starts; the fade time and a small internal safety buffer are reserved inside that cycle. If the interval is shorter than the fade plus buffer, the integration waits long enough to avoid overlapping Hue updates. Interval and transition changes take effect while auto-rotation is already running.


## Palette Ordering vs. Distribution

**Palette Ordering** controls the order of colors produced by album-art extraction before any lights are updated.

- **Vivid Colors First** is the default and preserves the existing behavior. It favors saturated, visually distinct colors that usually look better on lights, even if those colors are not the most common colors in the artwork.
- **Dominant Colors First** keeps the most common usable album-art colors first. With this mode, **Number of Colors** behaves as “top N dominant colors.” For example, choosing 3 keeps the top 3 dominant usable colors; choosing 6 adds the next most dominant usable colors.

**Color Distribution Mode** is separate. It controls how the selected palette is assigned to lights. **Sequential** preserves Palette Ordering most directly. Balanced, Alternating, and Brightness modes may rearrange colors for visual spread.

**Gradient Pattern** is also separate. It controls how supported gradient lights arrange the selected palette across gradient points.

## Gradient Lights

Gradient support depends on Hue device and Home Assistant Hue integration capabilities. When true gradient control is unavailable or rejected by the Hue API, the integration falls back to standard light color control where possible.

## Troubleshooting

### HACS shows stale information

HACS and GitHub can cache repository metadata. Refresh HACS, restart Home Assistant, and confirm the installed version under the integration details.

### Lights do not restore

Check that the selected lights were available before playback started and review the **Status / Palette** sensor attributes for `restore_last_result` and `restore_snapshot_count`.

### A room or zone misses lights

Some Hue group entities expose member lights differently. Enable **Distribute Across Group Lights** and review the **Target Preview** sensor to see how targets were resolved.

### AirPlay artwork is inconsistent

AirPlay-to-Sonos artwork can be unreliable. Use **Artwork Fallback** and **Cache Album Colors** to reduce flicker and avoid bad palette overwrites.

### Gradient behavior is inconsistent

Confirm the light is a Hue gradient-capable device and review diagnostics for gradient fallback information.

## Release workflow

This repository includes a GitHub Actions release workflow. Pushing a version tag such as `v1.1.4` creates a GitHub release and attaches a clean archive.

```bash
git tag v1.1.4
git push origin v1.1.4
```

## License

MIT License. See `LICENSE`.
