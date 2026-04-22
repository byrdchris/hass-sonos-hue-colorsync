
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .coordinator import SonosHueCoordinator
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    coordinator = SonosHueCoordinator(hass, entry.data)
    await coordinator.async_setup()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    return True
