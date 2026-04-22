
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import callback
from .hue import HueBridgeManager
from .color import extract_colors
from .storage import StateStore

class SonosHueCoordinator:
    def __init__(self, hass, config):
        self.hass = hass
        self.config = config
        self.hue = HueBridgeManager(config["hue_bridge_ip"], config["hue_app_key"])
        self.store = StateStore(hass)
        self.last_track = None

    async def async_setup(self):
        await self.store.load()
        async_track_state_change_event(
            self.hass,
            None,
            self._handle_event
        )

    def _get_master(self, state):
        return state.attributes.get("group_leader") or state.entity_id

    @callback
    async def _handle_event(self, event):
        new = event.data.get("new_state")
        if not new or not new.entity_id.startswith("media_player"):
            return

        master = self._get_master(new)

        if master != self.config["sonos_entity"]:
            return

        if new.state != "playing":
            return

        attrs = new.attributes
        track_id = attrs.get("media_content_id")
        if track_id == self.last_track:
            return

        self.last_track = track_id

        art = attrs.get("entity_picture")
        if art and art.startswith("/"):
            art = f"http://homeassistant.local:8123{art}"

        colors = extract_colors(art)
        groups = self.hue.get_groups()
        target = [g for g in groups.values() if g["name"] == self.config["hue_group"]]

        if not target:
            return

        lights = target[0]["lights"]

        for i, light in enumerate(lights):
            self.hue.set_light_color(light, colors[i % len(colors)])
