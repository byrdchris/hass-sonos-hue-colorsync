from __future__ import annotations
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SonosHueSyncEnableSwitch(coordinator, entry)], True)

class SonosHueSyncEnableSwitch(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        self._coordinator = coordinator
        self._entry = entry
        self._remove_listener = None
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_name = "Enabled"

    async def async_added_to_hass(self):
        self._remove_listener = self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        if self._remove_listener:
            self._remove_listener()

    @property
    def is_on(self):
        return self._coordinator.enabled

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.title or "Sonos Hue Sync",
            "manufacturer": "Custom",
            "model": "Sonos Hue Sync",
        }

    async def async_turn_on(self, **kwargs):
        await self._coordinator.async_enable()

    async def async_turn_off(self, **kwargs):
        await self._coordinator.async_disable()
