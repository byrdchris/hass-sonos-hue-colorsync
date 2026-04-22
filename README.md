
# Sonos Hue Color Sync (Production)

Sync Philips Hue lights to Sonos album art colors with high fidelity.

## Installation (HACS)
1. Add this repo as a Custom Repository in HACS
2. Install "Sonos Hue Color Sync"
3. Restart Home Assistant
4. Add Integration via UI

## Configuration
- Sonos Entity: any Sonos speaker (group leader auto-detected)
- Hue Bridge IP: your bridge IP
- Hue App Key: generated via Hue API
- Hue Group: name of Hue group

## Troubleshooting

### Lights not changing
- Verify Hue Bridge IP + API key
- Confirm group name matches exactly

### Colors look wrong
- Hue uses XY color space; some bulbs have gamut limits

### No reaction to music
- Ensure Sonos entity is `playing`
- Check HA logs for integration errors

### Grouping issues
- Integration follows current group coordinator automatically
- If inconsistent, regroup speakers in Sonos app

### Performance
- No polling used; event-driven
- If missed updates occur, restart HA

