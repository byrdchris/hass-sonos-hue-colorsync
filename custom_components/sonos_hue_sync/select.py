from __future__ import annotations

# Select entities. Provides advanced-only mode choices for palette ordering,
# rotation, gradient behavior, white handling, and artwork fallback.
# brief-code-commented-build: moderate block-level comments added for maintainability.

from homeassistant.components.select import SelectEntity

from .const import (
    ASSIGNMENT_STRATEGY_ALTERNATING,
    ASSIGNMENT_STRATEGY_BALANCED,
    ASSIGNMENT_STRATEGY_BRIGHTNESS,
    ASSIGNMENT_STRATEGY_SEQUENTIAL,
    ARTWORK_FALLBACK_MODE_LABELS,
    ARTWORK_FALLBACK_MODES,
    COLOR_ACCURACY_MODE_LABELS,
    COLOR_ACCURACY_MODE_OPTIONS,
    COLOR_PURITY_PRESET_CUSTOM,
    COLOR_PURITY_PRESET_LABELS,
    COLOR_PURITY_PRESET_OPTIONS,
    CONF_ARTWORK_FALLBACK_MODE,
    CONF_ASSIGNMENT_STRATEGY,
    CONF_COLOR_ACCURACY_MODE,
    CONF_COLOR_PURITY,
    CONF_GRADIENT_ORDER_MODE,
    CONF_MONOCHROME_MODE,
    CONF_PALETTE_ORDERING,
    CONF_PALETTE_COHERENCE,
    CONF_ROTATION_MODE,
    CONF_WHITE_HANDLING,
    DOMAIN,
    GRADIENT_ORDER_MODE_LABELS,
    GRADIENT_ORDER_MODES,
    MONOCHROME_MODE_DISABLED,
    MONOCHROME_MODE_GRAYSCALE,
    MONOCHROME_MODE_MUTED_ACCENT,
    MONOCHROME_MODE_WARM_NEUTRAL,
    PALETTE_COHERENCE_LABELS,
    PALETTE_COHERENCE_OPTIONS,
    PALETTE_ORDERING_LABELS,
    PALETTE_ORDERING_OPTIONS,
    ROTATION_MODE_LABELS,
    ROTATION_MODE_OPTIONS,
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

    # Keep all select controls visible and advanced; avoid Home Assistant form
    # visibility modes that caused confusing legacy mode behavior.
    entities = [
        SonosHueSelect(coordinator, entry, CONF_COLOR_ACCURACY_MODE, "Color Accuracy Mode", COLOR_ACCURACY_MODE_OPTIONS, COLOR_ACCURACY_MODE_LABELS, "mdi:palette-advanced"),
        SonosHueSelect(coordinator, entry, CONF_COLOR_PURITY, "Color Purity Preset", COLOR_PURITY_PRESET_OPTIONS, COLOR_PURITY_PRESET_LABELS, "mdi:palette-outline"),
        SonosHueSelect(coordinator, entry, CONF_WHITE_HANDLING, "White Handling", WHITE_HANDLING_OPTIONS, WHITE_HANDLING_LABELS, "mdi:white-balance-sunny"),
        SonosHueSelect(coordinator, entry, CONF_ROTATION_MODE, "Color Rotation", ROTATION_MODE_OPTIONS, ROTATION_MODE_LABELS, "mdi:rotate-3d-variant"),
        SonosHueSelect(coordinator, entry, CONF_ASSIGNMENT_STRATEGY, "Color Distribution Mode", ASSIGNMENT_OPTIONS, ASSIGNMENT_LABELS, "mdi:palette-swatch"),
        SonosHueSelect(coordinator, entry, CONF_PALETTE_ORDERING, "Palette Ordering", PALETTE_ORDERING_OPTIONS, PALETTE_ORDERING_LABELS, "mdi:sort"),
        SonosHueSelect(coordinator, entry, CONF_PALETTE_COHERENCE, "Palette Coherence", PALETTE_COHERENCE_OPTIONS, PALETTE_COHERENCE_LABELS, "mdi:vector-combine"),
        SonosHueSelect(coordinator, entry, CONF_GRADIENT_ORDER_MODE, "Gradient Pattern", GRADIENT_ORDER_MODES, GRADIENT_ORDER_MODE_LABELS, "mdi:gradient-horizontal"),
        SonosHueSelect(coordinator, entry, CONF_MONOCHROME_MODE, "Black & White Handling", MONOCHROME_OPTIONS, MONOCHROME_LABELS, "mdi:circle-opacity"),
        SonosHueSelect(coordinator, entry, CONF_ARTWORK_FALLBACK_MODE, "Artwork Fallback", ARTWORK_FALLBACK_MODES, ARTWORK_FALLBACK_MODE_LABELS, "mdi:image-sync"),
    ]
    async_add_entities(entities, True)


class SonosHueSelect(SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, name, options, labels, icon):
        # Store the config key and label map so UI labels stay friendly while
        # internal values remain stable for backwards-compatible storage.
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

    def _normalized_value(self):
        # Preset values may arrive as ints from old installs or strings from the
        # new select UI; normalize so both read the same without migration.
        value = self._coordinator.config.get(self._key, self._options[0])
        if self._key == CONF_COLOR_PURITY:
            value = str(value)
        return value

    @property
    def options(self):
        labels = [self._labels[value] for value in self._options]
        if self._key == CONF_COLOR_PURITY and self._normalized_value() not in self._labels:
            labels.append(self._labels[COLOR_PURITY_PRESET_CUSTOM])
        return labels

    @property
    def current_option(self):
        value = self._normalized_value()
        if self._key == CONF_COLOR_PURITY and value not in self._labels:
            return self._labels[COLOR_PURITY_PRESET_CUSTOM]
        return self._labels.get(value, self._labels[self._options[0]])

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}, "name": self._entry.title or "Sonos Hue Sync"}

    async def async_select_option(self, option: str):
        value = self._label_to_option.get(option)
        if value is None:
            return
        # Custom / Existing is display-only. It preserves a legacy or manually
        # supplied numeric value until the user selects one of the named presets.
        if self._key == CONF_COLOR_PURITY and value == COLOR_PURITY_PRESET_CUSTOM:
            return
        await self._coordinator.async_set_runtime_option(self._key, value)
