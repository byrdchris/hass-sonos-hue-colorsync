"""Coordinator for Sonos Color Sync."""
import asyncio
import hashlib
import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CACHE_ENABLED,
    CONF_COLOR_COUNT,
    CONF_FILTER_DULL,
    CONF_HUE_LIGHTS,
    CONF_POLL_INTERVAL,
    CONF_SONOS_ENTITY,
    CONF_TRANSITION_TIME,
)

_LOGGER = logging.getLogger(__name__)

# Lazy-loaded heavy dependencies
_np = None
_Image = None
_KMeans = None


def _lazy_imports():
    """Import heavy dependencies once."""
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
    """Manages Sonos → album art → Hue light color sync."""

    def __init__(self, hass: HomeAssistant, config: Dict) -> None:
        self.hass = hass
        self.config = config
        self.enabled = True
        self.was_playing = False
        self.last_track_id: Optional[str] = None
        self.previous_states: Dict[str, Dict] = {}  # entity_id → saved light state
        self.was_syncing = False
        self._update_task: Optional[asyncio.Task] = None

        # Persistence paths
        self.config_dir = Path(hass.config.config_dir) / "sonos_color_sync"
        self.cache_dir = self.config_dir / "cache"
        self.state_file = self.config_dir / "state.json"
        self.config_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)

        self._load_state()

    # ------------------------------------------------------------------ #
    # State persistence                                                    #
    # ------------------------------------------------------------------ #

    def _load_state(self) -> None:
        try:
            if self.state_file.exists():
                saved = json.loads(self.state_file.read_text())
                self.enabled = saved.get("enabled", True)
                self.previous_states = saved.get("previous_states", {})
                self.was_syncing = saved.get("was_syncing", False)
                _LOGGER.debug("State loaded: enabled=%s", self.enabled)
        except Exception as e:
            _LOGGER.warning("Could not load state: %s", e)

    def _save_state(self) -> None:
        try:
            self.state_file.write_text(json.dumps({
                "enabled": self.enabled,
                "previous_states": self.previous_states,
                "was_syncing": self.was_syncing,
            }, indent=2))
        except Exception as e:
            _LOGGER.warning("Could not save state: %s", e)

    # ------------------------------------------------------------------ #
    # Public controls                                                      #
    # ------------------------------------------------------------------ #

    def set_enabled(self, enabled: Optional[bool] = None) -> None:
        """Enable or disable the sync. Pass None to toggle."""
        self.enabled = enabled if enabled is not None else not self.enabled
        self._save_state()
        _LOGGER.info("Sonos Color Sync %s", "enabled" if self.enabled else "disabled")
        if not self.enabled and self.was_syncing:
            asyncio.create_task(self.async_restore_lights())

    async def async_config_update(self) -> None:
        """Pull latest config from the config entry."""
        entries = self.hass.config_entries.async_entries("sonos_color_sync")
        if entries:
            self.config = dict(entries[0].data)

    async def async_start(self) -> None:
        _LOGGER.info("Sonos Color Sync starting")
        self._update_task = asyncio.create_task(self._sync_loop())

    async def async_stop(self) -> None:
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        _LOGGER.info("Sonos Color Sync stopped")

    # ------------------------------------------------------------------ #
    # Main loop                                                            #
    # ------------------------------------------------------------------ #

    async def _sync_loop(self) -> None:
        try:
            await asyncio.to_thread(_lazy_imports)
        except Exception as e:
            _LOGGER.error("Failed to import image processing packages: %s", e)
            return

        while True:
            try:
                await self.async_config_update()
                poll = int(self.config.get(CONF_POLL_INTERVAL, 5))

                if not self.enabled:
                    if self.was_syncing:
                        await self.async_restore_lights()
                        self.was_syncing = False
                        self._save_state()
                    await asyncio.sleep(poll)
                    continue

                sonos_entity = self.config.get(CONF_SONOS_ENTITY)
                state = self.hass.states.get(sonos_entity)

                if not state or state.state != "playing":
                    if self.was_playing and self.was_syncing:
                        _LOGGER.info("Music stopped — restoring lights")
                        await self.async_restore_lights()
                        self.was_syncing = False
                        self._save_state()
                    self.was_playing = False
                    await asyncio.sleep(poll)
                    continue

                # Music is playing
                if not self.was_playing:
                    # Snapshot lights the moment music starts
                    await self._snapshot_light_states()

                self.was_playing = True
                self.was_syncing = True
                self._save_state()

                entity_picture = state.attributes.get("entity_picture")
                if not entity_picture:
                    await asyncio.sleep(poll)
                    continue

                if entity_picture.startswith("/"):
                    base = (self.hass.config.internal_url or "http://localhost:8123").rstrip("/")
                    entity_picture = f"{base}{entity_picture}"

                track_id = state.attributes.get("media_content_id") or entity_picture
                if track_id == self.last_track_id:
                    await asyncio.sleep(poll)
                    continue

                self.last_track_id = track_id
                title = state.attributes.get("media_title", "Unknown")
                artist = state.attributes.get("media_artist", "")
                _LOGGER.info("New track: %s — %s", title, artist)

                colors = await self._fetch_and_extract_colors(entity_picture)
                if colors:
                    await self._apply_colors_to_lights(colors)
                else:
                    _LOGGER.warning("No colors extracted from album art")

            except asyncio.CancelledError:
                raise
            except Exception as e:
                _LOGGER.error("Sync loop error: %s", e)

            await asyncio.sleep(int(self.config.get(CONF_POLL_INTERVAL, 5)))

    # ------------------------------------------------------------------ #
    # Light state snapshot & restore (via HA light domain)               #
    # ------------------------------------------------------------------ #

    async def _snapshot_light_states(self) -> None:
        """Save current state of all configured lights."""
        lights = self.config.get(CONF_HUE_LIGHTS, [])
        self.previous_states = {}

        for entity_id in lights:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue

            saved = {
                "state": state.state,
                "brightness": state.attributes.get(ATTR_BRIGHTNESS),
                "hs_color": state.attributes.get(ATTR_HS_COLOR),
                "xy_color": state.attributes.get(ATTR_XY_COLOR),
                "color_temp": state.attributes.get(ATTR_COLOR_TEMP),
                "color_mode": state.attributes.get("color_mode"),
            }
            self.previous_states[entity_id] = saved
            _LOGGER.debug("Snapshotted %s: %s", entity_id, saved)

        self._save_state()
        _LOGGER.info("Snapshotted %d light states", len(self.previous_states))

    async def async_restore_lights(self) -> None:
        """Restore all lights to their snapshotted state."""
        if not self.previous_states:
            _LOGGER.info("No saved light states to restore")
            return

        transition = int(self.config.get(CONF_TRANSITION_TIME, 2))

        for entity_id, saved in self.previous_states.items():
            try:
                if saved.get("state") == STATE_OFF:
                    await self.hass.services.async_call(
                        "light", "turn_off",
                        {ATTR_ENTITY_ID: entity_id, ATTR_TRANSITION: transition},
                        blocking=True,
                    )
                else:
                    service_data: Dict = {
                        ATTR_ENTITY_ID: entity_id,
                        ATTR_TRANSITION: transition,
                    }
                    if saved.get("brightness") is not None:
                        service_data[ATTR_BRIGHTNESS] = saved["brightness"]

                    # Restore color in the same mode it was in
                    color_mode = saved.get("color_mode")
                    if color_mode == ColorMode.COLOR_TEMP and saved.get("color_temp"):
                        service_data[ATTR_COLOR_TEMP] = saved["color_temp"]
                    elif saved.get("hs_color"):
                        service_data[ATTR_HS_COLOR] = saved["hs_color"]
                    elif saved.get("xy_color"):
                        service_data[ATTR_XY_COLOR] = saved["xy_color"]
                    elif saved.get("color_temp"):
                        service_data[ATTR_COLOR_TEMP] = saved["color_temp"]

                    await self.hass.services.async_call(
                        "light", SERVICE_TURN_ON,
                        service_data,
                        blocking=True,
                    )
                _LOGGER.debug("Restored %s", entity_id)
            except Exception as e:
                _LOGGER.error("Failed to restore %s: %s", entity_id, e)

        _LOGGER.info("Restored %d lights", len(self.previous_states))
        self.previous_states = {}
        self._save_state()

    # ------------------------------------------------------------------ #
    # Apply colors to lights                                               #
    # ------------------------------------------------------------------ #

    async def _apply_colors_to_lights(
        self, colors: List[Tuple[int, int, int]]
    ) -> None:
        """Send extracted colors to configured HA light entities."""
        lights = self.config.get(CONF_HUE_LIGHTS, [])
        transition = int(self.config.get(CONF_TRANSITION_TIME, 2))

        if not lights:
            _LOGGER.warning("No lights configured")
            return

        for i, entity_id in enumerate(lights):
            rgb = colors[i % len(colors)]
            r, g, b = rgb

            # Convert RGB → HS for HA light service
            import colorsys
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            hs_color = (h * 360, s * 100)
            brightness = int(v * 255)

            service_data = {
                ATTR_ENTITY_ID: entity_id,
                ATTR_HS_COLOR: hs_color,
                ATTR_BRIGHTNESS: brightness,
                ATTR_TRANSITION: transition,
            }

            try:
                await self.hass.services.async_call(
                    "light", SERVICE_TURN_ON,
                    service_data,
                    blocking=True,
                )
            except Exception as e:
                _LOGGER.error("Failed to set color on %s: %s", entity_id, e)

        _LOGGER.debug("Applied %d colors to %d lights", len(colors), len(lights))

    # ------------------------------------------------------------------ #
    # Color extraction                                                     #
    # ------------------------------------------------------------------ #

    async def _fetch_and_extract_colors(
        self, image_url: str
    ) -> List[Tuple[int, int, int]]:
        """Fetch album art and extract dominant colors."""
        cache_enabled = self.config.get(CONF_CACHE_ENABLED, True)
        color_count = int(self.config.get(CONF_COLOR_COUNT, 3))
        filter_dull = self.config.get(CONF_FILTER_DULL, True)

        if cache_enabled:
            cached = self._get_cached_colors(image_url)
            if cached:
                _LOGGER.debug("Using cached colors for %s", image_url)
                return cached

        try:
            session = self.hass.helpers.aiohttp_client.async_get_clientsession()
            async with session.get(image_url, timeout=10) as response:
                if response.status != 200:
                    _LOGGER.warning("Album art fetch returned HTTP %s", response.status)
                    return []
                image_bytes = await response.read()

            colors = await asyncio.to_thread(
                _extract_colors_from_bytes, image_bytes, color_count, filter_dull
            )

            if cache_enabled and colors:
                self._cache_colors(image_url, colors)

            return colors
        except Exception as e:
            _LOGGER.error("Failed to fetch/extract colors from %s: %s", image_url, e)
            return []

    def _get_cached_colors(self, image_url: str) -> Optional[List[Tuple[int, int, int]]]:
        cache_key = hashlib.md5(image_url.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                return [tuple(c) for c in data.get("colors", [])]
            except Exception:
                pass
        return None

    def _cache_colors(self, image_url: str, colors: List[Tuple[int, int, int]]) -> None:
        cache_key = hashlib.md5(image_url.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            cache_file.write_text(json.dumps({"url": image_url, "colors": colors}))
        except Exception as e:
            _LOGGER.warning("Cache write failed: %s", e)

    async def async_clear_cache(self) -> None:
        import shutil
        await asyncio.to_thread(shutil.rmtree, self.cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        _LOGGER.info("Cache cleared")


# ------------------------------------------------------------------ #
# Color extraction (runs in thread)                                   #
# ------------------------------------------------------------------ #

def _extract_colors_from_bytes(
    image_bytes: bytes, color_count: int, filter_dull: bool
) -> List[Tuple[int, int, int]]:
    """Extract dominant colors via K-means. Runs in a thread."""
    _lazy_imports()
    np = _np
    Image = _Image
    KMeans = _KMeans

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((150, 150))
    pixels = np.array(img).reshape(-1, 3).astype(float)

    # Request extra clusters so we have room to filter
    n_clusters = min(color_count + 4, len(pixels))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    kmeans.fit(pixels)

    # Sort by cluster size (most dominant first)
    labels = kmeans.labels_
    centers = kmeans.cluster_centers_
    counts = np.bincount(labels)
    order = np.argsort(-counts)
    centers = centers[order]

    if filter_dull:
        filtered = []
        for color in centers:
            brightness = int(color.sum()) // 3
            saturation = int(color.max()) - int(color.min())
            # Keep colors that aren't too dark, too bright, or too grey
            if 35 < brightness < 220 and saturation > 30:
                filtered.append(color)
        if filtered:
            centers = np.array(filtered)

    result = [tuple(int(v) for v in c) for c in centers[:color_count]]
    _LOGGER.debug("Extracted colors: %s", result)
    return result
