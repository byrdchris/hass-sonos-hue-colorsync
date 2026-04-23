
from .coordinator import SonosHueCoordinator
from .services import async_setup_services

async def async_setup_entry(hass,entry):
    coord=SonosHueCoordinator(hass,entry)
    await coord.async_setup()
    await async_setup_services(hass)
    hass.data.setdefault("sonos_hue_sync",{})[entry.entry_id]=coord
    return True
