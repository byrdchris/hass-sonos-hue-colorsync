# SONOS COLOR SYNC - QUICK REFERENCE (v2.0)

## ⚡ 5-Minute Setup

### 1️⃣ Install
- Copy files to Home Assistant `config/addons/sonos-color-sync/`
- Or add GitHub repo to Home Assistant Add-on Store
- Install "Sonos Color Sync" add-on

### 2️⃣ Configure
**Settings → Add-ons → Sonos Color Sync → Configuration**

| Field | What to Enter | Example |
|-------|---------------|---------|
| Sonos Entity | Media player entity | `media_player.living_room_sonos` |
| Hue Bridge IP | Your bridge's IP | `192.168.1.100` |
| Hue App Key | (Leave blank for pairing) | (auto-generated) |

### 3️⃣ Pair Hue Bridge
- Start add-on → Go to logs
- Click "Start Pairing" or use API
- **PRESS THE HUE BRIDGE BUTTON** within 30 seconds
- App key is generated automatically
- Save config

### 4️⃣ Play Music
- Play a song on Sonos
- Watch Hue lights sync colors automatically
- When music stops, lights return to previous scene
- Toggle add-on on/off to control syncing

---

## 🎯 NEW Features (v2.0)

**Automatic Scene Restoration:**
- When music stops, lights return to their previous state (color, brightness, on/off)
- Scene is captured before syncing starts
- Works even if add-on is restarted

**Toggle On/Off:**
- Disable add-on without losing scene data
- When disabled, music doesn't change lights
- Lights return to previous scene if they were syncing
- Re-enable anytime to resume functionality

---

## 🔄 Example Flow

```
Before:  Lights = warm white, 60% brightness
↓
Start playing music on Sonos
↓
Add-on captures: warm white, 60% brightness
↓
Lights sync to album colors
↓
Stop music
↓
Lights fade back to: warm white, 60% brightness ✨
```

---

## 🎛️ Configuration Reference

```
Sonos Settings:
├─ sonos_entity_id ........... Which Sonos to monitor
└─ (auto-populated from Home Assistant)

Hue Settings:
├─ hue_bridge_ip ............ Bridge IP (192.168.x.x)
├─ hue_app_key .............. (leave blank to pair)
└─ hue_light_group .......... (optional) specific group name

Sync Settings:
├─ poll_interval ............ Seconds between checks (default: 5)
├─ color_count .............. Colors to extract (default: 3)
├─ transition_time .......... Fade duration in seconds (default: 2)
├─ filter_dull_colors ....... Remove gray/black colors (default: on)
└─ cache_enabled ............ Cache album art (default: on)
```

---

## 🎮 API Controls

### Toggle Add-on

```bash
# Enable
curl -X POST http://homeassistant.local:8080/api/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Disable
curl -X POST http://homeassistant.local:8080/api/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

### Restore Lights Manually

```bash
curl -X POST http://homeassistant.local:8080/api/restore
```

### Check Status

```bash
curl http://homeassistant.local:8080/api/status
# Returns:
# {
#   "enabled": true,
#   "was_syncing": true,
#   "saved_scenes": 5,
#   ...
# }
```

---

## 🔧 Troubleshooting Checklist

### Lights not returning to previous scene
- [ ] Previous state was captured before music started
- [ ] Hue lights are still powered on
- [ ] Check logs: `Settings > Add-ons > Logs`
- [ ] Try manual restore: `curl -X POST http://.../api/restore`

### Add-on disabled but lights are stuck in sync colors
- [ ] Manually restore via API: `POST /api/restore`
- [ ] Or stop music and let it auto-restore
- [ ] Check if add-on is actually disabled: `GET /api/status`

### Add-on won't start
- [ ] Hue Bridge IP is correct
- [ ] Bridge is powered on and on same network
- [ ] Try: `ping 192.168.1.100`

### Colors not updating
- [ ] Music is actually playing (not paused)
- [ ] Sonos entity ID is correct
- [ ] Hue lights are powered on
- [ ] Add-on is enabled: check status API
- [ ] Check add-on logs for errors

---

## 📊 API Endpoints

```bash
# Status (includes enabled state & scenes)
GET /api/status

# Get Sonos entities
GET /api/sonos/entities

# Get Hue light groups
GET /api/hue/groups

# Clear cache
POST /api/cache/clear

# Start pairing
POST /api/pairing/start

# Toggle add-on
POST /api/toggle (with JSON: {"enabled": true/false})

# Restore lights to previous state
POST /api/restore
```

---

## 📁 File Structure

```
sonos-color-sync/
├── addon.yaml .............. Config & options
├── app.py .................. Main app (1200+ lines)
├── Dockerfile .............. Container
├── requirements.txt ........ Dependencies
├── README.md ............... Quick start
├── INSTALL.md .............. Full docs
└── DEPLOYMENT.md ........... Deployment
```

---

## 💾 What Gets Saved

- **State file** (`/data/state.json`): Enabled status, previous scenes, sync state
- **Cache** (`/data/cache/`): Album art colors (clearable via GUI/API)
- **Persistent across restarts**: Scenes, enabled status

---

## 🎯 All Features

✅ Real-time color sync (5 sec polling)
✅ **Automatic scene restoration when music stops**
✅ **Toggle on/off via API or future UI button**
✅ All settings editable in GUI (no restart needed)
✅ Automatic Hue pairing flow
✅ Smart caching with manual cache clear
✅ Smooth light transitions
✅ Multi-light support
✅ Production-ready & stable

---

**Ready? Install, configure, and start playing music!**
