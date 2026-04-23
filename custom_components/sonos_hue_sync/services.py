from __future__ import annotations

from .const import DOMAIN, SERVICE_DISABLE, SERVICE_ENABLE

async def async_setup_services(hass):
    if hass.data.get(f"{DOMAIN}_services_registered"):
        return

    async def enable(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_enable()

    async def disable(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_disable()

    hass.services.async_register(DOMAIN, SERVICE_ENABLE, enable)
    hass.services.async_register(DOMAIN, SERVICE_DISABLE, disable)
    hass.data[f"{DOMAIN}_services_registered"] = True
