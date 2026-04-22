
from homeassistant.helpers.storage import Store

class StateStore:
    def __init__(self, hass):
        self.store = Store(hass, 1, "sonos_hue_sync")
        self.data = {"scenes": {}}

    async def load(self):
        d = await self.store.async_load()
        if d:
            self.data = d

    async def save(self):
        await self.store.async_save(self.data)
