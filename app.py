#!/usr/bin/env python3
"""
Sonos Color Sync - Home Assistant Add-on
Extracts dominant colors from Sonos album art and syncs to Philips Hue lights
With scene restoration and enable/disable toggle
"""

import json
import logging
import os
import time
import hashlib
import requests
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from urllib.parse import urljoin
from PIL import Image
from io import BytesIO
from sklearn.cluster import KMeans
import numpy as np
from flask import Flask, jsonify, request
from threading import Thread, Event
import colorsys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
CONFIG_PATH = Path("/data/options.json")
CACHE_DIR = Path("/data/cache")
STATE_FILE = Path("/data/state.json")
CACHE_DIR.mkdir(exist_ok=True)

# Flask app for configuration UI and API
app = Flask(__name__)

class StateManager:
    """Manages persistent state (previous scenes, enabled/disabled status)"""
    
    def __init__(self):
        self.state = {
            "enabled": True,
            "previous_scenes": {},  # light_id -> {xy, bri, state}
            "was_syncing": False,
            "last_synced_group": None
        }
        self.load()
    
    def load(self):
        """Load state from file"""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, 'r') as f:
                    self.state = json.load(f)
                    logger.info(f"State loaded: enabled={self.state.get('enabled', True)}")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
    
    def save(self):
        """Save state to file"""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")
    
    def set_enabled(self, enabled: bool):
        """Set enabled/disabled status"""
        self.state["enabled"] = enabled
        self.save()
        logger.info(f"Add-on toggled: {'enabled' if enabled else 'disabled'}")
    
    def is_enabled(self) -> bool:
        """Check if add-on is enabled"""
        return self.state.get("enabled", True)
    
    def save_scene(self, light_id: str, scene_data: Dict):
        """Save current light state as previous scene"""
        self.state["previous_scenes"][light_id] = scene_data
        self.save()
    
    def get_scene(self, light_id: str) -> Optional[Dict]:
        """Get saved scene for light"""
        return self.state["previous_scenes"].get(light_id)
    
    def clear_scenes(self):
        """Clear all saved scenes"""
        self.state["previous_scenes"] = {}
        self.state["was_syncing"] = False
        self.save()

state_manager = StateManager()

class ConfigWatcher:
    """Watches for configuration file changes and reloads without restart"""
    def __init__(self):
        self.config = {}
        self.last_mtime = 0
        self.reload_event = Event()
        self.load()
    
    def load(self):
        """Load configuration from Home Assistant"""
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, 'r') as f:
                    self.config = json.load(f)
                    self.last_mtime = CONFIG_PATH.stat().st_mtime
                    logger.info(f"Configuration loaded: {self.config}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    
    def check_reload(self):
        """Check if config file has changed and reload if needed"""
        try:
            if CONFIG_PATH.exists():
                current_mtime = CONFIG_PATH.stat().st_mtime
                if current_mtime > self.last_mtime:
                    self.load()
                    self.reload_event.set()
                    logger.info("Configuration reloaded from Home Assistant")
        except Exception as e:
            logger.error(f"Error checking config: {e}")
    
    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)

config_watcher = ConfigWatcher()

