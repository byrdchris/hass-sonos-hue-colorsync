
async def async_setup_services(hass):
    async def enable(call):
        for c in hass.data["sonos_hue_sync"].values():
            c.enabled = True

    async def disable(call):
        for c in hass.data["sonos_hue_sync"].values():
            c.enabled = False
            await c._handle_stop()

    hass.services.async_register("sonos_hue_sync","enable",enable)
    hass.services.async_register("sonos_hue_sync","disable",disable)
