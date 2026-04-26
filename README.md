# Sonos Hue Sync

Sonos Hue Sync is a Home Assistant custom integration that extracts colors from the currently playing Sonos album art and applies them to Philips Hue lights, rooms, zones, and supported gradient lights.

---

## Requirements

- Home Assistant (latest)
- HACS installed
- Sonos integration configured
- Philips Hue integration configured
- At least one Sonos media player
- At least one Hue light, room, or zone

---

## Installation (HACS Custom Repository)

1. Open **HACS**
2. Go to **Integrations**
3. Click the **⋮ menu (top right)**
4. Select **Custom repositories**
5. Add: https://github.com/byrdchris/hass-sonos-hue-colorsync

6. Category: **Integration**
7. Click **Add**
8. Install **Sonos Hue Sync**
9. Restart Home Assistant

📘 HACS docs: https://hacs.xyz/docs/faq/custom_repositories/

---

## Setup

1. Go to **Settings → Devices & Services**
2. Click **Add Integration**
3. Search for **Sonos Hue Sync**
4. Select:
- Sonos speaker
- Hue lights / rooms / zones
5. Configure options

---

## Features

- Album art color extraction
- Hue light, room, and zone support
- Gradient light support
- Color distribution modes
- Brightness controls (min/max/gradient)
- Transition control
- Artwork fallback handling
- Reapply / rotation
- Diagnostics + preview

---

## Usage

- **Refresh Colors** → extract new palette
- **Reapply Colors** → rotate existing colors
- **Targets** → shows controlled lights
- **Status** → shows palette + diagnostics
- **Enable/Disable** → toggle sync

---

## Notes

- AirPlay → Sonos may not always expose album art reliably
- Integration handles fallback behavior automatically

---

## License

MIT License  
© Chris Byrd
