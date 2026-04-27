from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .const import (
    ASSIGNMENT_STRATEGY_ALTERNATING,
    ASSIGNMENT_STRATEGY_BALANCED,
    ASSIGNMENT_STRATEGY_BRIGHTNESS,
    ASSIGNMENT_STRATEGY_SEQUENTIAL,
    ARTWORK_FALLBACK_MODE_LABELS,
    ARTWORK_FALLBACK_MODES,
    BASIC_WHITE_HANDLING_LABELS,
    BASIC_WHITE_HANDLING_OPTIONS,
    BRIGHTNESS_LEVEL_LABELS,
    BRIGHTNESS_LEVEL_OPTIONS,
    COLOR_ACCURACY_MODE_LABELS,
    COLOR_ACCURACY_MODE_OPTIONS,
    CONF_ARTWORK_FALLBACK_MODE,
    CONF_ASSIGNMENT_STRATEGY,
    CONF_BASIC_WHITE_HANDLING,
    CONF_BRIGHTNESS_LEVEL,
    CONF_COLOR_ACCURACY_MODE,
    CONF_CONTROL_MODE,
    CONF_GRADIENT_ORDER_MODE,
    CONF_MONOCHROME_MODE,
    CONF_PALETTE_ORDERING,
    CONF_ROTATION_MODE,
    CONF_WHITE_FILTER_STRENGTH,
    CONF_WHITE_HANDLING,
    CONTROL_MODE_LABELS,
    CONTROL_MODE_OPTIONS,
    DOMAIN,
    GRADIENT_ORDER_MODE_LABELS,
    GRADIENT_ORDER_MODES,
    MONOCHROME_MODE_DISABLED,
    MONOCHROME_MODE_GRAYSCALE,
    MONOCHROME_MODE_MUTED_ACCENT,
    MONOCHROME_MODE_WARM_NEUTRAL,
    PALETTE_ORDERING_LABELS,
    PALETTE_ORDERING_OPTIONS,
    ROTATION_MODE_LABELS,
    ROTATION_MODE_OPTIONS,
    WHITE_FILTER_STRENGTH_LABELS,
    WHITE_FILTER_STRENGTH_OPTIONS,
    WHITE_HANDLING_LABELS,
    WHITE_HANDLING_OPTIONS,
)

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


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        # Primary/everyday controls first
        SonosHueSelect(coordinator, entry, CONF_CONTROL_MODE, "Control Mode", CONTROL_MODE_OPTIONS, CONTROL_MODE_LABELS, "mdi:tune-variant"),
        SonosHueSelect(coordinator, entry, CONF_COLOR_ACCURACY_MODE, "Color Accuracy Mode", COLOR_ACCURACY_MODE_OPTIONS, COLOR_ACCURACY_MODE_LABELS, "mdi:palette-advanced"),
        SonosHueSelect(coordinator, entry, CONF_BASIC_WHITE_HANDLING, "White Handling", BASIC_WHITE_HANDLING_OPTIONS, BASIC_WHITE_HANDLING_LABELS, "mdi:white-balance-sunny"),
        SonosHueSelect(coordinator, entry, CONF_BRIGHTNESS_LEVEL, "Brightness Level", BRIGHTNESS_LEVEL_OPTIONS, BRIGHTNESS_LEVEL_LABELS, "mdi:brightness-6"),
        SonosHueSelect(coordinator, entry, CONF_ROTATION_MODE, "Color Rotation Mode", ROTATION_MODE_OPTIONS, ROTATION_MODE_LABELS, "mdi:rotate-3d-variant"),
        # Advanced tuning remains visible but is only authoritative in Advanced (Custom) mode.
        SonosHueSelect(coordinator, entry, CONF_ASSIGNMENT_STRATEGY, "Color Distribution Mode", ASSIGNMENT_OPTIONS, ASSIGNMENT_LABELS, "mdi:palette-swatch"),
        SonosHueSelect(coordinator, entry, CONF_PALETTE_ORDERING, "Palette Ordering", PALETTE_ORDERING_OPTIONS, PALETTE_ORDERING_LABELS, "mdi:sort"),
        SonosHueSelect(coordinator, entry, CONF_GRADIENT_ORDER_MODE, "Gradient Pattern", GRADIENT_ORDER_MODES, GRADIENT_ORDER_MODE_LABELS, "mdi:gradient-horizontal"),
        SonosHueSelect(coordinator, entry, CONF_WHITE_HANDLING, "White Color Handling", WHITE_HANDLING_OPTIONS, WHITE_HANDLING_LABELS, "mdi:white-balance-sunny"),
        SonosHueSelect(coordinator, entry, CONF_WHITE_FILTER_STRENGTH, "White Filtering Strength", WHITE_FILTER_STRENGTH_OPTIONS, WHITE_FILTER_STRENGTH_LABELS, "mdi:tune-variant"),
        SonosHueSelect(coordinator, entry, CONF_MONOCHROME_MODE, "Black & White Handling", MONOCHROME_OPTIONS, MONOCHROME_LABELS, "mdi:circle-opacity"),
        SonosHueSelect(coordinator, entry, CONF_ARTWORK_FALLBACK_MODE, "Artwork Fallback", ARTWORK_FALLBACK_MODES, ARTWORK_FALLBACK_MODE_LABELS, "mdi:image-sync"),
    ]
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
        await self._coordinator.async_set_runtime_option(self._key, value)
