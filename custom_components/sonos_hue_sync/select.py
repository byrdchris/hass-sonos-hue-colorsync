from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .const import (
    ASSIGNMENT_STRATEGY_ALTERNATING,
    ASSIGNMENT_STRATEGY_BALANCED,
    ASSIGNMENT_STRATEGY_BRIGHTNESS,
    ASSIGNMENT_STRATEGY_SEQUENTIAL,
    CONF_ASSIGNMENT_STRATEGY,
    DOMAIN,
)

OPTIONS = [
    ASSIGNMENT_STRATEGY_BALANCED,
    ASSIGNMENT_STRATEGY_SEQUENTIAL,
    ASSIGNMENT_STRATEGY_ALTERNATING,
    ASSIGNMENT_STRATEGY_BRIGHTNESS,
]

OPTION_LABELS = {
    ASSIGNMENT_STRATEGY_BALANCED: "Balanced",
    ASSIGNMENT_STRATEGY_SEQUENTIAL: "Sequential",
    ASSIGNMENT_STRATEGY_ALTERNATING: "Alternating bright/dim",
    ASSIGNMENT_STRATEGY_BRIGHTNESS: "Brightness order",
}

LABEL_TO_OPTION = {label: key for key, label in OPTION_LABELS.items()}

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SonosHueAssignmentStrategySelect(coordinator, entry)], True)

class SonosHueAssignmentStrategySelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Assignment Strategy"
    _attr_icon = "mdi:palette-swatch"

    def __init__(self, coordinator, entry):
        self._coordinator = coordinator
        self._entry = entry
        self._remove_listener = None
        self._attr_unique_id = f"{entry.entry_id}_assignment_strategy"

    async def async_added_to_hass(self):
        self._remove_listener = self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        if self._remove_listener:
            self._remove_listener()

    @property
    def options(self):
        return [OPTION_LABELS[value] for value in OPTIONS]

    @property
    def current_option(self):
        value = self._coordinator.config.get(CONF_ASSIGNMENT_STRATEGY, ASSIGNMENT_STRATEGY_BALANCED)
        return OPTION_LABELS.get(value, OPTION_LABELS[ASSIGNMENT_STRATEGY_BALANCED])

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.title or "Sonos Hue Sync",
        }

    async def async_select_option(self, option: str):
        value = LABEL_TO_OPTION.get(option)
        if value is None:
            return
        await self._coordinator.async_set_assignment_strategy(value)
