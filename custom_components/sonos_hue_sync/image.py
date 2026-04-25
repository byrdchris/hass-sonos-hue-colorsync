from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SonosHueSyncAlbumArtImage(coordinator, entry)])


class SonosHueSyncAlbumArtImage(ImageEntity):
    """Current Sonos album art exposed as an image entity."""

    _attr_has_entity_name = True
    _attr_name = "Album Art"
    _attr_translation_key = "album_art"
    _attr_icon = "mdi:album"

    def __init__(self, coordinator, entry):
        super().__init__(hass=coordinator.hass)
        self.coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_album_art"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Sonos Hue Sync",
        )
        self._attr_content_type = "image/jpeg"

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def available(self):
        return bool(getattr(self.coordinator, "enabled", False))

    @property
    def extra_state_attributes(self):
        attrs = getattr(self.coordinator, "last_sonos_attributes", {}) or {}
        return {
            "sonos_entity": self.coordinator.sonos_entity,
            "media_title": attrs.get("media_title"),
            "media_artist": attrs.get("media_artist"),
            "media_album_name": attrs.get("media_album_name"),
            "entity_picture_present": attrs.get("entity_picture_present"),
            "media_image_url_present": attrs.get("media_image_url_present"),
            "image_fetch_status": getattr(self.coordinator, "last_image_fetch_status", None),
            "image_candidates": getattr(self.coordinator, "last_image_fetch_candidates", []),
        }

    async def async_image(self):
        data, content_type = await self.coordinator.async_get_current_artwork()
        if content_type:
            self._attr_content_type = content_type
        return data
