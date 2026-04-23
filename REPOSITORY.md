# Repository Setup & Deployment Guide

## For Repository Maintainers

This guide helps you set up the repository for HACS distribution.

### Directory Structure

```
ha-sonos-color-sync/
├── sonos_color_sync/
│   ├── __init__.py              # Main integration entry
│   ├── config_flow.py           # Configuration UI
│   ├── const.py                 # Constants
│   ├── coordinator.py           # Sync logic & state
│   ├── switch.py                # Switch entity (on/off)
│   └── manifest.json            # Integration metadata
├── hacs.json                    # HACS metadata
├── README.md                    # Full documentation
├── QUICKSTART.md                # Quick start guide
├── LICENSE                      # MIT license
└── .gitignore                   # Git ignore file
```

### Initial Setup

1. **Create GitHub Repository**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/ha-sonos-color-sync.git
   git push -u origin main
   ```

2. **Update Files for Your Repository**
   
   In `manifest.json`:
   ```json
   "codeowners": ["@yourgithubusername"],
   "documentation": "https://github.com/yourgithubusername/ha-sonos-color-sync",
   "issues": "https://github.com/yourgithubusername/ha-sonos-color-sync/issues"
   ```

   In `hacs.json`:
   ```json
   "documentation": "https://github.com/yourgithubusername/ha-sonos-color-sync"
   ```

3. **Add to HACS**
   
   Once your repo is public:
   - Go to HACS website: https://hacs.xyz/
   - Click "Submit" in the menu
   - Fill out the form with your repository URL
   - Wait for review & approval (usually 1-2 days)

### Version Management

Update version in:
- `manifest.json`: `"version": "X.Y.Z"`
- `hacs.json`: `"version": "X.Y.Z"`

### Release Process

1. Update version numbers
2. Commit with message: `v2.0.0 release`
3. Create git tag: `git tag v2.0.0 && git push --tags`
4. GitHub will auto-create release notes

---

## For End Users (Container Installation)

### Option 1: HACS Installation (Recommended)

1. Ensure HACS is installed in Home Assistant
2. Go to HACS > Integrations
3. Click "+" and search for "Sonos Color Sync"
4. Install and restart Home Assistant
5. Go to Settings > Create Integration and configure

### Option 2: Manual Installation

For container deployments:

```bash
# Inside your Home Assistant container
docker exec homeassistant mkdir -p /config/custom_components/sonos_color_sync

# Copy files from this repository into that directory
# Then restart Home Assistant
```

Or if mounting config volume:

```bash
# On host machine
cp -r sonos_color_sync ~/.homeassistant/custom_components/
# Then restart Home Assistant
```

### Post-Installation

1. Restart Home Assistant
2. Go to Settings > Devices & Services > Create Integration
3. Search for "Sonos Color Sync"
4. Fill in configuration
5. Done!

---

## Requirements

The integration requires these Python packages (auto-installed):

- `Pillow==10.1.0` - Image processing
- `scikit-learn==1.3.2` - K-means clustering
- `numpy==1.24.3` - Numerical operations

All are specified in `manifest.json` and installed automatically by Home Assistant.

---

## File Descriptions

### `__init__.py`
- Entry point for the integration
- Handles setup and teardown
- Registers services and platforms

### `config_flow.py`
- Configuration UI (Settings > Create Integration)
- Options flow for editing existing config
- Validates user input

### `const.py`
- All configuration keys and constants
- Service names
- Platform names

### `coordinator.py`
- Main sync loop (async)
- Color extraction logic
- Hue Bridge API calls
- State management & persistence

### `switch.py`
- Toggle entity (`switch.sonos_color_sync`)
- Turn on/off the syncing

### `manifest.json`
- Integration metadata
- Requirements
- Documentation links
- Version

### `hacs.json`
- HACS-specific metadata
- Minimum HA version
- Links

---

## Troubleshooting Deployments

### Integration doesn't appear after install

```bash
# Check if folder exists and has files
ls -la ~/.homeassistant/custom_components/sonos_color_sync/

# Check Home Assistant logs for errors
# Settings > System > Logs > Load Full Logs
```

### Import errors at startup

Usually means a Python dependency is missing. Home Assistant should install them automatically from `manifest.json`, but you can manually:

```bash
# Inside HA container
pip install Pillow scikit-learn numpy
```

### Coordinator not starting

Check logs for:
- Missing Sonos entity ID
- Invalid Hue Bridge IP
- Network connectivity issues

### Changes not applying

The integration reads config at startup and when you edit in the UI. If editing manually, restart Home Assistant.

---

## Development Tips

### Testing Locally

1. Clone the repo
2. Copy to `~/.homeassistant/custom_components/`
3. Restart Home Assistant
4. Go through config flow
5. Check logs for errors

### Adding New Features

1. Edit `config_flow.py` to add new config options
2. Add constants to `const.py`
3. Update `coordinator.py` with new logic
4. Update `manifest.json` version
5. Test thoroughly in your HA instance

### Debugging

Enable debug logging:

```yaml
logger:
  logs:
    custom_components.sonos_color_sync: debug
```

Then check Settings > System > Logs for output.

---

## License

MIT License - Feel free to fork, modify, and distribute

## Credits

Built with:
- Home Assistant (framework)
- Philips Hue API
- scikit-learn
- Pillow
