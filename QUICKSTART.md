# Sonos Color Sync - Quick Start (HACS Integration)

## Installation (2 minutes)

### Step 1: Install via HACS
1. Open Home Assistant
2. Go to **HACS** > **Integrations**
3. Click **+** (in bottom right)
4. Search for **"Sonos Color Sync"**
5. Click **Install**
6. **Restart Home Assistant** (Settings > System > Restart)

### Step 2: Add Integration
1. Go to **Settings > Devices & Services**
2. Click **Create Integration**
3. Search for **"Sonos Color Sync"**
4. Follow the setup wizard:

   | Field | What to Enter |
   |-------|---------------|
   | Sonos Entity | Select from dropdown (e.g., `media_player.living_room`) |
   | Hue Bridge IP | Your bridge's local IP (e.g., `192.168.1.100`) |
   | Hue App Key | Leave blank (for now) |
   | All other options | Use defaults or customize |

5. Click **Create**

### Step 3: Done!
- A switch entity `switch.sonos_color_sync` is created
- Start playing music on your Sonos
- Watch your Hue lights change colors! 🎨

## Manual Hue Pairing (if needed)

If you have an existing Hue app key you want to use:

1. Go back to **Settings > Devices & Services**
2. Find **Sonos Color Sync**
3. Click **⋮ > Edit**
4. Paste your **Hue App Key** in the field
5. Click **Update**

## Basic Controls

### Via Switch

Toggle on/off: **Settings > Devices & Services > Sonos Color Sync** (use the switch)

### Via Automation

```yaml
# Disable when watching TV
automation:
  - alias: "TV on, disable sync"
    trigger:
      platform: state
      entity_id: binary_sensor.tv_on
      to: "on"
    action:
      service: sonos_color_sync.toggle
      data:
        enabled: false

  - alias: "TV off, enable sync"
    trigger:
      platform: state
      entity_id: binary_sensor.tv_on
      to: "off"
    action:
      service: sonos_color_sync.toggle
      data:
        enabled: true
```

## Troubleshooting

### Integration won't appear after install

- [ ] Did you restart Home Assistant? (Settings > System > Restart)
- [ ] HACS properly installed? (Check HACS page)
- [ ] Custom components folder exists? (`~/.homeassistant/custom_components/`)

### Colors not syncing

- [ ] Is the switch turned ON? Check **Settings > Devices & Services**
- [ ] Is music actually playing? (Not paused)
- [ ] Are Hue lights powered on?
- [ ] Is Hue Bridge IP correct? Try: `ping 192.168.1.100`

### Lights don't return to previous scene

- [ ] Lights were in stable state before music started
- [ ] Try manually calling the restore service:
  ```yaml
  service: sonos_color_sync.restore_lights
  ```

## What's Happening (Under the Hood)

```
You play music on Sonos
        ↓
Integration detects new track
        ↓
Downloads album art
        ↓
Extracts dominant colors (K-means)
        ↓
Sends colors to Hue lights (2-second fade)
        ↓
When music stops
        ↓
Lights fade back to previous state ✨
```

## Settings Explained

| Setting | What It Does | Default |
|---------|-------------|---------|
| **Poll Interval** | Check for new songs every X seconds | 5 |
| **Color Count** | How many colors to extract (1-10) | 3 |
| **Transition Time** | Fade duration when changing colors (seconds) | 2 |
| **Filter Dull Colors** | Remove gray/black colors for better look | Enabled |
| **Cache Enabled** | Remember album colors to go faster | Enabled |
| **Light Group** | Only sync specific group (blank = all) | Blank |

## Common Automations

### Disable during movie night
```yaml
automation:
  - alias: "Movie time - disable sync"
    trigger:
      platform: state
      entity_id: binary_sensor.movie_mode
      to: "on"
    action:
      service: sonos_color_sync.toggle
      data:
        enabled: false
```

### Sync only at night
```yaml
automation:
  - alias: "Evening sync mode"
    trigger:
      platform: sun
      event: sunset
    action:
      service: sonos_color_sync.toggle
      data:
        enabled: true
```

### Specific light group only
Edit the integration and set **Light Group** to a group name like "Bedroom" or "Living Room"

## Full Feature List

✅ Real-time color sync (every 5 seconds)
✅ Automatic scene restoration when music stops
✅ Toggle on/off via switch entity or service
✅ Smart caching to reduce network load
✅ Hot configuration (changes apply instantly)
✅ Multi-light group support
✅ Configurable color extraction (1-10 colors)
✅ Smooth light transitions (0-10 seconds)
✅ Filter dull colors for better aesthetics
✅ Works with Home Assistant container deployments

## Next Steps

- **Customize settings** by editing the integration
- **Create automations** to control syncing based on events
- **Set up scenes** with specific light groups
- **Check logs** if something isn't working: Settings > System > Logs

---

**That's it! You're ready to go. Play some music and enjoy the color sync!** 🎵🎨
