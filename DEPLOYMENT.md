# Sonos Color Sync Add-on - Deployment Guide

## What You Have

This is a **complete, production-ready Home Assistant add-on** that:

1. **Monitors Sonos** via Home Assistant API for currently playing tracks
2. **Extracts dominant colors** from album art using K-means clustering
3. **Updates Philips Hue lights** in real-time with those colors
4. **Hot-reloads configuration** without requiring a restart
5. **Handles automatic Hue pairing** with a simple button flow
6. **Caches album art** to reduce network load, with GUI cache clearing

## Files Included

```
└── sonos-color-sync/                 # Main add-on directory
    ├── addon.yaml                    # Home Assistant add-on metadata & config schema
    ├── app.py                        # Main Python application (1000+ lines)
    ├── Dockerfile                    # Docker container definition
    ├── requirements.txt              # Python dependencies
    ├── README.md                     # Quick start guide
    ├── INSTALL.md                    # Detailed installation & troubleshooting
    └── setup.sh                      # Helper script for repository setup
```

## Deployment Options

### Option 1: Local Testing (Fastest)

1. **Create directory structure** on your Home Assistant machine:
   ```bash
   mkdir -p /home/homeassistant/addons/sonos-color-sync
   ```

2. **Copy files** to that directory:
   ```
   addon.yaml
   app.py
   Dockerfile
   requirements.txt
   ```

3. **Restart Home Assistant** and go to **Settings > Add-ons > Create addon > Local add-ons**

4. **Install** the "Sonos Color Sync" add-on

### Option 2: GitHub Repository (Recommended for sharing)

1. **Create a GitHub repository** named `addon-sonos-color-sync`

2. **Set up directory structure**:
   ```bash
   git clone <your-repo>
   cd addon-sonos-color-sync
   mkdir -p sonos-color-sync
   mv addon.yaml app.py Dockerfile requirements.txt sonos-color-sync/
   ```

3. **Create root README** and other docs at repository root

4. **Add to Home Assistant**:
   - Settings > Add-ons > Add-on Store (three dots menu)
   - Repositories > Add: `https://github.com/yourusername/addon-sonos-color-sync`
   - Refresh and install "Sonos Color Sync"

## Core Features Explained

### Hot-Reload Configuration

The application continuously monitors the `/data/options.json` file (where Home Assistant stores configuration). When you change any setting in the GUI:

1. Home Assistant writes the new config
2. The app detects the file change
3. It reloads configuration and applies it on the next cycle
4. **No restart needed**

```python
# From app.py - ConfigWatcher class
def check_reload(self):
    if CONFIG_PATH.stat().st_mtime > self.last_mtime:
        self.load()
        self.reload_event.set()  # Signal to main loop
```

### Color Extraction Pipeline

1. **Fetch album art** from Home Assistant entity's `entity_picture`
2. **Resize to 150x150** for fast processing
3. **K-means clustering** (scikit-learn) to find dominant colors
4. **Filter dull colors** (optional) - removes near-black/white
5. **Cache result** by URL hash to avoid re-processing

```
Album Art → K-means (3-10 clusters) → Filter → RGB Tuples → Cache
```

### Hue Bridge Integration

Two modes:

**Pairing Mode** (first-time setup):
- User enters bridge IP
- App requests pairing from bridge API
- User presses physical bridge button
- Bridge generates `app_key` automatically
- User saves key to config, ready to go

**Normal Mode** (after pairing):
- Uses stored `app_key` to authenticate
- Converts RGB to Hue's XY color space
- Applies gamma correction for proper brightness
- Sets transition time (smooth fade)
- Cycles colors across lights in group

### Caching Strategy

**Why cache?**
- Album art URLs are large (often 500KB+)
- The same song/album reappears frequently
- Reduces network load significantly

**How it works:**
- URL → MD5 hash → JSON file in `/data/cache/`
- Contains: URL, extracted RGB colors, timestamp
- User can clear cache anytime from GUI

## Configuration Options Explained

All configurable via Home Assistant GUI, no manual YAML editing:

