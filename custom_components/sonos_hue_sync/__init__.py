from __future__ import annotations

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_LIGHT_ENTITIES, CONF_LIGHT_GROUP, DOMAIN, PLATFORMS
from .coordinator import SonosHueCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info("Migrating Sonos Hue Sync config entry from version %s", entry.version)
    data = dict(entry.data)
    options = dict(entry.options)
    if CONF_LIGHT_ENTITIES not in data and data.get(CONF_LIGHT_GROUP):
        data[CONF_LIGHT_ENTITIES] = [data[CONF_LIGHT_GROUP]]
    if CONF_LIGHT_ENTITIES not in options and options.get(CONF_LIGHT_GROUP):
        options[CONF_LIGHT_ENTITIES] = [options[CONF_LIGHT_GROUP]]
    hass.config_entries.async_update_entry(entry, data=data, options=options, version=1)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.info("Setting up Sonos Hue Sync entry %s", entry.entry_id)
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
