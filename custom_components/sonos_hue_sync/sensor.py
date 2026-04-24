from __future__ import annotations

from homeassistant.components.sensor import SensorEntity

from .const import ATTR_HEX_COLORS, DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SonosHueSyncPaletteSensor(coordinator, entry)], True)

class SonosHueSyncPaletteSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Palette"

    def __init__(self, coordinator, entry):
        self._coordinator = coordinator
        self._entry = entry
        self._remove_listener = None
        self._attr_unique_id = f"{entry.entry_id}_palette"

    async def async_added_to_hass(self):
        self._remove_listener = self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        if self._remove_listener:
            self._remove_listener()

    @property
    def native_value(self):
        colors = self._coordinator.palette_attributes.get(ATTR_HEX_COLORS, [])
        return f"{len(colors)} colors" if colors else "unknown"

    @property
    def extra_state_attributes(self):
        return self._coordinator.palette_attributes

    @property
    def icon(self):
        return "mdi:palette"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}, "name": self._entry.title or "Sonos Hue Sync"}
