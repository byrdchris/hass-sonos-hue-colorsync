from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode

from .const import DOMAIN

NUMBERS = [
    ("color_count", "Number of Colors", "mdi:palette", 1, 10, 1),
    ("min_brightness", "Minimum Brightness", "mdi:brightness-5", 1, 255, 1),
    ("max_brightness", "Maximum Brightness", "mdi:brightness-7", 1, 255, 1),
    ("gradient_brightness", "Gradient Brightness", "mdi:gradient-horizontal", 1, 255, 1),
    ("restore_delay", "Restore Delay", "mdi:timer-sand", 0, 60, 1),
    ("transition", "Transition Time", "mdi:timer-outline", 0, 10, 1),
    ("gradient_color_points", "Gradient Detail Level", "mdi:gradient-horizontal", 2, 5, 1),
]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SonosHueNumber(coordinator, entry, *args) for args in NUMBERS], True)

class SonosHueNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry, key, name, icon, minimum, maximum, step):
        self._coordinator = coordinator
        self._entry = entry
        self._key = key
        self._remove_listener = None
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step

    async def async_added_to_hass(self):
        self._remove_listener = self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        if self._remove_listener:
            self._remove_listener()

    @property
    def native_value(self):
        return self._coordinator.config.get(self._key)

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}, "name": self._entry.title or "Sonos Hue Sync"}

    async def async_set_native_value(self, value):
        if self._key == "color_count":
            value = int(value)
        await self._coordinator.async_set_runtime_option(self._key, value)
