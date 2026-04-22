
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import callback
from .hue import HueBridgeManager
from .color import extract_colors

class SonosHueCoordinator:
    def __init__(self, hass, config):
        self.hass = hass
        self.config = config
        self.hue = HueBridgeManager(config["hue_bridge_ip"], config["hue_app_key"])
        self.last_track = None

    async def async_setup(self):
        async_track_state_change_event(self.hass, None, self._event)

    def _is_sonos(self, state):
        return state and state.entity_id.startswith("media_player")

    def _leader(self, state):
        return state.attributes.get("group_leader") or state.entity_id

    @callback
    async def _event(self, event):
        new = event.data.get("new_state")
        if not self._is_sonos(new):
            return

        if new.state != "playing":
            return

        leader = self._leader(new)
        if leader != self.config["sonos_entity"]:
            return

        attrs = new.attributes
        track = attrs.get("media_content_id")
        if track == self.last_track:
            return

        self.last_track = track

        art = attrs.get("entity_picture")
        if art and art.startswith("/"):
            art = f"http://homeassistant.local:8123{art}"

        colors = extract_colors(art)
        groups = self.hue.get_groups()
        target = [g for g in groups.values() if g["name"] == self.config["hue_group"]]
        if not target:
            return

        lights = target[0]["lights"]
        for i,l in enumerate(lights):
            self.hue.set_light_color(l, colors[i % len(colors)])