class HueBridgeManager:
    """Manages Philips Hue Bridge connection and pairing"""
    
    def __init__(self):
        self.bridge_ip = None
        self.app_key = None
        self.pairing_mode = False
        self.pairing_username = None
    
    def update_connection(self, bridge_ip: str, app_key: str):
        """Update bridge connection details"""
        self.bridge_ip = bridge_ip
        self.app_key = app_key
        if not bridge_ip or not app_key:
            self.pairing_mode = True
            logger.info("Pairing mode enabled - waiting for app key")
        else:
            self.pairing_mode = False
            logger.info(f"Connected to Hue Bridge at {bridge_ip}")
    
    def start_pairing(self) -> Dict:
        """Initiate pairing with Hue Bridge"""
        if not self.bridge_ip:
            return {"status": "error", "message": "Bridge IP not configured"}
        
        try:
            url = f"http://{self.bridge_ip}/api"
            payload = {"devicetype": "sonos-color-sync"}
            response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    if "success" in result[0]:
                        self.pairing_username = result[0]["success"].get("username")
                        logger.info(f"Pairing initiated. Please press the Hue Bridge button within 30 seconds.")
                        return {
                            "status": "pairing_started",
                            "message": "Press the Hue Bridge button within 30 seconds"
                        }
                    elif "error" in result[0]:
                        error = result[0]["error"]
                        if error.get("type") == 101:
                            return {
                                "status": "pairing_needed",
                                "message": "Press the Hue Bridge button and retry pairing"
                            }
            return {"status": "error", "message": "Failed to initiate pairing"}
        except Exception as e:
            logger.error(f"Pairing error: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_light_state(self, light_id: str) -> Optional[Dict]:
        """Get current state of a light"""
        if not self.bridge_ip or not self.app_key or self.pairing_mode:
            return None
        
        try:
            url = f"http://{self.bridge_ip}/api/{self.app_key}/lights/{light_id}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                state = data.get("state", {})
                return {
                    "xy": state.get("xy"),
                    "bri": state.get("bri"),
                    "on": state.get("on"),
                    "ct": state.get("ct"),
                    "hue": state.get("hue"),
                    "sat": state.get("sat")
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get light state: {e}")
            return None
    
    def set_light_color(self, light_id: str, rgb: Tuple[int, int, int], 
                       transition_time: int = 2) -> bool:
        """Set light color via Hue Bridge"""
        if not self.bridge_ip or not self.app_key or self.pairing_mode:
            logger.warning("Hue Bridge not properly configured or in pairing mode")
            return False
        
        try:
            # Convert RGB to Hue XY color space
            r, g, b = [x / 255.0 for x in rgb]
            
            # Gamma correction
            r = pow((r + 0.055) / 1.055, 2.4) if r > 0.04045 else r / 12.92
            g = pow((g + 0.055) / 1.055, 2.4) if g > 0.04045 else g / 12.92
            b = pow((b + 0.055) / 1.055, 2.4) if b > 0.04045 else b / 12.92
            
            x = r * 0.664511 + g * 0.154324 + b * 0.162028
            y = r * 0.283881 + g * 0.668433 + b * 0.047685
            z = r * 0.000088 + g * 0.072310 + b * 0.986039
            
            if x + y + z == 0:
                xy = [0.3, 0.3]
            else:
                xy = [x / (x + y + z), y / (x + y + z)]
            
            # Get brightness from RGB
            brightness = int(max(r, g, b) * 254)
            
            url = f"http://{self.bridge_ip}/api/{self.app_key}/lights/{light_id}/state"
            payload = {
                "xy": xy,
                "bri": brightness,
                "transitiontime": transition_time * 10  # Hue uses 100ms units
            }
            
            response = requests.put(url, json=payload, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to set light color: {e}")
            return False
    
    def restore_light_state(self, light_id: str, scene: Dict) -> bool:
        """Restore light to previous state"""
        if not self.bridge_ip or not self.app_key or self.pairing_mode:
            return False
        
        try:
            url = f"http://{self.bridge_ip}/api/{self.app_key}/lights/{light_id}/state"
            
            # Restore state with smooth transition
            payload = {
                "transitiontime": 20  # 2 second transition for restore
            }
            
            # Try to restore color info if available
            if scene.get("xy"):
                payload["xy"] = scene["xy"]
            if scene.get("bri"):
                payload["bri"] = scene["bri"]
            if scene.get("ct"):
                payload["ct"] = scene["ct"]
            if scene.get("hue"):
                payload["hue"] = scene["hue"]
            if scene.get("sat"):
                payload["sat"] = scene["sat"]
            
            # Restore on/off state
            if "on" in scene:
                payload["on"] = scene["on"]
            
            response = requests.put(url, json=payload, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to restore light state: {e}")
            return False
    
    def get_light_groups(self) -> List[Dict]:
        """Get available light groups from Hue Bridge"""
        if not self.bridge_ip or not self.app_key or self.pairing_mode:
            return []
        
        try:
            url = f"http://{self.bridge_ip}/api/{self.app_key}/groups"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                groups = response.json()
                return [{"id": k, "name": v.get("name")} for k, v in groups.items()]
            return []
        except Exception as e:
            logger.error(f"Failed to get light groups: {e}")
            return []

hue_manager = HueBridgeManager()

class HomeAssistantClient:
    """Interface with Home Assistant API"""
    
    def __init__(self):
        self.ha_url = os.getenv("HA_URL", "http://supervisor/core/api")
        self.ha_token = os.getenv("SUPERVISOR_TOKEN", "")
    
    def get_entity_state(self, entity_id: str) -> Optional[Dict]:
        """Get current state of a Home Assistant entity"""
        try:
            url = urljoin(self.ha_url, f"states/{entity_id}")
            headers = {
                "Authorization": f"Bearer {self.ha_token}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get entity state: {e}")
            return None
    
    def get_available_sonos_entities(self) -> List[Dict]:
        """Get all available Sonos media player entities"""
        try:
            url = urljoin(self.ha_url, "states")
            headers = {
                "Authorization": f"Bearer {self.ha_token}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                states = response.json()
                sonos_entities = [
                    {
                        "entity_id": s.get("entity_id"),
                        "name": s.get("attributes", {}).get("friendly_name", "Unknown")
                    }
                    for s in states
                    if s.get("entity_id", "").startswith("media_player.")
                    and "sonos" in s.get("attributes", {}).get("device_name", "").lower()
                ]
                return sonos_entities
        except Exception as e:
            logger.error(f"Failed to get Sonos entities: {e}")
        return []

ha_client = HomeAssistantClient()

class ColorExtractor:
    """Extracts dominant colors from images"""
    
    @staticmethod
    def fetch_and_extract(image_url: str, color_count: int = 3,
                         filter_dull: bool = True, cache_enabled: bool = True) -> List[Tuple[int, int, int]]:
        """Fetch image and extract dominant colors"""
        
        # Check cache first
        if cache_enabled:
            cached = ColorExtractor._get_cached(image_url)
            if cached:
                return cached
        
        try:
            response = requests.get(image_url, timeout=10)
            if response.status_code != 200:
                return []
            
            img = Image.open(BytesIO(response.content))
            img = img.convert('RGB')
            
            # Resize for faster processing
            img.thumbnail((150, 150))
            
            colors = ColorExtractor.extract_from_image(img, color_count, filter_dull)
            
            # Cache the result
            if cache_enabled:
                ColorExtractor._cache_colors(image_url, colors)
            
            return colors
        except Exception as e:
            logger.error(f"Failed to extract colors from {image_url}: {e}")
            return []
    
    @staticmethod
    def extract_from_image(img: Image.Image, color_count: int = 3,
                          filter_dull: bool = True) -> List[Tuple[int, int, int]]:
        """Extract dominant colors from PIL Image"""
        try:
            # Convert to numpy array
            img_array = np.array(img)
            pixels = img_array.reshape(-1, 3)
            
            # K-means clustering
            kmeans = KMeans(n_clusters=min(color_count, len(pixels)), random_state=42, n_init=10)
            kmeans.fit(pixels)
            
            colors = kmeans.cluster_centers_.astype(int)
            
            if filter_dull:
                colors = ColorExtractor._filter_dull_colors(colors)
            
            # Limit to requested count after filtering
            return [tuple(c) for c in colors[:color_count]]
        except Exception as e:
            logger.error(f"Color extraction error: {e}")
            return []
    
    @staticmethod
    def _filter_dull_colors(colors: np.ndarray, threshold: int = 40) -> np.ndarray:
        """Remove near-black and near-white colors"""
        filtered = []
        for color in colors:
            r, g, b = color
            # Check if color is not too close to black or white
            brightness = (r + g + b) / 3
            if threshold < brightness < 255 - threshold:
                filtered.append(color)
        return np.array(filtered) if filtered else colors
    
    @staticmethod
    def _get_cached(image_url: str) -> Optional[List[Tuple[int, int, int]]]:
        """Get colors from cache"""
        cache_key = hashlib.md5(image_url.encode()).hexdigest()
        cache_file = CACHE_DIR / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    return [tuple(c) for c in data.get("colors", [])]
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
        return None
    
    @staticmethod
    def _cache_colors(image_url: str, colors: List[Tuple[int, int, int]]):
        """Cache extracted colors"""
        cache_key = hashlib.md5(image_url.encode()).hexdigest()
        cache_file = CACHE_DIR / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump({"url": image_url, "colors": colors}, f)
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

class SonosColorSync:
    """Main service that syncs Sonos colors to Hue lights"""
    
    def __init__(self):
        self.running = False
        self.last_track_id = None
        self.thread = None
        self.was_playing = False
    
    def start(self):
        """Start the sync service"""
        if self.running:
            return
        
        self.running = True
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("Sonos Color Sync started")
    
    def stop(self):
        """Stop the sync service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Sonos Color Sync stopped")
    
    def _run(self):
        """Main sync loop"""
        config_watcher.reload_event.clear()
        
        while self.running:
            try:
                # Check for config changes
                config_watcher.check_reload()
                if config_watcher.reload_event.is_set():
                    self._update_configuration()
                    config_watcher.reload_event.clear()
                
                # Check if add-on is enabled
                if not state_manager.is_enabled():
                    # If it was previously syncing, restore lights
                    if state_manager.state.get("was_syncing"):
                        self._restore_all_lights()
                        state_manager.state["was_syncing"] = False
                        state_manager.save()
                    
                    time.sleep(config_watcher.get("poll_interval", 5))
                    continue
                
                # Get Sonos entity state
                sonos_entity = config_watcher.get("sonos_entity_id")
                state = ha_client.get_entity_state(sonos_entity)
                
                if not state or state.get("state") != "playing":
                    # Music stopped - restore previous scene
                    if self.was_playing and state_manager.state.get("was_syncing"):
                        logger.info("Music stopped - restoring previous scene")
                        self._restore_all_lights()
                        state_manager.state["was_syncing"] = False
                        state_manager.save()
                        self.was_playing = False
                    
                    time.sleep(config_watcher.get("poll_interval", 5))
                    continue
                
                self.was_playing = True
                state_manager.state["was_syncing"] = True
                state_manager.save()
                
                # Get album art URL
                attributes = state.get("attributes", {})
                entity_picture = attributes.get("entity_picture")
                
                if not entity_picture:
                    time.sleep(config_watcher.get("poll_interval", 5))
                    continue
                
                # Construct full URL if relative
                if entity_picture.startswith("/"):
                    entity_picture = urljoin(
                        os.getenv("HA_URL", "http://supervisor/core/api"),
                        entity_picture
                    )
                
                # Check if track changed (avoid re-processing same track)
                track_id = attributes.get("media_content_id", entity_picture)
                if track_id == self.last_track_id:
                    time.sleep(config_watcher.get("poll_interval", 5))
                    continue
                
                self.last_track_id = track_id
                logger.info(f"New track: {attributes.get('title', 'Unknown')}")
                
                # Extract colors
                colors = ColorExtractor.fetch_and_extract(
                    entity_picture,
                    color_count=config_watcher.get("color_count", 3),
                    filter_dull=config_watcher.get("filter_dull_colors", True),
                    cache_enabled=config_watcher.get("cache_enabled", True)
                )
                
                if not colors:
                    logger.warning("No colors extracted")
                    time.sleep(config_watcher.get("poll_interval", 5))
                    continue
                
                # Update Hue lights
                self._update_hue_lights(colors)
                
            except Exception as e:
                logger.error(f"Sync error: {e}")
            
            time.sleep(config_watcher.get("poll_interval", 5))
    
    def _update_configuration(self):
        """Update manager configuration from Home Assistant"""
        bridge_ip = config_watcher.get("hue_bridge_ip", "")
        app_key = config_watcher.get("hue_app_key", "")
        hue_manager.update_connection(bridge_ip, app_key)
    
    def _update_hue_lights(self, colors: List[Tuple[int, int, int]]):
        """Update Hue light group with extracted colors"""
        try:
            light_group = config_watcher.get("hue_light_group", "")
            transition_time = config_watcher.get("transition_time", 2)
            
            # Get all light groups
            groups = hue_manager.get_light_groups()
            
            if light_group:
                # Filter to specific group
                groups = [g for g in groups if g["name"].lower() == light_group.lower()]
            
            if not groups:
                logger.warning("No light groups found")
                return
            
            # Get lights in group(s)
            all_lights = set()
            for group in groups:
                url = f"http://{hue_manager.bridge_ip}/api/{hue_manager.app_key}/groups/{group['id']}"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    group_data = response.json()
                    all_lights.update(group_data.get("lights", []))
            
            # Save current state before syncing (for restoration later)
            for light_id in all_lights:
                if light_id not in state_manager.state["previous_scenes"]:
                    current_state = hue_manager.get_light_state(light_id)
                    if current_state:
                        state_manager.save_scene(light_id, current_state)
            
            # Assign colors to lights (cycle through colors)
            lights_list = list(all_lights)
            for idx, light_id in enumerate(lights_list):
                color_idx = idx % len(colors)
                hue_manager.set_light_color(light_id, colors[color_idx], transition_time)
            
            logger.info(f"Updated {len(lights_list)} lights with {len(colors)} colors")
        except Exception as e:
            logger.error(f"Failed to update Hue lights: {e}")
    
    def _restore_all_lights(self):
        """Restore all lights to their previous scenes"""
        try:
            light_group = config_watcher.get("hue_light_group", "")
            groups = hue_manager.get_light_groups()
            
            if light_group:
                groups = [g for g in groups if g["name"].lower() == light_group.lower()]
            
            if not groups:
                return
            
            # Get lights in group(s)
            all_lights = set()
            for group in groups:
                url = f"http://{hue_manager.bridge_ip}/api/{hue_manager.app_key}/groups/{group['id']}"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    group_data = response.json()
                    all_lights.update(group_data.get("lights", []))
            
            # Restore each light
            restored = 0
            for light_id in all_lights:
                scene = state_manager.get_scene(light_id)
                if scene:
                    hue_manager.restore_light_state(light_id, scene)
                    restored += 1
            
            logger.info(f"Restored {restored} lights to previous state")
        except Exception as e:
            logger.error(f"Failed to restore lights: {e}")

# Flask API endpoints
@app.route('/api/pairing/start', methods=['POST'])
def start_pairing():
    """Start Hue Bridge pairing"""
    result = hue_manager.start_pairing()
    return jsonify(result)

@app.route('/api/pairing/status', methods=['GET'])
def pairing_status():
    """Get pairing status"""
    return jsonify({
        "pairing_mode": hue_manager.pairing_mode,
        "bridge_ip": hue_manager.bridge_ip,
        "app_key": "***" if hue_manager.app_key else None
    })

@app.route('/api/sonos/entities', methods=['GET'])
def get_sonos_entities():
    """Get available Sonos entities"""
    entities = ha_client.get_available_sonos_entities()
    return jsonify(entities)

@app.route('/api/hue/groups', methods=['GET'])
def get_hue_groups():
    """Get available Hue light groups"""
    groups = hue_manager.get_light_groups()
    return jsonify(groups)

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """Clear album art cache"""
    try:
        import shutil
        shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(exist_ok=True)
        return jsonify({"status": "success", "message": "Cache cleared"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def status():
    """Get service status"""
    return jsonify({
        "running": sync_service.running,
        "enabled": state_manager.is_enabled(),
        "was_syncing": state_manager.state.get("was_syncing", False),
        "pairing_mode": hue_manager.pairing_mode,
        "bridge_ip": hue_manager.bridge_ip,
        "cache_size": len(list(CACHE_DIR.glob("*.json"))),
        "saved_scenes": len(state_manager.state.get("previous_scenes", {}))
    })

@app.route('/api/toggle', methods=['POST'])
def toggle_addon():
    """Toggle add-on on/off via API"""
    data = request.get_json() or {}
    enabled = data.get("enabled")
    
    if enabled is None:
        # Toggle if not specified
        enabled = not state_manager.is_enabled()
    
    state_manager.set_enabled(enabled)
    
    if not enabled and sync_service.running:
        # Restore lights when disabling
        if state_manager.state.get("was_syncing"):
            sync_service._restore_all_lights()
    
    return jsonify({
        "status": "success",
        "enabled": enabled,
        "message": f"Add-on {'enabled' if enabled else 'disabled'}"
    })

@app.route('/api/restore', methods=['POST'])
def restore_lights_manual():
    """Manually restore all lights to previous state"""
    sync_service._restore_all_lights()
    return jsonify({"status": "success", "message": "Lights restored"})

# Main service instance
sync_service = SonosColorSync()

def main():
    """Main entry point"""
    logger.info("Sonos Color Sync Add-on starting...")
    
    # Load initial configuration
    config_watcher.load()
    sync_service._update_configuration()
    
    # Start sync service
    sync_service.start()
    
    # Start Flask API server
    try:
        app.run(host='0.0.0.0', port=8080, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
        sync_service.stop()

if __name__ == '__main__':
    main()
