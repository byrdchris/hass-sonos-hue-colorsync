# Sonos Color Sync - Home Assistant Add-on

**Automatically sync the dominant colors from your Sonos album art to your Philips Hue lights.**

Play music → Extract album colors → Update Hue lights in real-time. All configurable, all automatic.

## Quick Start

1. **Install** the add-on to Home Assistant
2. **Enter your Sonos entity ID** and Hue Bridge IP in the configuration
3. **Pair with your Hue Bridge** (press the button when prompted)
4. **Start** the add-on
5. **Play music** on Sonos and watch your lights change color

## What It Does

- Monitors your Sonos speaker for currently playing tracks
- Extracts the 3 most dominant colors from the album art (configurable)
- Sends those colors to your Philips Hue lights every 5 seconds (configurable)
- Lights fade smoothly between colors (2 second default fade, configurable)
- Caches album art to reduce network requests
- Automatically reloads configuration changes without restart

## Requirements

- Home Assistant with Sonos integration already set up
- Philips Hue Bridge on your network
- Hue lights or light groups

## Documentation

See [INSTALL.md](INSTALL.md) for detailed installation and configuration instructions.

## Architecture

```
Sonos (Home Assistant) 
    ↓ (monitors entity)
Color Extractor (K-means clustering)
    ↓ (extracts RGB colors)
Hue Bridge API
    ↓ (sets light colors)
Hue Lights (fade to new colors)
```

## Key Features

✅ Real-time color sync (checks every 5 seconds by default)
✅ Hot-reload configuration (no restart needed)
✅ Smart caching (reduces network load)
✅ Automatic Hue pairing flow
✅ Configurable color extraction (1-10 colors)
✅ Smooth transitions (0-10 seconds)
✅ Dull color filtering (optional)
✅ Multi-light support (cycles colors across lights)

## Support

Check [INSTALL.md](INSTALL.md) for troubleshooting and advanced usage.
