from __future__ import annotations

import logging
from homeassistant.helpers.event import async_track_state_change_event

from .cache import PaletteCache
from .const import (
    CONF_CACHE,
    CONF_LIGHT_GROUP,
    CONF_SONOS_ENTITY,
)
from .hue_controller import apply_palette, restore_scene, snapshot_scene
from .palette import extract_palette

_LOGGER = logging.getLogger(__name__)

class SonosHueCoordinator:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.scene = None
        self.enabled = True
        self._remove_listener = None
        self.cache = PaletteCache() if self.config.get(CONF_CACHE, True) else None

    @property
    def config(self):
        return {**self.entry.data, **self.entry.options}

    @property
    def sonos_entity(self):
        return self.config[CONF_SONOS_ENTITY]

    @property
    def light_group(self):
        return self.config[CONF_LIGHT_GROUP]

    async def async_setup(self):
        await self.async_refresh_listener()

    async def async_unload(self):
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

    async def async_refresh_listener(self):
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

        self._remove_listener = async_track_state_change_event(
            self.hass, [self.sonos_entity], self._handle
        )

    async def async_update_config(self):
        self.cache = PaletteCache() if self.config.get(CONF_CACHE, True) else None
        await self.async_refresh_listener()

    async def _handle(self, event):
        state = event.data.get("new_state")
        if not state or not self.enabled:
            return

        if state.state == "playing":
            if not self.scene:
                self.scene = await snapshot_scene(self.hass, self.light_group)

            art = state.attributes.get("entity_picture")
            if not art:
                return

            if self.cache and self.cache.exists(art):
                palette = self.cache.get(art)
            else:
                palette = await extract_palette(art, self.config)
                if self.cache:
                    self.cache.set(art, palette)

            await apply_palette(self.hass, self.light_group, palette, self.config)

        elif state.state in ["paused", "idle", "off"]:
            await self._handle_stop()

    async def _handle_stop(self):
        if self.scene:
            await restore_scene(self.hass, self.scene)
            self.scene = None

    async def async_enable(self):
        self.enabled = True

    async def async_disable(self):
        self.enabled = False
        await self._handle_stop()
