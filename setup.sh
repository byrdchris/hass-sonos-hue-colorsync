#!/bin/bash
# Sonos Color Sync Add-on Repository Setup

# This script helps you set up the add-on repository structure
# Run this after cloning or creating the project

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Sonos Color Sync Add-on Setup${NC}"
echo "=============================="

# Create directory structure
echo -e "\n${GREEN}Creating directory structure...${NC}"

mkdir -p sonos-color-sync/{.github/workflows,translations}

# Move files to proper locations
echo -e "${GREEN}Organizing files...${NC}"

# The addon itself goes in a subdirectory
mkdir -p sonos-color-sync/sonos-color-sync

# Copy files
cp addon.yaml sonos-color-sync/sonos-color-sync/
cp app.py sonos-color-sync/sonos-color-sync/
cp Dockerfile sonos-color-sync/sonos-color-sync/
cp requirements.txt sonos-color-sync/sonos-color-sync/

# Create root files
cp README.md sonos-color-sync/
cp INSTALL.md sonos-color-sync/

# Create empty translations
cat > sonos-color-sync/translations/en.json << 'EOF'
{
  "configuration": {
    "step": {
      "init": {
        "title": "Configure Sonos Color Sync",
        "description": "Set up your Sonos and Hue Bridge connection",
        "data": {
          "sonos_entity_id": "Sonos Media Player Entity",
          "hue_bridge_ip": "Hue Bridge IP Address",
          "hue_app_key": "Hue App Key (leave empty to pair)",
          "hue_light_group": "Hue Light Group (optional)",
          "poll_interval": "Poll Interval (seconds)",
          "color_count": "Number of Colors to Extract",
          "transition_time": "Light Transition Time (seconds)",
          "filter_dull_colors": "Filter Dull Colors",
          "cache_enabled": "Enable Album Art Caching"
        }
      }
    }
  }
}
EOF

echo -e "${GREEN}✓ Directory structure created${NC}"
echo ""
echo "Directory structure:"
echo "sonos-color-sync/"
echo "├── sonos-color-sync/"
echo "│   ├── addon.yaml"
echo "│   ├── app.py"
echo "│   ├── Dockerfile"
echo "│   └── requirements.txt"
echo "├── README.md"
echo "├── INSTALL.md"
echo "└── translations/"
echo "    └── en.json"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Initialize a git repository: cd sonos-color-sync && git init"
echo "2. Create a GitHub repository for your add-on"
echo "3. Push to GitHub: git remote add origin <your-repo-url> && git push"
echo "4. Add the repository URL to Home Assistant's add-on store"
echo ""
echo "For manual testing, you can also:"
echo "1. Copy the sonos-color-sync/ directory to your Home Assistant config/addons/ folder"
echo "2. Restart Home Assistant"
echo "3. Go to Settings > Add-ons > Local add-ons to install"
