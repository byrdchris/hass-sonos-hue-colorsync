from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SonosHueSyncButton(coordinator, entry, "Extract Now", "extract_now", "mdi:image-sync"),
            SonosHueSyncButton(coordinator, entry, "Apply Last Palette", "apply_last_palette", "mdi:palette"),
            SonosHueSyncButton(coordinator, entry, "Test Rainbow", "test_rainbow", "mdi:rainbow"),
        ],
        True,
    )

class SonosHueSyncButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, name, action, icon):
        self._coordinator = coordinator
        self._entry = entry
        self._action = action
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{action}"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}, "name": self._entry.title or "Sonos Hue Sync"}

    async def async_press(self):
        if self._action == "extract_now":
            await self._coordinator.async_process_current_state(reason="button_extract_now")
        elif self._action == "apply_last_palette":
            await self._coordinator.async_apply_last_palette()
        elif self._action == "test_rainbow":
            await self._coordinator.async_test_rainbow()
