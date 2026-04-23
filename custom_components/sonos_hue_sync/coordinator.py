
from homeassistant.helpers.event import async_track_state_change_event
from .palette import extract_palette
from .hue_controller import apply_palette,snapshot_scene,restore_scene
from .cache import PaletteCache

class SonosHueCoordinator:
    def __init__(self,hass,entry):
        self.hass=hass
        self.entry=entry
        self.entity_id=entry.data["sonos_entity"]
        self.group=entry.data["light_group"]
        self.cache=PaletteCache()
        self.scene=None
        self.enabled=True

    async def async_setup(self):
        self._rm=async_track_state_change_event(self.hass,[self.entity_id],self._handle)

    async def _handle(self,event):
        state=event.data.get("new_state")
        if not state or not self.enabled: return

        if state.state=="playing":
            if not self.scene:
                self.scene=await snapshot_scene(self.hass,self.group)
            art=state.attributes.get("entity_picture")
            if not art: return
            palette=self.cache.get(art) if self.cache.exists(art) else await extract_palette(art,self.entry.data)
            self.cache.set(art,palette)
            await apply_palette(self.hass,self.group,palette,self.entry.data)

        elif state.state in ["paused","idle","off"]:
            await self._handle_stop()

    async def _handle_stop(self):
        if self.scene:
            await restore_scene(self.hass,self.scene)
            self.scene=None
