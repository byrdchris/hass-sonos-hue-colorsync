"""Coordinator for Sonos Color Sync."""
import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from io import BytesIO

from homeassistant.core import HomeAssistant

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

# These are lazily imported so HA can load the integration even if
# they take a moment to become available after install
_np = None
_Image = None
_KMeans = None


def _lazy_imports():
    """Import heavy dependencies lazily."""
    global _np, _Image, _KMeans
    if _np is None:
        import numpy as np
        _np = np
    if _Image is None:
        from PIL import Image
        _Image = Image
    if _KMeans is None:
        from sklearn.cluster import KMeans
        _KMeans = KMeans


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
                    _LOGGER.info("State loaded: enabled=%s", self.enabled)
        except Exception as e:
            _LOGGER.warning("Failed to load state: %s", e)

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
            _LOGGER.warning("Failed to save state: %s", e)

    def set_enabled(self, enabled: Optional[bool] = None) -> None:
        """Set enabled/disabled status."""
        if enabled is None:
            enabled = not self.enabled
        self.enabled = enabled
        self._save_state()
        if not enabled and self.was_syncing:
            asyncio.create_task(self.async_restore_lights())
        _LOGGER.info("Sonos Color Sync %s", "enabled" if enabled else "disabled")

    async def async_config_update(self) -> None:
        """Reload config from current config entry."""
        entries = self.hass.config_entries.async_entries("sonos_color_sync")
        if entries:
            self.config = dict(entries[0].data)

    async def async_start(self) -> None:
        """Start the sync loop."""
        _LOGGER.info("Sonos Color Sync coordinator starting")
        self._update_task = asyncio.create_task(self._sync_loop())

    async def async_stop(self) -> None:
        """Stop the sync loop."""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        _LOGGER.info("Sonos Color Sync coordinator stopped")

    async def _sync_loop(self) -> None:
        """Main polling loop."""
        # Ensure heavy packages are available before starting
        try:
            await asyncio.to_thread(_lazy_imports)
        except Exception as e:
            _LOGGER.error("Failed to import required packages: %s", e)
            return

        while True:
            try:
                # Reload config in case it changed
                await self.async_config_update()

                if not self.enabled:
                    if self.was_syncing:
                        await self.async_restore_lights()
                        self.was_syncing = False
                        self._save_state()
                    await asyncio.sleep(self.config.get(CONF_POLL_INTERVAL, 5))
                    continue

                sonos_entity = self.config.get(CONF_SONOS_ENTITY)
                state = self.hass.states.get(sonos_entity)

                if not state or state.state != "playing":
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

                entity_picture = state.attributes.get("entity_picture")
                if not entity_picture:
                    await asyncio.sleep(self.config.get(CONF_POLL_INTERVAL, 5))
                    continue

                # Build full URL for relative paths
                if entity_picture.startswith("/"):
                    base = self.hass.config.internal_url or "http://localhost:8123"
                    entity_picture = f"{base.rstrip('/')}{entity_picture}"

                # Skip if same track
                track_id = state.attributes.get("media_content_id") or entity_picture
                if track_id == self.last_track_id:
                    await asyncio.sleep(self.config.get(CONF_POLL_INTERVAL, 5))
                    continue

                self.last_track_id = track_id
                _LOGGER.info(
                    "New track: %s", state.attributes.get("media_title", "Unknown")
                )

                colors = await self._fetch_and_extract_colors(entity_picture)
                if colors:
                    await self._update_hue_lights(colors)
                else:
                    _LOGGER.warning("No colors extracted from album art")

            except asyncio.CancelledError:
                raise
            except Exception as e:
                _LOGGER.error("Sync loop error: %s", e)

            await asyncio.sleep(self.config.get(CONF_POLL_INTERVAL, 5))

    # ------------------------------------------------------------------ #
    # Color extraction                                                     #
    # ------------------------------------------------------------------ #

    async def _fetch_and_extract_colors(
        self, image_url: str
    ) -> List[Tuple[int, int, int]]:
        """Fetch image and extract dominant colors."""
        cache_enabled = self.config.get(CONF_CACHE_ENABLED, True)
        color_count = self.config.get(CONF_COLOR_COUNT, 3)
        filter_dull = self.config.get(CONF_FILTER_DULL, True)

        if cache_enabled:
            cached = self._get_cached_colors(image_url)
            if cached:
                return cached

        try:
            # Use HA's async session to fetch image
            session = self.hass.helpers.aiohttp_client.async_get_clientsession()
            async with session.get(image_url, timeout=10) as response:
                if response.status != 200:
                    _LOGGER.warning("Album art fetch returned %s", response.status)
                    return []
                image_bytes = await response.read()

            colors = await asyncio.to_thread(
                self._extract_colors_from_bytes, image_bytes, color_count, filter_dull
            )

            if cache_enabled and colors:
                self._cache_colors(image_url, colors)

            return colors
        except Exception as e:
            _LOGGER.error("Failed to fetch/extract colors: %s", e)
            return []

    @staticmethod
    def _extract_colors_from_bytes(
        image_bytes: bytes, color_count: int, filter_dull: bool
    ) -> List[Tuple[int, int, int]]:
        """Run in thread: extract dominant colors from raw image bytes."""
        _lazy_imports()
        np = _np
        Image = _Image
        KMeans = _KMeans

        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((150, 150))

        pixels = np.array(img).reshape(-1, 3)
        n_clusters = min(color_count + 2, len(pixels))  # extra clusters for filtering

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        kmeans.fit(pixels)

        colors = kmeans.cluster_centers_.astype(int)

        if filter_dull:
            filtered = []
            for color in colors:
                brightness = int(color.sum()) // 3
                if 40 < brightness < 215:
                    filtered.append(color)
            colors = np.array(filtered) if filtered else colors

        return [tuple(int(v) for v in c) for c in colors[:color_count]]

    def _get_cached_colors(
        self, image_url: str
    ) -> Optional[List[Tuple[int, int, int]]]:
        """Read cached colors synchronously."""
        cache_key = hashlib.md5(image_url.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                return [tuple(c) for c in data.get("colors", [])]
            except Exception as e:
                _LOGGER.warning("Cache read error: %s", e)
        return None

    def _cache_colors(
        self, image_url: str, colors: List[Tuple[int, int, int]]
    ) -> None:
        """Write cached colors synchronously."""
        cache_key = hashlib.md5(image_url.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            cache_file.write_text(json.dumps({"url": image_url, "colors": colors}))
        except Exception as e:
            _LOGGER.warning("Cache write error: %s", e)

    async def async_clear_cache(self) -> None:
        """Clear the album art cache."""
        import shutil
        await asyncio.to_thread(shutil.rmtree, self.cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        _LOGGER.info("Cache cleared")

    # ------------------------------------------------------------------ #
    # Hue Bridge                                                           #
    # ------------------------------------------------------------------ #

    async def _hue_get(self, path: str) -> Optional[dict]:
        """GET request to Hue Bridge."""
        bridge_ip = self.config.get(CONF_HUE_BRIDGE_IP)
        app_key = self.config.get(CONF_HUE_APP_KEY)
        if not bridge_ip or not app_key:
            return None
        try:
            session = self.hass.helpers.aiohttp_client.async_get_clientsession()
            async with session.get(
                f"http://{bridge_ip}/api/{app_key}/{path}", timeout=5
            ) as r:
                return await r.json() if r.status == 200 else None
        except Exception as e:
            _LOGGER.error("Hue GET %s failed: %s", path, e)
            return None

    async def _hue_put(self, path: str, payload: dict) -> bool:
        """PUT request to Hue Bridge."""
        bridge_ip = self.config.get(CONF_HUE_BRIDGE_IP)
        app_key = self.config.get(CONF_HUE_APP_KEY)
        if not bridge_ip or not app_key:
            return False
        try:
            session = self.hass.helpers.aiohttp_client.async_get_clientsession()
            async with session.put(
                f"http://{bridge_ip}/api/{app_key}/{path}",
                json=payload,
                timeout=5,
            ) as r:
                return r.status == 200
        except Exception as e:
            _LOGGER.error("Hue PUT %s failed: %s", path, e)
            return False

    async def _get_hue_groups(self) -> List[Dict]:
        """Return list of Hue light groups."""
        data = await self._hue_get("groups")
        if not data:
            return []
        return [{"id": k, "name": v.get("name", "")} for k, v in data.items()]

    async def _get_lights_for_group(self, group_id: str) -> List[str]:
        """Return light IDs for a group."""
        data = await self._hue_get(f"groups/{group_id}")
        return data.get("lights", []) if data else []

    async def _get_hue_light_state(self, light_id: str) -> Optional[Dict]:
        """Return current state of a light."""
        data = await self._hue_get(f"lights/{light_id}")
        if not data:
            return None
        s = data.get("state", {})
        return {k: s.get(k) for k in ("xy", "bri", "on", "ct", "hue", "sat")}

    async def _set_hue_color(
        self, light_id: str, rgb: Tuple[int, int, int], transition_time: int
    ) -> None:
        """Set a light to an RGB color."""
        r, g, b = (x / 255.0 for x in rgb)

        # Gamma correction (sRGB)
        def gc(v):
            return pow((v + 0.055) / 1.055, 2.4) if v > 0.04045 else v / 12.92

        r, g, b = gc(r), gc(g), gc(b)

        X = r * 0.664511 + g * 0.154324 + b * 0.162028
        Y = r * 0.283881 + g * 0.668433 + b * 0.047685
        Z = r * 0.000088 + g * 0.072310 + b * 0.986039
        total = X + Y + Z
        xy = [X / total, Y / total] if total else [0.3, 0.3]
        bri = max(1, int(max(r, g, b) * 254))

        await self._hue_put(
            f"lights/{light_id}/state",
            {"xy": xy, "bri": bri, "transitiontime": transition_time * 10},
        )

    async def _restore_hue_light(self, light_id: str, scene: Dict) -> None:
        """Restore a light to its saved state."""
        payload: Dict = {"transitiontime": 20}
        for key in ("xy", "bri", "ct", "hue", "sat", "on"):
            if scene.get(key) is not None:
                payload[key] = scene[key]
        await self._hue_put(f"lights/{light_id}/state", payload)

    async def _update_hue_lights(self, colors: List[Tuple[int, int, int]]) -> None:
        """Apply extracted colors to Hue lights."""
        light_group_name = self.config.get(CONF_LIGHT_GROUP, "")
        transition_time = self.config.get(CONF_TRANSITION_TIME, 2)

        groups = await self._get_hue_groups()
        if light_group_name:
            groups = [g for g in groups if g["name"].lower() == light_group_name.lower()]
        if not groups:
            _LOGGER.warning("No matching Hue light groups found")
            return

        all_lights: set = set()
        for group in groups:
            lights = await self._get_lights_for_group(group["id"])
            all_lights.update(lights)

        # Snapshot state before first sync
        for light_id in all_lights:
            if light_id not in self.previous_scenes:
                s = await self._get_hue_light_state(light_id)
                if s:
                    self.previous_scenes[light_id] = s
        self._save_state()

        # Assign colors round-robin
        lights_list = sorted(all_lights)
        for i, light_id in enumerate(lights_list):
            await self._set_hue_color(light_id, colors[i % len(colors)], transition_time)

        _LOGGER.info("Updated %d lights with %d colors", len(lights_list), len(colors))

    async def async_restore_lights(self) -> None:
        """Restore all lights to their saved state."""
        if not self.previous_scenes:
            _LOGGER.info("No saved scenes to restore")
            return
        count = 0
        for light_id, scene in self.previous_scenes.items():
            await self._restore_hue_light(light_id, scene)
            count += 1
        _LOGGER.info("Restored %d lights to previous state", count)
        # Clear scenes after restore so next play captures fresh state
        self.previous_scenes = {}
        self._save_state()
