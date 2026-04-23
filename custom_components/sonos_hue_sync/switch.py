from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities: AddEntitiesCallback):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SonosHueSyncEnableSwitch(coordinator, entry)], True)

class SonosHueSyncEnableSwitch(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_name = "Enabled"

    @property
    def is_on(self):
        return self._coordinator.enabled

    @property
    def available(self):
        return True

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
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._coordinator.async_disable()
        self.async_write_ha_state()
