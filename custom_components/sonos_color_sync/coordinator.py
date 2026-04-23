"""Coordinator for Sonos Color Sync."""
import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiofiles
import numpy as np
import requests
from PIL import Image
from io import BytesIO
from sklearn.cluster import KMeans

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateCoordinator

from .const import (
    CONF_CACHE_ENABLED,
    CONF_COLOR_COUNT,
    CONF_FILTER_DULL,
    CONF_HUE_APP_KEY,
    CONF_HUE_BRIDGE_IP,
    CONF_LIGHT_GROUP,
    CONF_POLL_INTERVAL,
    CONF_SONOS_ENTITY,
    CONF_TRANSITION_TIME,
)

_LOGGER = logging.getLogger(__name__)


class SonosColorSyncCoordinator:
    """Coordinator for Sonos Color Sync."""

    def __init__(self, hass: HomeAssistant, config: Dict) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.config = config
        self.enabled = True
        self.was_playing = False
        self.last_track_id = None
        self.previous_scenes: Dict[str, Dict] = {}
        self.was_syncing = False
        self._update_task = None
        
        # Paths for cache and state
        self.config_dir = Path(hass.config.config_dir) / "sonos_color_sync"
        self.cache_dir = self.config_dir / "cache"
        self.state_file = self.config_dir / "state.json"
        self.config_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)
        
        self._load_state()

    def _load_state(self) -> None:
        """Load persisted state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    state = json.load(f)
                    self.enabled = state.get("enabled", True)
                    self.previous_scenes = state.get("previous_scenes", {})
                    self.was_syncing = state.get("was_syncing", False)
                    _LOGGER.info(f"State loaded: enabled={self.enabled}")
        except Exception as e:
            _LOGGER.warning(f"Failed to load state: {e}")

    def _save_state(self) -> None:
        """Save state to file."""
        try:
            state = {
                "enabled": self.enabled,
                "previous_scenes": self.previous_scenes,
                "was_syncing": self.was_syncing,
            }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            _LOGGER.warning(f"Failed to save state: {e}")

    def set_enabled(self, enabled: Optional[bool] = None) -> None:
        """Set enabled/disabled status."""
        if enabled is None:
            enabled = not self.enabled
        
        self.enabled = enabled
        self._save_state()
        
        if not enabled and self.was_syncing:
            # Schedule restore for next event loop
            asyncio.create_task(self.async_restore_lights())
        
        _LOGGER.info(f"Add-on toggled: {'enabled' if enabled else 'disabled'}")

    async def async_config_update(self) -> None:
        """Update configuration from config entry."""
        self.config = dict(self.hass.config_entries.async_entries(
            "sonos_color_sync"
        )[0].data) if self.hass.config_entries.async_entries("sonos_color_sync") else self.config

    async def async_start(self) -> None:
        """Start the sync coordinator."""
        _LOGGER.info("Sonos Color Sync coordinator starting")
        self._update_task = asyncio.create_task(self._sync_loop())

    async def async_stop(self) -> None:
        """Stop the sync coordinator."""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        _LOGGER.info("Sonos Color Sync coordinator stopped")

    async def _sync_loop(self) -> None:
        """Main sync loop."""
        while True:
            try:
                # Check if enabled
                if not self.enabled:
                    if self.was_syncing:
                        await self.async_restore_lights()
                        self.was_syncing = False
                        self._save_state()
                    
                    await asyncio.sleep(self.config.get(CONF_POLL_INTERVAL, 5))
                    continue

                # Get Sonos entity state
                sonos_entity = self.config.get(CONF_SONOS_ENTITY)
                state = self.hass.states.get(sonos_entity)
                
                if not state or state.state != "playing":
                    # Music stopped - restore scene
                    if self.was_playing and self.was_syncing:
                        _LOGGER.info("Music stopped - restoring previous scene")
                        await self.async_restore_lights()
                        self.was_syncing = False
                        self._save_state()
                    
                    self.was_playing = False
                    await asyncio.sleep(self.config.get(CONF_POLL_INTERVAL, 5))
                    continue

                self.was_playing = True
                self.was_syncing = True
                self._save_state()

                # Get album art URL
                entity_picture = state.attributes.get("entity_picture")
                if not entity_picture:
                    await asyncio.sleep(self.config.get(CONF_POLL_INTERVAL, 5))
                    continue

                # Construct full URL if relative
                if entity_picture.startswith("/"):
                    entity_picture = f"{self.hass.config.internal_url}{entity_picture}"

                # Check if track changed
                track_id = state.attributes.get("media_content_id", entity_picture)
                if track_id == self.last_track_id:
                    await asyncio.sleep(self.config.get(CONF_POLL_INTERVAL, 5))
                    continue

                self.last_track_id = track_id
                title = state.attributes.get("title", "Unknown")
                _LOGGER.info(f"New track: {title}")

                # Extract colors
                colors = await self._fetch_and_extract_colors(entity_picture)
                if not colors:
                    _LOGGER.warning("No colors extracted")
                    await asyncio.sleep(self.config.get(CONF_POLL_INTERVAL, 5))
                    continue

                # Update Hue lights
                await self._update_hue_lights(colors)

            except Exception as e:
                _LOGGER.error(f"Sync error: {e}")

            await asyncio.sleep(self.config.get(CONF_POLL_INTERVAL, 5))

    async def _fetch_and_extract_colors(
        self, image_url: str
    ) -> List[Tuple[int, int, int]]:
        """Fetch and extract colors from image."""
        cache_enabled = self.config.get(CONF_CACHE_ENABLED, True)
        color_count = self.config.get(CONF_COLOR_COUNT, 3)
        filter_dull = self.config.get(CONF_FILTER_DULL, True)

        # Check cache
        if cache_enabled:
            cached = await self._get_cached_colors(image_url)
            if cached:
                return cached

        try:
            # Fetch image
            response = await asyncio.to_thread(
                requests.get, image_url, timeout=10
            )
            if response.status_code != 200:
                return []

            img = Image.open(BytesIO(response.content))
            img = img.convert("RGB")
            img.thumbnail((150, 150))

            # Extract colors
            colors = await asyncio.to_thread(
                self._extract_from_image, img, color_count, filter_dull
            )

            # Cache
            if cache_enabled:
                await self._cache_colors(image_url, colors)

            return colors
        except Exception as e:
            _LOGGER.error(f"Failed to extract colors: {e}")
            return []

    @staticmethod
    def _extract_from_image(
        img: Image.Image, color_count: int = 3, filter_dull: bool = True
    ) -> List[Tuple[int, int, int]]:
        """Extract dominant colors using K-means."""
        try:
            img_array = np.array(img)
            pixels = img_array.reshape(-1, 3)

            kmeans = KMeans(
                n_clusters=min(color_count, len(pixels)),
                random_state=42,
                n_init=10,
            )
            kmeans.fit(pixels)

            colors = kmeans.cluster_centers_.astype(int)

            if filter_dull:
                colors = SonosColorSyncCoordinator._filter_dull_colors(colors)

            return [tuple(c) for c in colors[:color_count]]
        except Exception as e:
            _LOGGER.error(f"Color extraction error: {e}")
            return []

    @staticmethod
    def _filter_dull_colors(colors: np.ndarray, threshold: int = 40) -> np.ndarray:
        """Remove near-black and near-white colors."""
        filtered = []
        for color in colors:
            r, g, b = color
            brightness = (r + g + b) / 3
            if threshold < brightness < 255 - threshold:
                filtered.append(color)
        return np.array(filtered) if filtered else colors

    async def _get_cached_colors(
        self, image_url: str
    ) -> Optional[List[Tuple[int, int, int]]]:
        """Get colors from cache."""
        cache_key = hashlib.md5(image_url.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                async with aiofiles.open(cache_file) as f:
                    data = json.loads(await f.read())
                    return [tuple(c) for c in data.get("colors", [])]
            except Exception as e:
                _LOGGER.warning(f"Cache read error: {e}")
        return None

    async def _cache_colors(
        self, image_url: str, colors: List[Tuple[int, int, int]]
    ) -> None:
        """Cache extracted colors."""
        cache_key = hashlib.md5(image_url.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            async with aiofiles.open(cache_file, "w") as f:
                await f.write(
                    json.dumps({"url": image_url, "colors": colors})
                )
        except Exception as e:
            _LOGGER.warning(f"Cache write error: {e}")

    async def _update_hue_lights(self, colors: List[Tuple[int, int, int]]) -> None:
        """Update Hue lights with colors."""
        try:
            bridge_ip = self.config.get(CONF_HUE_BRIDGE_IP)
            app_key = self.config.get(CONF_HUE_APP_KEY)
            light_group = self.config.get(CONF_LIGHT_GROUP, "")
            transition_time = self.config.get(CONF_TRANSITION_TIME, 2)

            if not bridge_ip or not app_key:
                _LOGGER.warning("Hue Bridge not configured")
                return

            # Get light groups
            groups = await self._get_hue_groups()
            if light_group:
                groups = [g for g in groups if g["name"].lower() == light_group.lower()]

            if not groups:
                _LOGGER.warning("No light groups found")
                return

            # Get lights in groups
            all_lights = set()
            for group in groups:
                url = f"http://{bridge_ip}/api/{app_key}/groups/{group['id']}"
                response = await asyncio.to_thread(requests.get, url, timeout=5)
                if response.status_code == 200:
                    group_data = response.json()
                    all_lights.update(group_data.get("lights", []))

            # Save current state before syncing
            for light_id in all_lights:
                if light_id not in self.previous_scenes:
                    state = await self._get_hue_light_state(light_id)
                    if state:
                        self.previous_scenes[light_id] = state
                        self._save_state()

            # Set colors on lights
            lights_list = list(all_lights)
            for idx, light_id in enumerate(lights_list):
                color_idx = idx % len(colors)
                await self._set_hue_light_color(
                    light_id, colors[color_idx], transition_time
                )

            _LOGGER.info(f"Updated {len(lights_list)} lights with {len(colors)} colors")
        except Exception as e:
            _LOGGER.error(f"Failed to update Hue lights: {e}")

    async def async_restore_lights(self) -> None:
        """Restore lights to previous state."""
        try:
            bridge_ip = self.config.get(CONF_HUE_BRIDGE_IP)
            app_key = self.config.get(CONF_HUE_APP_KEY)

            if not bridge_ip or not app_key:
                return

            restored = 0
            for light_id, scene in self.previous_scenes.items():
                if await self._restore_hue_light_state(light_id, scene):
                    restored += 1

            _LOGGER.info(f"Restored {restored} lights to previous state")
        except Exception as e:
            _LOGGER.error(f"Failed to restore lights: {e}")

    async def _get_hue_light_state(self, light_id: str) -> Optional[Dict]:
        """Get current Hue light state."""
        bridge_ip = self.config.get(CONF_HUE_BRIDGE_IP)
        app_key = self.config.get(CONF_HUE_APP_KEY)

        try:
            url = f"http://{bridge_ip}/api/{app_key}/lights/{light_id}"
            response = await asyncio.to_thread(requests.get, url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                state = data.get("state", {})
                return {
                    "xy": state.get("xy"),
                    "bri": state.get("bri"),
                    "on": state.get("on"),
                    "ct": state.get("ct"),
                    "hue": state.get("hue"),
                    "sat": state.get("sat"),
                }
            return None
        except Exception as e:
            _LOGGER.error(f"Failed to get light state: {e}")
            return None

    async def _set_hue_light_color(
        self, light_id: str, rgb: Tuple[int, int, int], transition_time: int = 2
    ) -> bool:
        """Set Hue light color."""
        bridge_ip = self.config.get(CONF_HUE_BRIDGE_IP)
        app_key = self.config.get(CONF_HUE_APP_KEY)

        try:
            # Convert RGB to XY
            r, g, b = [x / 255.0 for x in rgb]
            r = pow((r + 0.055) / 1.055, 2.4) if r > 0.04045 else r / 12.92
            g = pow((g + 0.055) / 1.055, 2.4) if g > 0.04045 else g / 12.92
            b = pow((b + 0.055) / 1.055, 2.4) if b > 0.04045 else b / 12.92

            x = r * 0.664511 + g * 0.154324 + b * 0.162028
            y = r * 0.283881 + g * 0.668433 + b * 0.047685
            z = r * 0.000088 + g * 0.072310 + b * 0.986039

            xy = [0.3, 0.3] if x + y + z == 0 else [x / (x + y + z), y / (x + y + z)]
            brightness = int(max(r, g, b) * 254)

            url = f"http://{bridge_ip}/api/{app_key}/lights/{light_id}/state"
            payload = {
                "xy": xy,
                "bri": brightness,
                "transitiontime": transition_time * 10,
            }

            response = await asyncio.to_thread(
                requests.put, url, json=payload, timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            _LOGGER.error(f"Failed to set light color: {e}")
            return False

    async def _restore_hue_light_state(self, light_id: str, scene: Dict) -> bool:
        """Restore Hue light to previous state."""
        bridge_ip = self.config.get(CONF_HUE_BRIDGE_IP)
        app_key = self.config.get(CONF_HUE_APP_KEY)

        try:
            url = f"http://{bridge_ip}/api/{app_key}/lights/{light_id}/state"
            payload = {"transitiontime": 20}

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
            if "on" in scene:
                payload["on"] = scene["on"]

            response = await asyncio.to_thread(
                requests.put, url, json=payload, timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            _LOGGER.error(f"Failed to restore light state: {e}")
            return False

    async def _get_hue_groups(self) -> List[Dict]:
        """Get available Hue light groups."""
        bridge_ip = self.config.get(CONF_HUE_BRIDGE_IP)
        app_key = self.config.get(CONF_HUE_APP_KEY)

        try:
            url = f"http://{bridge_ip}/api/{app_key}/groups"
            response = await asyncio.to_thread(requests.get, url, timeout=5)
            if response.status_code == 200:
                groups = response.json()
                return [{"id": k, "name": v.get("name")} for k, v in groups.items()]
            return []
        except Exception as e:
            _LOGGER.error(f"Failed to get light groups: {e}")
            return []

    async def async_clear_cache(self) -> None:
        """Clear the album art cache."""
        try:
            import shutil
            await asyncio.to_thread(shutil.rmtree, self.cache_dir)
            self.cache_dir.mkdir(exist_ok=True)
            _LOGGER.info("Cache cleared")
        except Exception as e:
            _LOGGER.error(f"Failed to clear cache: {e}")
