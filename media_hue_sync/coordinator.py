
class MediaHueCoordinator:
    def __init__(self, hass, media_entity):
        self.hass = hass
        self.media_entity = media_entity
        self.enabled = True

        self.media_snapshot = None
        self.last_palette = None

    async def async_process_update(self, state):
        if not self.enabled:
            return

        snapshot = self._build_media_snapshot(state)
        self.media_snapshot = snapshot

        palette = await self._extract_palette(snapshot)
        self.last_palette = palette

        await self._apply_to_hue(palette)

    def _build_media_snapshot(self, state):
        return {
            "entity": self.media_entity,
            "state": state.state,
            "title": state.attributes.get("media_title"),
            "artist": state.attributes.get("media_artist"),
            "album": state.attributes.get("media_album_name"),
            "artwork": state.attributes.get("entity_picture"),
        }

    async def _extract_palette(self, snapshot):
        return await self.hass.data["media_hue_sync"].palette_engine.extract(
            snapshot.get("artwork")
        )

    async def _apply_to_hue(self, palette):
        await self.hass.data["media_hue_sync"].hue_engine.apply(palette)

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