| Option | Type | Default | Purpose |
|--------|------|---------|---------|
| `sonos_entity_id` | string | - | Which Sonos media player to monitor |
| `hue_bridge_ip` | string | - | IP address of Hue Bridge (192.168.x.x) |
| `hue_app_key` | string | - | Auto-generated during pairing (leave blank) |
| `poll_interval` | integer | 5 | Seconds between checking for new tracks |
| `color_count` | integer | 3 | How many dominant colors to extract (1-10) |
| `transition_time` | integer | 2 | Seconds for lights to fade to new color (0-10) |
| `filter_dull_colors` | boolean | true | Remove near-black/near-white colors |
| `cache_enabled` | boolean | true | Cache album art URLs to reduce requests |
| `hue_light_group` | string | - | (Optional) Specific light group name |

## API Endpoints

The add-on exposes these endpoints (port 8080) for advanced users:

```bash
# Check if service is running
GET /api/status

# Get available Sonos entities from Home Assistant
GET /api/sonos/entities

# Get available Hue light groups
GET /api/hue/groups

# Start Hue Bridge pairing
POST /api/pairing/start

# Check pairing status
GET /api/pairing/status

# Clear album art cache
POST /api/cache/clear
```

Example:
```bash
curl http://homeassistant.local:8123/api/addons/sonos-color-sync/status
```

## Requirements

**System:**
- Home Assistant with Sonos integration already set up
- Philips Hue Bridge (v2 or v3)
- Local network connectivity between HA and Hue Bridge

**Python libraries** (automatically installed):
- `requests` - HTTP requests
- `Pillow` - Image processing
- `Flask` - Web API
- `numpy` - Numerical operations
- `scikit-learn` - K-means clustering

**Computational:**
- Minimal - K-means on 150x150 images is fast
- Color extraction: ~100-200ms per image
- No GPU needed

## Troubleshooting

### Add-on won't start
```
Check logs: Settings > Add-ons > Sonos Color Sync > Logs
Common issues:
- Hue Bridge IP is wrong
- Network connectivity between HA and Hue Bridge
- Port 8080 already in use on HA machine
```

### Colors not updating
```
1. Confirm music is playing on Sonos (state = "playing")
2. Check Sonos entity ID is correct (Developer Tools > States)
3. Verify album art is available (check Sonos app)
4. Check Hue lights are powered on
5. Try a different song
```

### Pairing fails
```
1. Make sure you press the Hue Bridge button WITHIN 30 SECONDS
   - Button is usually on top of bridge
   - Some bridges have capacitive touch instead
2. Check bridge is reachable: ping <bridge-ip>
3. Try pairing again - no harm in retrying
```

### Poor color quality
```
- Enable "Filter Dull Colors" - removes grays/blacks
- Increase "Color Count" to 5-7 for more variety
- Some album art is inherently low-contrast
```

## Performance Considerations

**Resource Usage:**
- Memory: ~50-100 MB (Python + PIL + scikit-learn)
- CPU: Minimal - clustering runs every ~5 seconds
- Network: ~1-5 requests/minute after caching kicks in

**Bottlenecks:**
- Image download speed (network dependent)
- K-means clustering (very fast on 150x150 images)
- Home Assistant API calls (rate limited, but 1-2 per poll is fine)

## Development & Customization

The code is well-structured for modifications:

```
ConfigWatcher          → Manages hot-reload of settings
HueBridgeManager       → Handles Hue Bridge pairing & API
HomeAssistantClient    → Queries HA for Sonos state
ColorExtractor         → K-means clustering & caching
SonosColorSync         → Main loop tying everything together
Flask API              → Web endpoints for UI integration
```

## Logs

Monitor in Home Assistant:
```
Settings > Add-ons > Sonos Color Sync > Logs
```

Typical output:
```
Configuration loaded: {...}
Connected to Hue Bridge at 192.168.1.100
Sonos Color Sync started
New track: Song Name - Artist
Extracted colors: [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
Updated 5 lights with 3 colors
```

## Next Steps

1. **Deploy** using Option 1 or 2 above
2. **Configure** via Home Assistant GUI (Settings > Add-ons > Sonos Color Sync)
3. **Pair** with Hue Bridge (fill in IP, start pairing, press button)
4. **Start** the add-on
5. **Play** music on Sonos and watch your lights change!

## Support

For issues:
1. Check logs first (Settings > Add-ons > Logs)
2. Verify Sonos and Hue Bridge are on network
3. Test connectivity: `ping <bridge-ip>`
4. Try clearing cache and restarting

## License

MIT - Feel free to modify and distribute

## Credits

- **Home Assistant** - Core automation platform
- **Philips Hue API** - Light control
- **scikit-learn** - Color clustering
- **Pillow** - Image processing
