from __future__ import annotations

import logging
import voluptuous as vol

from .const import (
    DOMAIN,
    SERVICE_APPLY_LAST_PALETTE,
    SERVICE_DISABLE,
    SERVICE_ENABLE,
    SERVICE_EXTRACT_NOW,
    SERVICE_TEST_COLOR,
    SERVICE_TEST_RAINBOW,
    SERVICE_SHOW_HELP,
)

_LOGGER = logging.getLogger(__name__)

TEST_COLOR_SCHEMA = vol.Schema({
    vol.Required("r"): vol.All(int, vol.Range(min=0, max=255)),
    vol.Required("g"): vol.All(int, vol.Range(min=0, max=255)),
    vol.Required("b"): vol.All(int, vol.Range(min=0, max=255)),
})

async def async_setup_services(hass):
    if hass.data.get(f"{DOMAIN}_services_registered"):
        return

    async def enable(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_enable()

    async def disable(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_disable()

    async def apply_last_palette(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_apply_last_palette()

    async def test_color(call):
        rgb = [call.data["r"], call.data["g"], call.data["b"]]
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_test_color(rgb)

    async def extract_now(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_process_current_state(reason="extract_now_service", bypass_cache=True, force_apply=True)


    async def show_help(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_show_help()

    async def test_rainbow(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_test_rainbow()

    hass.services.async_register(DOMAIN, SERVICE_ENABLE, enable)
    hass.services.async_register(DOMAIN, SERVICE_DISABLE, disable)
    hass.services.async_register(DOMAIN, SERVICE_APPLY_LAST_PALETTE, apply_last_palette)
    hass.services.async_register(DOMAIN, SERVICE_TEST_COLOR, test_color, schema=TEST_COLOR_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_EXTRACT_NOW, extract_now)
    hass.services.async_register(DOMAIN, SERVICE_TEST_RAINBOW,
    SERVICE_SHOW_HELP, test_rainbow)
    hass.data[f"{DOMAIN}_services_registered"] = True
    _LOGGER.info("Registered Sonos Hue Sync services")
