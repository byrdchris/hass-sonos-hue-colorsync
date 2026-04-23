from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, PLATFORMS
from .coordinator import SonosHueCoordinator
from .services import async_setup_services

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    coordinator = SonosHueCoordinator(hass, entry)
    await coordinator.async_setup()
    await async_setup_services(hass)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_update_config()

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    coordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.async_unload()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
