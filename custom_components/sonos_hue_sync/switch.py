from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN

OPTION_SWITCHES = [
    ("filter_dull", "Remove Dull Colors", "mdi:palette-outline"),
    ("filter_bright_white", "Reduce Harsh Whites", "mdi:white-balance-sunny"),
    ("low_color_handling", "Stabilize Low-Color Artwork", "mdi:contrast-circle"),
    ("cache", "Cache Album Colors", "mdi:cached"),
    ("expand_groups", "Distribute Across Group Lights", "mdi:lightbulb-group"),
    ("true_gradient_mode", "Enable True Gradient", "mdi:gradient-horizontal"),
]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [SonosHueSyncEnableSwitch(coordinator, entry)]
    entities.extend(SonosHueSyncOptionSwitch(coordinator, entry, key, name, icon) for key, name, icon in OPTION_SWITCHES)
    async_add_entities(entities, True)

class SonosHueSyncEnableSwitch(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        self._coordinator = coordinator
        self._entry = entry
        self._remove_listener = None
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_name = "Sync Enabled"
        self._attr_icon = "mdi:toggle-switch"

    async def async_added_to_hass(self):
        self._remove_listener = self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        if self._remove_listener:
            self._remove_listener()

    @property
    def is_on(self):
        return self._coordinator.enabled

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}, "name": self._entry.title or "Sonos Hue Sync"}

    async def async_turn_on(self, **kwargs):
        await self._coordinator.async_enable()

    async def async_turn_off(self, **kwargs):
        await self._coordinator.async_disable()

class SonosHueSyncOptionSwitch(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, name, icon):
        self._coordinator = coordinator
        self._entry = entry
        self._key = key
        self._remove_listener = None
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon

    async def async_added_to_hass(self):
        self._remove_listener = self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        if self._remove_listener:
            self._remove_listener()

    @property
    def is_on(self):
        return bool(self._coordinator.config.get(self._key, True))

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}, "name": self._entry.title or "Sonos Hue Sync"}

    async def async_turn_on(self, **kwargs):
        await self._coordinator.async_set_runtime_option(self._key, True)

    async def async_turn_off(self, **kwargs):
        await self._coordinator.async_set_runtime_option(self._key, False)
