# Sonos Color Sync - Home Assistant Add-on

A Home Assistant add-on that extracts dominant colors from Sonos album art and syncs them to Philips Hue lights in real-time.

## Features

- **Album Art Color Extraction**: Automatically extracts 3-10 dominant colors from currently playing album art
- **Real-time Sync**: Updates Hue lights every 5 seconds (configurable)
- **Smart Caching**: Caches album art to reduce network load, with cache clearing via GUI
- **Hot-reload Configuration**: All settings update without restarting the add-on
- **Automatic Pairing**: Simple Hue Bridge pairing flow integrated into the UI
- **Dull Color Filtering**: Automatically filters out near-black and near-white colors for better aesthetics
- **Smooth Transitions**: Configurable fade transitions (0-10 seconds)
- **Multi-light Support**: Cycles extracted colors across all lights in a Hue group

## Installation

### 1. Add Repository to Home Assistant

1. Go to **Settings** > **Add-ons** > **Add-on Store**
2. Click the three-dot menu and select **Repositories**
3. Add this repository URL:
   ```
   https://github.com/yourusername/sonos-color-sync-addon
   ```
4. Close the dialog
5. Search for "Sonos Color Sync" and click **Install**

### 2. Configure the Add-on

After installation:

1. Go to the add-on page and click **Configuration**
2. Fill in the following fields:

   **Sonos Setup**
   - **Sonos Entity ID**: Click the dropdown to select your Sonos media player
     (e.g., `media_player.living_room_sonos`)

   **Hue Bridge Setup**
   - **Hue Bridge IP**: Enter your Hue Bridge's IP address (e.g., `192.168.1.100`)
   - **Hue App Key**: Leave empty initially, then follow pairing instructions below
   - **Hue Light Group**: (Optional) Specify a light group name, or leave empty to use all lights

   **Sync Settings**
   - **Poll Interval**: How often to check for song changes (default: 5 seconds)
   - **Color Count**: Number of dominant colors to extract (default: 3)
   - **Transition Time**: Smooth fade duration in seconds (default: 2)
   - **Filter Dull Colors**: Remove near-black/near-white colors (default: enabled)
   - **Cache Enabled**: Cache album art to reduce network requests (default: enabled)

3. Click **Save**

### 3. Pair with Hue Bridge (if you don't have an app key)

1. **In Home Assistant**: Open the add-on logs
2. Click the **Pairing** button (if available in the UI), or use the API:
   ```bash
   curl -X POST http://homeassistant.local:8123/api/...
   ```
3. **On your Hue Bridge**: Press the physical button within 30 seconds
4. **In Home Assistant**: The add-on will generate an `app_key` automatically
5. Save the app key to configuration and the add-on will restart

### 4. Start the Add-on

1. Click the **Start** button on the add-on page
2. Monitor the logs to ensure it connects:
   ```
   INFO - Configuration loaded
   INFO - Connected to Hue Bridge at 192.168.1.100
   INFO - Sonos Color Sync started
   ```

## Usage

Once configured and running:

1. **Play music** on your Sonos device
2. **Watch your Hue lights** automatically sync to the album art colors
3. **Adjust settings** anytime via the add-on Configuration tab—changes apply immediately without restart

### Cache Management

To clear the album art cache (useful if you want to force re-extraction):

```bash
curl -X POST http://homeassistant.local:8123/api/addons/sonos-color-sync/cache/clear
```

Or use the Home Assistant UI if a cache clear button is available.

## Troubleshooting

### Add-on won't start
- Check Hue Bridge IP is correct and reachable: `ping 192.168.1.100`
- Ensure Home Assistant can reach the Hue Bridge on the local network
- Check add-on logs for specific error messages

### Colors not updating
- Confirm Sonos is actively playing music
- Verify the selected Sonos entity ID is correct (check in Developer Tools > States)
- Check that album art is available (should show in Sonos app)
- Ensure Hue lights are powered on and not in a scene/schedule

### Hue Bridge pairing fails
- Make sure you press the bridge button within 30 seconds of starting pairing
- The bridge button is usually on top (physical button or capacitive touch)
- If pairing times out, try again—no harm in retrying

### Colors are dull or monochrome
- Enable "Filter Dull Colors" in configuration
- Increase "Color Count" to extract more colors
- Some album art is inherently low-contrast (try a different song)

## API Endpoints

The add-on exposes these endpoints for advanced usage:

- `GET /api/status` - Service status and cache info
- `GET /api/sonos/entities` - Available Sonos media players
- `GET /api/hue/groups` - Available Hue light groups
- `POST /api/pairing/start` - Start Hue Bridge pairing
- `GET /api/pairing/status` - Check pairing status
- `POST /api/cache/clear` - Clear album art cache

## Configuration Schema Reference

```json
{
  "sonos_entity_id": "media_player.sonos",
  "hue_bridge_ip": "192.168.1.100",
  "hue_app_key": "generated-by-pairing",
  "poll_interval": 5,
  "color_count": 3,
  "transition_time": 2,
  "filter_dull_colors": true,
  "cache_enabled": true,
  "hue_light_group": ""
}
```

## Advanced Usage

### Manual API Configuration

If you prefer to manage configuration via Home Assistant's REST API:

```bash
curl -X POST http://homeassistant.local:8123/api/addons/sonos-color-sync/options \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sonos_entity_id": "media_player.living_room_sonos",
    "hue_bridge_ip": "192.168.1.100",
    "hue_app_key": "your-app-key",
    "poll_interval": 5,
    "color_count": 3,
    "transition_time": 2
  }'
```

## Support & Development

For issues, feature requests, or to contribute:
- GitHub Issues: [link to repo]
- Home Assistant Community: [link to forum thread]

## License

MIT License - See LICENSE file for details

## Credits

Built with:
- Home Assistant
- Philips Hue API
- Sonos API (via Home Assistant)
- scikit-learn (K-means color clustering)
- Pillow (image processing)
