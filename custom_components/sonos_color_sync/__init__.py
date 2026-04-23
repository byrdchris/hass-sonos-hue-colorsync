"""Sonos Color Sync integration for Home Assistant."""
import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "sonos_color_sync"
VERSION: Final = "2.0.0"

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration from YAML (legacy)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sonos Color Sync from config entry."""
    from .coordinator import SonosColorSyncCoordinator
    from .config_flow import SonosColorSyncOptionsFlow
    
    hass.data.setdefault(DOMAIN, {})
    
    coordinator = SonosColorSyncCoordinator(hass, dict(entry.data))
    await coordinator.async_config_update()
    await coordinator.async_start()
    
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }
    
    # Register options flow
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    async def toggle_service(call: ServiceCall) -> None:
        """Handle toggle service call."""
        enabled = call.data.get("enabled")
        coordinator.set_enabled(enabled)
    
    async def restore_service(call: ServiceCall) -> None:
        """Handle restore service call."""
        await coordinator.async_restore_lights()
    
    hass.services.async_register(
        DOMAIN,
        "toggle",
        toggle_service,
        schema=vol.Schema(
            {
                vol.Optional("enabled"): cv.boolean,
            }
        ),
    )
    
    hass.services.async_register(
        DOMAIN,
        "restore_lights",
        restore_service,
    )
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
