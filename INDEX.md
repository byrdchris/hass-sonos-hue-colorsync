# Sonos Color Sync - Complete Package Guide

## 📦 What You Have

A complete, production-ready **HACS integration for Home Assistant** that extracts album art colors and syncs them to Philips Hue lights.

**For container deployments** (Docker, Kubernetes, etc.)

---

## 🚀 Quick Start (2 Minutes)

### You Want the HACS Integration (Recommended for Containers)

1. **Read**: `HACS_SETUP.md` or `QUICKSTART.md`
2. **Extract**: `ha-sonos-color-sync-hacs.tar.gz`
3. **Copy**: `sonos_color_sync/` folder to `~/.homeassistant/custom_components/`
4. **Restart**: Home Assistant
5. **Configure**: Settings → Create Integration → Sonos Color Sync
6. **Play music** → Watch lights sync colors! 🎨

---

## 📄 Documentation Files

### For Container Users (START HERE)
- **`HACS_SETUP.md`** - Complete HACS installation guide for containers
  - Docker commands
  - Docker Compose examples
  - Kubernetes setup
  - Troubleshooting

- **`QUICKSTART.md`** - 5-minute quick start
  - Step-by-step setup
  - Basic controls
  - Common automations

### Full Documentation
- **`README.md`** - Complete feature list and usage guide
  - All features explained
  - Automations examples
  - Troubleshooting

- **`REPOSITORY.md`** - For developers/maintainers
  - How to set up the GitHub repository
  - Version management
  - Development tips

### Legacy (Add-on Version)
- `DEPLOYMENT.md` - Old add-on deployment (skip this)
- `INSTALL.md` - Old add-on installation (skip this)
- `QUICK_REFERENCE.md` - Old add-on reference (skip this)

---

## 📦 Package Contents

### Main HACS Integration Archive
**`ha-sonos-color-sync-hacs.tar.gz`** (14 KB)

Contains:
```
sonos_color_sync/
├── __init__.py              # Integration entry point
├── config_flow.py           # Configuration UI
├── const.py                 # Constants
├── coordinator.py           # Main sync logic (async)
├── switch.py                # On/off toggle entity
└── manifest.json            # Metadata & dependencies

Plus:
├── hacs.json                # HACS metadata
├── README.md
├── QUICKSTART.md
├── REPOSITORY.md
├── LICENSE                  # MIT License
└── .gitignore
```

### Source Files (Individual)
Located in `/mnt/user-data/outputs/sonos_color_sync/`:
- `__init__.py` - Main integration setup
- `config_flow.py` - Configuration dialog
- `const.py` - Configuration constants
- `coordinator.py` - Color sync coordinator (1200+ lines)
- `switch.py` - Toggle switch entity
- `manifest.json` - Integration manifest

---

## 🎯 Installation Methods

### Method 1: HACS UI (When Listed)
1. HACS → Integrations → "+" → Search "Sonos Color Sync"
2. Install
3. Restart Home Assistant

### Method 2: Manual (For Containers)
```bash
# Extract the archive
tar -xzf ha-sonos-color-sync-hacs.tar.gz

# Copy to custom components
cp -r sonos_color_sync ~/.homeassistant/custom_components/

# If using container with mounted volume:
docker cp sonos_color_sync <container>:/config/custom_components/

# Restart
docker restart <container>  # or restart Home Assistant UI
```

### Method 3: Clone Repository
```bash
git clone https://github.com/yourusername/ha-sonos-color-sync.git
cp -r ha-sonos-color-sync/sonos_color_sync ~/.homeassistant/custom_components/
```

---

## ✨ Key Features

✅ **Real-time Color Sync** - Every 5 seconds (configurable)
✅ **Scene Restoration** - Lights return to previous state when music stops
✅ **Toggle Control** - Enable/disable via Home Assistant switch
✅ **Hot Configuration** - Changes apply without restart
✅ **Smart Caching** - Album art cache reduces network load
✅ **Multi-light Support** - Cycles colors across light group
✅ **Smooth Transitions** - Configurable 0-10 second fades
✅ **Container Friendly** - Perfect for Docker, Kubernetes, etc.

---

## 🔧 Configuration

After installation, configure in **Settings → Devices & Services → Create Integration**:

| Field | Required | Example | Purpose |
|-------|----------|---------|---------|
| Sonos Entity | Yes | `media_player.living_room` | Which Sonos to monitor |
| Hue Bridge IP | Yes | `192.168.1.100` | Your Hue Bridge |
| Hue App Key | No | (auto-generated) | Hue authentication |
| Poll Interval | No | 5 | Check interval (seconds) |
| Color Count | No | 3 | Colors to extract (1-10) |
| Transition Time | No | 2 | Fade duration (seconds) |
| Filter Dull Colors | No | ON | Remove gray/black colors |
| Cache Enabled | No | ON | Cache album art |
| Light Group | No | "Living Room" | Specific group or all |

