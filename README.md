# Sonos Color Sync - Home Assistant Integration

A Home Assistant HACS integration that extracts dominant colors from Sonos album art and syncs them to Philips Hue lights in real-time.

## Features

✨ **Real-time Color Sync** - Updates every 5 seconds (configurable)
✨ **Automatic Scene Restoration** - Lights return to previous state when music stops
✨ **Toggle Control** - Enable/disable syncing via switch entity
✨ **Smart Caching** - Caches album art to reduce network load
✨ **Hot Configuration** - Change settings without restarting Home Assistant
✨ **Multi-light Support** - Cycles colors across all lights in a group
✨ **Smooth Transitions** - Configurable fade duration (0-10 seconds)

## Installation

### Via HACS (Recommended)

1. **Install HACS** if you haven't already
2. Go to HACS > Integrations
3. Click "+" and search for "Sonos Color Sync"
4. Click Install
5. Restart Home Assistant

### Manual Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ha-sonos-color-sync.git
   ```

2. Copy to your config:
   ```bash
   cp -r ha-sonos-color-sync/sonos_color_sync ~/.homeassistant/custom_components/
   ```

3. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to **Settings > Devices & Services > Create Integration**
2. Search for "Sonos Color Sync"
3. Enter your configuration:
   - **Sonos Entity**: Select your Sonos media player from the dropdown
   - **Hue Bridge IP**: Your bridge's IP address (e.g., `192.168.1.100`)
   - **Hue App Key**: Leave blank to skip (auto-pairing coming soon) or enter existing key
   - **Light Group** (optional): Specific group name, or leave blank for all lights
   - **Poll Interval**: How often to check for changes (1-60 seconds, default: 5)
   - **Color Count**: Number of dominant colors to extract (1-10, default: 3)
   - **Transition Time**: Fade duration when changing colors (0-10 seconds, default: 2)
   - **Filter Dull Colors**: Remove near-black/white colors (default: enabled)
   - **Cache Enabled**: Cache album art (default: enabled)

### Modify Configuration

1. Go to **Settings > Devices & Services**
2. Find "Sonos Color Sync" 
3. Click the three-dot menu > Edit
4. Update any settings and save
5. Changes apply immediately

## Usage

### Automatic Sync

Once configured, the integration automatically:
1. Monitors your Sonos speaker for currently playing music
2. Extracts 3 dominant colors from the album art
3. Syncs those colors to your Hue lights with smooth fade
4. Restores lights to previous state when music stops

### Manual Controls

#### Via Switch Entity

A switch entity `switch.sonos_color_sync` is created. Toggle it to enable/disable syncing.

#### Via Service Call

```yaml
# Enable syncing
service: sonos_color_sync.toggle
data:
  enabled: true

# Disable syncing
service: sonos_color_sync.toggle
data:
  enabled: false

# Manually restore lights
service: sonos_color_sync.restore_lights
```

#### Via Automation

```yaml
automation:
  - alias: "Disable Sonos Sync when TV is on"
    trigger:
      platform: state
      entity_id: binary_sensor.living_room_tv_on
      to: "on"
    action:
      service: sonos_color_sync.toggle
      data:
        enabled: false

  - alias: "Enable Sonos Sync when TV is off"
    trigger:
      platform: state
      entity_id: binary_sensor.living_room_tv_on
      to: "off"
    action:
      service: sonos_color_sync.toggle
      data:
        enabled: true
```

## How It Works

### Color Extraction

```
Album Art → Download → Resize to 150x150 → K-means Clustering → RGB Colors
```

The integration uses scikit-learn's K-means algorithm to find the dominant colors in album artwork. This is fast and accurate for most music types.

### Scene Restoration

Before syncing to album colors, the integration captures the current state of each light:
- Color (XY coordinates in Hue color space)
- Brightness
- On/off state
- Color temperature

When music stops or syncing is disabled, these are restored with a smooth 2-second fade.

### Caching Strategy

Album art URLs are cached by MD5 hash. Extracted colors are stored alongside the URL, so repeated plays of the same song don't require re-extraction—just a database lookup.

To clear the cache:
```bash
# Via service (coming soon)
```

Or manually delete the cache directory:
```bash
rm -rf ~/.homeassistant/sonos_color_sync/cache/
```

## Troubleshooting

### Colors not updating

- [ ] Confirm music is actually playing (not paused)
- [ ] Check that the Sonos entity ID is correct
- [ ] Verify Hue lights are powered on
- [ ] Check the switch entity is turned ON
- [ ] Look at the Home Assistant logs: `Settings > System > Logs`

### Lights not returning to previous scene

- [ ] Ensure lights were in a stable state before music started
- [ ] Verify Hue lights are still powered on
- [ ] Try the manual restore service
- [ ] Check logs for errors

### Hue Bridge connection fails

- [ ] Verify bridge IP address is correct: `ping 192.168.x.x`
- [ ] Ensure bridge is on the same network as Home Assistant
- [ ] Confirm app key is valid (if using existing key)

### Poor color quality

- [ ] Enable "Filter Dull Colors" to remove grays/blacks
- [ ] Increase "Color Count" to 5-7 for more variety
- [ ] Some album art is inherently low-contrast

## API/Service Reference

### Services

- **`sonos_color_sync.toggle`** - Enable/disable syncing
  - Parameter: `enabled` (boolean, optional - toggle if omitted)

- **`sonos_color_sync.restore_lights`** - Manually restore lights to previous state

### Entities Created

- **`switch.sonos_color_sync`** - Main on/off switch for the integration

## Performance

| Metric | Value |
|--------|-------|
| Memory Usage | ~20-50 MB |
| CPU Usage | Minimal (clustering every 5s) |
| Network | ~1-5 requests/minute (after caching) |
| Latency | <500ms per cycle |

## Configuration Examples

### Sync only living room lights

```yaml
# In configuration flow, set:
Hue Light Group: "Living Room"
```

### Slow, smooth transitions

```yaml
Transition Time: 5  # 5 second fade
```

### Aggressive color extraction

```yaml
Color Count: 7
Filter Dull Colors: Enabled
Poll Interval: 3  # Check more frequently
```

## Development

For contributing or development setup, see [DEVELOPMENT.md](DEVELOPMENT.md)

## License

MIT License - See LICENSE file

## Support

- **GitHub Issues**: https://github.com/yourusername/ha-sonos-color-sync/issues
- **Home Assistant Community**: https://community.home-assistant.io/

## Credits

Built with:
- Home Assistant (core framework)
- Philips Hue API
- Sonos (via Home Assistant integration)
- scikit-learn (K-means clustering)
- Pillow (image processing)
