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
    GRADIENT_ORDER_MODE_LABELS,
    GRADIENT_ORDER_MODES,
    PALETTE_ORDERING_LABELS,
    PALETTE_ORDERING_OPTIONS,
    ROTATION_MODE_LABELS,
    ROTATION_MODE_OPTIONS,
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
    async_add_entities(
        [
            SonosHueSelect(
                coordinator,
                entry,
                key=CONF_COLOR_ACCURACY_MODE,
                name="Color Accuracy Mode",
                options=COLOR_ACCURACY_MODE_OPTIONS,
                labels=COLOR_ACCURACY_MODE_LABELS,
                icon="mdi:palette-advanced",
            ),
            SonosHueSelect(
                coordinator,
                entry,
                key=CONF_PALETTE_ORDERING,
                name="Palette Ordering",
                options=PALETTE_ORDERING_OPTIONS,
                labels=PALETTE_ORDERING_LABELS,
                icon="mdi:sort",
            ),
            SonosHueSelect(
                coordinator,
                entry,
                key=CONF_ASSIGNMENT_STRATEGY,
                name="Color Distribution Mode",
                options=ASSIGNMENT_OPTIONS,
                labels=ASSIGNMENT_LABELS,
                icon="mdi:palette-swatch",
            ),
            SonosHueSelect(
                coordinator,
                entry,
                key=CONF_ROTATION_MODE,
                name="Color Rotation Mode",
                options=ROTATION_MODE_OPTIONS,
                labels=ROTATION_MODE_LABELS,
                icon="mdi:rotate-3d-variant",
            ),
            SonosHueSelect(
                coordinator,
                entry,
                key=CONF_ARTWORK_FALLBACK_MODE,
                name="Artwork Fallback",
                options=ARTWORK_FALLBACK_MODES,
                labels=ARTWORK_FALLBACK_MODE_LABELS,
                icon="mdi:image-sync",
            ),
            SonosHueSelect(
                coordinator,
                entry,
                key=CONF_GRADIENT_ORDER_MODE,
                name="Gradient Pattern",
                options=GRADIENT_ORDER_MODES,
                labels=GRADIENT_ORDER_MODE_LABELS,
                icon="mdi:gradient-horizontal",
            ),
            SonosHueSelect(
                coordinator,
                entry,
                key="monochrome_mode",
                name="Black & White Handling",
                options=MONOCHROME_OPTIONS,
                labels=MONOCHROME_LABELS,
                icon="mdi:circle-opacity",
            ),
        ],
        True,
    )


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
