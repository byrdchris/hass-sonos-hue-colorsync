# Sonos Color Sync - HACS Integration (Container Guide)

## What You're Getting

A complete Home Assistant integration that runs **inside Home Assistant** (not as a separate add-on). Perfect for container deployments.

**Features:**
- Extracts album art colors and syncs to Hue lights
- Automatic scene restoration when music stops
- Toggle on/off via Home Assistant switch
- Hot configuration (changes apply instantly)
- Smart caching + filter dull colors
- All configurable via Home Assistant UI

---

## Installation (3 Steps)

### Step 1: Install HACS (if not already installed)

1. Go to: https://hacs.xyz/docs/setup/prerequisites
2. Follow their installation instructions for your setup
3. Restart Home Assistant

### Step 2: Add This Integration to HACS

#### Option A: Via HACS UI (When Available)
1. Open Home Assistant → HACS → Integrations
2. Click "+" (bottom right)
3. Search: "Sonos Color Sync"
4. Install
5. Restart Home Assistant

#### Option B: Manual (For Container)
1. Extract `ha-sonos-color-sync-hacs.tar.gz`
2. Copy the `sonos_color_sync` folder to: `~/.homeassistant/custom_components/`
   
   If mounted in container:
   ```bash
   # If your config volume is at /config
   docker cp sonos_color_sync <container-id>:/config/custom_components/
   ```

3. Restart Home Assistant

### Step 3: Configure

1. Go to **Settings → Devices & Services**
2. Click **Create Integration**
3. Search: "Sonos Color Sync"
4. Fill in the form:

   | Field | Example |
   |-------|---------|
   | **Sonos Entity** | `media_player.living_room` (from dropdown) |
   | **Hue Bridge IP** | `192.168.1.100` |
   | **Hue App Key** | Leave blank (for now) |
   | **Poll Interval** | 5 (seconds) |
   | **Color Count** | 3 |
   | **Transition Time** | 2 (seconds) |
   | Other options | Use defaults |

5. Click **Create**

**Done!** A switch entity `switch.sonos_color_sync` is created.

---

## Quick Usage

### Play Music
1. Play a song on your Sonos device
2. Watch your Hue lights change colors automatically!
3. When the song ends, lights return to previous state

### Enable/Disable
Toggle the switch: **Settings → Devices & Services → Sonos Color Sync**

Or use a service call:
```yaml
service: sonos_color_sync.toggle
data:
  enabled: false  # disable
```

### Manually Restore Lights
```yaml
service: sonos_color_sync.restore_lights
```

---

## Container-Specific Setup

### Docker Container

If running Home Assistant as a container:

**Mounted Volume:**
```bash
docker run -v ~/.homeassistant:/config homeassistant/home-assistant:latest

# Then copy the integration:
docker cp sonos_color_sync <container-id>:/config/custom_components/
docker restart <container-id>
```

**Or directly in container:**
```bash
docker exec homeassistant mkdir -p /config/custom_components/sonos_color_sync
docker cp sonos_color_sync/* <container-id>:/config/custom_components/sonos_color_sync/
docker restart <container-id>
```

### Docker Compose

Add to your docker-compose.yml:
```yaml
homeassistant:
  image: homeassistant/home-assistant:latest
  volumes:
    - ./config:/config
    - /etc/localtime:/etc/localtime:ro
  # ... other config
```

Then:
```bash
cp -r sonos_color_sync config/custom_components/
docker-compose restart homeassistant
```

### Kubernetes (Helm)

If using the Home Assistant Helm chart, mount your custom components:
```yaml
persistence:
  config:
    enabled: true
    size: 10Gi
    
# Copy the custom component
kubectl cp sonos_color_sync <pod-name>:/config/custom_components/
```

---

## Troubleshooting

### Integration doesn't appear after install

```bash
# Check if the integration was copied correctly
docker exec <container> ls /config/custom_components/sonos_color_sync/

# Should show: __init__.py, coordinator.py, config_flow.py, switch.py, manifest.json, const.py

# If empty or missing, copy again and restart container
docker restart <container>
```

### Python Dependencies Missing

Home Assistant should auto-install these from `manifest.json`:
- Pillow
- scikit-learn
- numpy

If it doesn't, check logs: **Settings > System > Logs**

### No Sonos Entity in Dropdown

1. Make sure Sonos integration is installed in Home Assistant
2. Restart Home Assistant
3. Go back to config flow

### Colors Not Syncing

