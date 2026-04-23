"""Sonos Color Sync — Home Assistant custom integration."""
import logging
from typing import Final

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "sonos_color_sync"
PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    from .coordinator import SonosColorSyncCoordinator

    hass.data.setdefault(DOMAIN, {})

    coordinator = SonosColorSyncCoordinator(hass, dict(entry.data))
    await coordinator.async_config_update()
    await coordinator.async_start()

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    # Reload when options are saved
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Services
    async def _toggle(call: ServiceCall) -> None:
        coordinator.set_enabled(call.data.get("enabled"))

    async def _restore(call: ServiceCall) -> None:
        await coordinator.async_restore_lights()

    hass.services.async_register(
        DOMAIN, "toggle", _toggle,
        schema=vol.Schema({vol.Optional("enabled"): cv.boolean}),
    )
    hass.services.async_register(DOMAIN, "restore_lights", _restore)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["coordinator"].async_stop()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
