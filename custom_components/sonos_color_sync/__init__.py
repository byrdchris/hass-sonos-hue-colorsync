"""Sonos Color Sync integration for Home Assistant."""
import logging
from typing import Final

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "sonos_color_sync"
VERSION: Final = "2.0.0"

CONF_SONOS_ENTITY = "sonos_entity_id"
CONF_HUE_BRIDGE_IP = "hue_bridge_ip"
CONF_HUE_APP_KEY = "hue_app_key"
CONF_POLL_INTERVAL = "poll_interval"
CONF_COLOR_COUNT = "color_count"
CONF_TRANSITION_TIME = "transition_time"
CONF_FILTER_DULL = "filter_dull_colors"
CONF_CACHE_ENABLED = "cache_enabled"
CONF_LIGHT_GROUP = "hue_light_group"

SERVICE_TOGGLE = "toggle"
SERVICE_RESTORE = "restore_lights"

PLATFORMS: list[Platform] = [Platform.SWITCH]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_SONOS_ENTITY): cv.entity_id,
                        vol.Required(CONF_HUE_BRIDGE_IP): cv.string,
                        vol.Optional(CONF_HUE_APP_KEY, default=""): cv.string,
                        vol.Optional(CONF_POLL_INTERVAL, default=5): cv.positive_int,
                        vol.Optional(CONF_COLOR_COUNT, default=3): vol.Range(
                            min=1, max=10
                        ),
                        vol.Optional(CONF_TRANSITION_TIME, default=2): vol.Range(
                            min=0, max=10
                        ),
                        vol.Optional(CONF_FILTER_DULL, default=True): cv.boolean,
                        vol.Optional(CONF_CACHE_ENABLED, default=True): cv.boolean,
                        vol.Optional(CONF_LIGHT_GROUP, default=""): cv.string,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration from YAML (legacy)."""
    hass.data.setdefault(DOMAIN, {})
    
    if DOMAIN not in config:
        return True
    
    # Store YAML config for later use
    hass.data[DOMAIN]["yaml_config"] = config[DOMAIN]
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sonos Color Sync from config entry."""
    from .coordinator import SonosColorSyncCoordinator
    
    hass.data.setdefault(DOMAIN, {})
    
    coordinator = SonosColorSyncCoordinator(hass, dict(entry.data))
    await coordinator.async_config_update()
    
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "unsub_reload": entry.add_update_listener(async_reload_entry),
    }
    
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
        SERVICE_TOGGLE,
        toggle_service,
        schema=vol.Schema(
            {
                vol.Optional("enabled"): cv.boolean,
            }
        ),
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTORE,
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
