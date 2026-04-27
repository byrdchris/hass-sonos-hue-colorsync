from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .const import (
    ASSIGNMENT_STRATEGY_ALTERNATING,
    ASSIGNMENT_STRATEGY_BALANCED,
    ASSIGNMENT_STRATEGY_BRIGHTNESS,
    ASSIGNMENT_STRATEGY_SEQUENTIAL,
    CONF_ASSIGNMENT_STRATEGY,
    CONF_ARTWORK_FALLBACK_MODE,
    CONF_GRADIENT_ORDER_MODE,
    CONF_PALETTE_ORDERING,
    CONF_COLOR_ACCURACY_MODE,
    CONF_CONTROL_MODE,
    CONF_BRIGHTNESS_LEVEL,
    CONF_ROTATION_MODE,
    DOMAIN,
    MONOCHROME_MODE_DISABLED,
    MONOCHROME_MODE_GRAYSCALE,
    MONOCHROME_MODE_MUTED_ACCENT,
    MONOCHROME_MODE_WARM_NEUTRAL,
    ARTWORK_FALLBACK_MODE_LABELS,
    ARTWORK_FALLBACK_MODES,
    COLOR_ACCURACY_MODE_LABELS,
    COLOR_ACCURACY_MODE_OPTIONS,
    CONTROL_MODE_LABELS,
    CONTROL_MODE_OPTIONS,
    BRIGHTNESS_LEVEL_LABELS,
    BRIGHTNESS_LEVEL_OPTIONS,
    GRADIENT_ORDER_MODE_LABELS,
    GRADIENT_ORDER_MODES,
    PALETTE_ORDERING_LABELS,
    PALETTE_ORDERING_OPTIONS,
    ROTATION_MODE_LABELS,
    ROTATION_MODE_OPTIONS,
)

CONTROL_MODE_ADVANCED_VALUE = "advanced_custom"

ASSIGNMENT_OPTIONS = [
    ASSIGNMENT_STRATEGY_BALANCED,
    ASSIGNMENT_STRATEGY_SEQUENTIAL,
    ASSIGNMENT_STRATEGY_ALTERNATING,
    ASSIGNMENT_STRATEGY_BRIGHTNESS,
]

ASSIGNMENT_LABELS = {
    ASSIGNMENT_STRATEGY_BALANCED: "Balanced",
    ASSIGNMENT_STRATEGY_SEQUENTIAL: "Sequential",
    ASSIGNMENT_STRATEGY_ALTERNATING: "Alternating bright / dim",
    ASSIGNMENT_STRATEGY_BRIGHTNESS: "Brightness order",
}

MONOCHROME_OPTIONS = [
    MONOCHROME_MODE_WARM_NEUTRAL,
    MONOCHROME_MODE_GRAYSCALE,
    MONOCHROME_MODE_MUTED_ACCENT,
    MONOCHROME_MODE_DISABLED,
]

MONOCHROME_LABELS = {
    MONOCHROME_MODE_WARM_NEUTRAL: "Warm neutral",
    MONOCHROME_MODE_GRAYSCALE: "Preserve grayscale",
    MONOCHROME_MODE_MUTED_ACCENT: "Muted accent",
    MONOCHROME_MODE_DISABLED: "Disabled",
}


def _is_advanced(coordinator):
    return coordinator.config.get(CONF_CONTROL_MODE) == CONTROL_MODE_ADVANCED_VALUE


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        SonosHueSelect(coordinator, entry, CONF_CONTROL_MODE, "Control Mode", CONTROL_MODE_OPTIONS, CONTROL_MODE_LABELS, "mdi:tune-variant"),
        SonosHueSelect(coordinator, entry, CONF_COLOR_ACCURACY_MODE, "Color Accuracy Mode", COLOR_ACCURACY_MODE_OPTIONS, COLOR_ACCURACY_MODE_LABELS, "mdi:palette-advanced"),
        SonosHueSelect(coordinator, entry, CONF_BRIGHTNESS_LEVEL, "Brightness Level", BRIGHTNESS_LEVEL_OPTIONS, BRIGHTNESS_LEVEL_LABELS, "mdi:brightness-6"),
        SonosHueSelect(coordinator, entry, CONF_ROTATION_MODE, "Color Rotation Mode", ROTATION_MODE_OPTIONS, ROTATION_MODE_LABELS, "mdi:rotate-3d-variant"),
    ]
    if _is_advanced(coordinator):
        entities.extend([
            SonosHueSelect(coordinator, entry, CONF_PALETTE_ORDERING, "Palette Ordering", PALETTE_ORDERING_OPTIONS, PALETTE_ORDERING_LABELS, "mdi:sort"),
            SonosHueSelect(coordinator, entry, CONF_ASSIGNMENT_STRATEGY, "Color Distribution Mode", ASSIGNMENT_OPTIONS, ASSIGNMENT_LABELS, "mdi:palette-swatch"),
            SonosHueSelect(coordinator, entry, CONF_ARTWORK_FALLBACK_MODE, "Artwork Fallback", ARTWORK_FALLBACK_MODES, ARTWORK_FALLBACK_MODE_LABELS, "mdi:image-sync"),
            SonosHueSelect(coordinator, entry, CONF_GRADIENT_ORDER_MODE, "Gradient Pattern", GRADIENT_ORDER_MODES, GRADIENT_ORDER_MODE_LABELS, "mdi:gradient-horizontal"),
            SonosHueSelect(coordinator, entry, "monochrome_mode", "Black & White Handling", MONOCHROME_OPTIONS, MONOCHROME_LABELS, "mdi:circle-opacity"),
        ])
    async_add_entities(entities, True)


class SonosHueSelect(SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, name, options, labels, icon):
        self._coordinator = coordinator
        self._entry = entry
        self._key = key
        self._options = options
        self._labels = labels
        self._label_to_option = {label: value for value, label in labels.items()}
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
    def options(self):
        return [self._labels[value] for value in self._options]

    @property
    def current_option(self):
        value = self._coordinator.config.get(self._key, self._options[0])
        return self._labels.get(value, self._labels[self._options[0]])

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}, "name": self._entry.title or "Sonos Hue Sync"}

    async def async_select_option(self, option: str):
        value = self._label_to_option.get(option)
        if value is None:
            return
        reload_needed = self._key == CONF_CONTROL_MODE and value != self._coordinator.config.get(CONF_CONTROL_MODE)
        await self._coordinator.async_set_runtime_option(self._key, value)
        if reload_needed:
            self.hass.async_create_task(self.hass.config_entries.async_reload(self._entry.entry_id))
