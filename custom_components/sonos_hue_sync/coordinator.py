
from homeassistant.helpers.event import async_track_state_change_event
from .palette import extract_palette
from .hue_controller import apply_palette, snapshot_scene, restore_scene
from .cache import PaletteCache

class SonosHueCoordinator:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.entity_id = entry.data["sonos_entity"]
        self.light_group = entry.data["light_group"]
        self.cache = PaletteCache()
        self.scene_id = None
        self.enabled = True

    async def async_setup(self):
        self._remove = async_track_state_change_event(
            self.hass,[self.entity_id],self._handle)

    async def _handle(self,event):
        state = event.data.get("new_state")
        if not state or not self.enabled:
            return

        if state.state == "playing":
            if not self.scene_id:
                self.scene_id = await snapshot_scene(self.hass,self.light_group)

            art = state.attributes.get("entity_picture")
            if not art:
                return

            if self.cache.exists(art):
                palette = self.cache.get(art)
            else:
                palette = await extract_palette(art,self.entry.data)
                self.cache.set(art,palette)

            await apply_palette(self.hass,self.light_group,palette,self.entry.data)

        elif state.state in ["paused","idle","off"]:
            if self.scene_id:
                await restore_scene(self.hass,self.scene_id)
                self.scene_id = None
