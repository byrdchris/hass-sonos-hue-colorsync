
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .coordinator import SonosHueCoordinator
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    coord = SonosHueCoordinator(hass, entry.data)
    await coord.async_setup()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coord
    return True