---

## 🎮 Usage

### Automatic
1. Play music on Sonos
2. Lights automatically sync to album colors
3. When music stops, lights return to previous state

### Manual Control

**Toggle via Home Assistant:**
- Switch: `switch.sonos_color_sync`
- Or service: `sonos_color_sync.toggle`

**Create Automations:**
```yaml
automation:
  - alias: "Disable sync during movie"
    trigger:
      state:
        entity_id: binary_sensor.movie_mode
        to: "on"
    action:
      service: sonos_color_sync.toggle
      data:
        enabled: false
```

---

## 📋 Architecture

The integration runs **inside Home Assistant** as a custom component:

```
Home Assistant Container
├── Sonos Integration
├── Hue Integration (for bridge access)
└── Sonos Color Sync Integration ← YOU ARE HERE
    ├── Config Flow (UI setup)
    ├── Coordinator (async sync loop)
    ├── Switch Entity (on/off control)
    └── Services (toggle, restore)
```

**Runs:** Async, in the Home Assistant event loop
**Updates:** Every 5 seconds (or configured interval)
**Network:** Direct to Hue Bridge on local network
**State:** Persisted to Home Assistant config directory

---

## 🐳 Container Examples

### Docker
```bash
docker run -v ~/.homeassistant:/config homeassistant/home-assistant:latest

# Copy integration
docker cp sonos_color_sync <container>:/config/custom_components/
docker restart <container>
```

### Docker Compose
```yaml
version: '3'
services:
  homeassistant:
    image: homeassistant/home-assistant:latest
    volumes:
      - ./config:/config
    ports:
      - "8123:8123"
    restart: unless-stopped
```

Then:
```bash
cp -r sonos_color_sync config/custom_components/
docker-compose restart homeassistant
```

### Kubernetes
```bash
# Copy to pod
kubectl cp sonos_color_sync pod-name:/config/custom_components/

# Restart pod
kubectl delete pod pod-name
```

---

## 📊 What Gets Stored

### State File (Persisted)
`~/.homeassistant/sonos_color_sync/state.json`
- Enabled/disabled status
- Previous light scenes
- Sync activity state

### Cache Directory
`~/.homeassistant/sonos_color_sync/cache/`
- Album art color cache (by URL hash)
- Cleared via service call or manually deleted

---

## 🔍 Troubleshooting

### Integration doesn't appear
1. Check folder exists: `~/.homeassistant/custom_components/sonos_color_sync/`
2. Verify all files are present (6 Python files, manifest.json)
3. Restart Home Assistant
4. Check logs: Settings > System > Logs

### Colors not syncing
1. Is music playing? (Not paused)
2. Is switch turned ON?
3. Are Hue lights powered?
4. Can Home Assistant reach bridge? `ping <ip>`

### Lights stuck in sync colors
- Toggle switch off then on
- Or call `sonos_color_sync.restore_lights` service

See **HACS_SETUP.md** for detailed troubleshooting.

---

## 📚 Documentation Priority

**For Container Users:**
1. Start: `HACS_SETUP.md` (5 min)
2. Quick setup: `QUICKSTART.md` (2 min)
3. Full guide: `README.md` (reference)

**For Developers:**
- `REPOSITORY.md` (how to maintain repo)

**Ignore (Legacy):**
- `DEPLOYMENT.md`, `INSTALL.md`, `QUICK_REFERENCE.md` (old add-on format)

---

## 🎁 What's Included

✅ Complete integration source code
✅ Configuration UI (Home Assistant native)
✅ All dependencies listed in manifest
✅ Full documentation
✅ MIT License
✅ Git-ready (.gitignore, etc.)
✅ Ready for HACS distribution

---

## 🚀 Next Steps

1. **Extract**: `ha-sonos-color-sync-hacs.tar.gz`
2. **Copy**: `sonos_color_sync/` to custom_components
3. **Restart**: Home Assistant
4. **Configure**: Follow QUICKSTART.md
5. **Enjoy**: Play music and watch the colors! 🎨

---

## 📞 Support

- **Documentation**: See files above
- **Issues**: GitHub issues (after repository setup)
- **Community**: Home Assistant forums
- **Logs**: Settings > System > Logs (filter: `sonos_color_sync`)

---

## 📜 License

MIT License - Completely free to use, modify, and distribute

---

**Ready to get started? Read `HACS_SETUP.md` for your container platform!** 🚀
