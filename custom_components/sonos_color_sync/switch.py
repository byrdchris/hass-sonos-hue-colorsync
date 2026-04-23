"""Switch platform for Sonos Color Sync."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    
    async_add_entities([
        SonosColorSyncSwitch(coordinator, config_entry)
    ])


class SonosColorSyncSwitch(SwitchEntity):
    """Switch to enable/disable Sonos Color Sync."""

    def __init__(self, coordinator, config_entry):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._attr_name = "Sonos Color Sync"
        self._attr_unique_id = f"{DOMAIN}_switch_{config_entry.entry_id}"
        self._attr_icon = "mdi:palette"

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        return self.coordinator.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        self.coordinator.set_enabled(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        self.coordinator.set_enabled(False)
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "Sonos Color Sync",
            "manufacturer": "Sonos Color Sync",
        }