- [ ] Is music actually playing (not paused)?
- [ ] Is the switch turned ON?
- [ ] Are Hue lights powered on?
- [ ] Can Home Assistant reach Hue Bridge? `ping <bridge-ip>`
- [ ] Check logs: **Settings > System > Logs**

### Lights Don't Return to Previous Scene

- Ensure lights were in a stable state before music started
- Try manually: `service: sonos_color_sync.restore_lights`
- Check logs for errors

---

## Configuration Options

All options are in the integration's options screen (**Settings > ⋮ Edit**):

| Option | Min | Max | Default | Purpose |
|--------|-----|-----|---------|---------|
| Poll Interval | 1 | 60 | 5 | Check for new song (seconds) |
| Color Count | 1 | 10 | 3 | How many colors to extract |
| Transition Time | 0 | 10 | 2 | Fade duration (seconds) |
| Filter Dull Colors | - | - | ON | Remove gray/black colors |
| Cache Enabled | - | - | ON | Remember album colors |

---

## Persistence & State

The integration stores state in your Home Assistant config directory:

```
~/.homeassistant/sonos_color_sync/
├── state.json          # Enabled status, previous scenes, sync state
└── cache/              # Album art color cache
    ├── <hash1>.json
    ├── <hash2>.json
    └── ...
```

All persists across restarts, so lights return to previous scenes even after HA restart.

---

## Automations & Services

### Services

**Toggle Sync On/Off**
```yaml
service: sonos_color_sync.toggle
data:
  enabled: true  # or false, or omit to toggle
```

**Restore Lights Manually**
```yaml
service: sonos_color_sync.restore_lights
```

### Example Automations

**Disable During TV Time:**
```yaml
automation:
  - alias: "TV on, disable sync"
    trigger:
      platform: state
      entity_id: binary_sensor.living_room_tv
      to: "on"
    action:
      service: sonos_color_sync.toggle
      data:
        enabled: false

  - alias: "TV off, enable sync"
    trigger:
      platform: state
      entity_id: binary_sensor.living_room_tv
      to: "off"
    action:
      service: sonos_color_sync.toggle
      data:
        enabled: true
```

**Disable During Work Hours:**
```yaml
automation:
  - alias: "Workday morning, disable"
    trigger:
      platform: time
      at: "09:00:00"
    condition:
      condition: state
      entity_id: binary_sensor.workday_sensor
      state: "on"
    action:
      service: sonos_color_sync.toggle
      data:
        enabled: false

  - alias: "After work, enable"
    trigger:
      platform: time
      at: "17:00:00"
    action:
      service: sonos_color_sync.toggle
      data:
        enabled: true
```

**Sync Only in Specific Room:**
Edit the integration and set "Hue Light Group" to a group name like "Living Room"

---

## Performance Notes

- **Memory**: ~20-50 MB (minimal)
- **CPU**: Negligible (clustering every 5 seconds)
- **Network**: ~1-5 API calls per minute after caching
- **Latency**: <500ms per cycle

Safe to run on low-power containers.

---

## Development

For contributing or modifying:

1. Copy to `custom_components` as above
2. Enable debug logging:
   ```yaml
   logger:
     logs:
       custom_components.sonos_color_sync: debug
   ```
3. Check logs: **Settings > System > Logs**
4. Make changes and restart HA

---

## File Structure

```
sonos_color_sync/
├── __init__.py          # Entry point, services, platforms
├── config_flow.py       # Configuration UI
├── const.py             # Constants
├── coordinator.py       # Main sync loop & Hue/Sonos logic
├── switch.py            # On/off toggle entity
└── manifest.json        # Metadata & dependencies
```

---

## Updating

### Via HACS
HACS will notify you of updates. Click "Update" when available.

### Manual
1. Download latest `ha-sonos-color-sync-hacs.tar.gz`
2. Extract and copy `sonos_color_sync/` to `custom_components/`
3. Restart Home Assistant

---

## License

MIT License - Free to use, modify, and distribute

---

## Support

- **GitHub**: https://github.com/yourusername/ha-sonos-color-sync/issues
- **Home Assistant Community**: https://community.home-assistant.io/
- **Logs**: **Settings > System > Logs** (filter by `sonos_color_sync`)

---

## Next Steps

1. ✅ Install the integration
2. ✅ Configure it
3. ✅ Play music and enjoy the colors!
4. Create automations for your use case
5. Customize settings to your liking

**Enjoy!** 🎵🎨
