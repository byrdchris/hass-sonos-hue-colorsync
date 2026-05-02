from __future__ import annotations

# Config and options flow. Builds one stable advanced setup/options form;
# avoids legacy mode gating because Home Assistant entity controls do not
# support reliable dynamic grouping/visibility.
# brief-code-commented-build: moderate block-level comments added for maintainability.

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    ASSIGNMENT_STRATEGY_ALTERNATING,
    ASSIGNMENT_STRATEGY_BALANCED,
    ASSIGNMENT_STRATEGY_BRIGHTNESS,
    ASSIGNMENT_STRATEGY_SEQUENTIAL,
    ARTWORK_FALLBACK_MODE_LABELS,
    ARTWORK_FALLBACK_MODES,
    COLOR_ACCURACY_MODE_LABELS,
    COLOR_ACCURACY_MODE_OPTIONS,
    COLOR_PURITY_PRESET_LABELS,
    COLOR_PURITY_PRESET_OPTIONS,
    CONF_AIRPLAY_POLL_INTERVAL,
    CONF_ARTWORK_FALLBACK_MODE,
    CONF_ASSIGNMENT_STRATEGY,
    CONF_AUTO_ROTATE_INTERVAL,
    CONF_CACHE,
    CONF_COLOR_ACCURACY_MODE,
    CONF_COLOR_COUNT,
    CONF_COLOR_PURITY,
    CONF_EXCLUDE_LIGHT_ENTITIES,
    CONF_EXPAND_GROUPS,
    CONF_GRADIENT_BRIGHTNESS,
    CONF_GRADIENT_COLOR_POINTS,
    CONF_GRADIENT_ORDER_MODE,
    CONF_GROUP_ENTITIES,
    CONF_LIGHT_ENTITIES,
    CONF_LIGHT_GROUP,
    CONF_LOW_COLOR_HANDLING,
    CONF_MAX_BRIGHTNESS,
    CONF_MEMBER_LIGHT_ENTITIES,
    CONF_MIN_BRIGHTNESS,
    CONF_MONOCHROME_MODE,
    CONF_PALETTE_ORDERING,
    CONF_PALETTE_COHERENCE,
    CONF_RESTORE_DELAY,
    CONF_ROTATION_MODE,
    CONF_SONOS_ENTITY,
    CONF_TRANSITION,
    CONF_TRUE_GRADIENT_MODE,
    CONF_WHITE_HANDLING,
    CONF_WHITE_LEVEL,
    DEFAULT_AIRPLAY_POLL_INTERVAL,
    DEFAULT_ARTWORK_FALLBACK_MODE,
    DEFAULT_ASSIGNMENT_STRATEGY,
    DEFAULT_AUTO_ROTATE_INTERVAL,
    DEFAULT_CACHE,
    DEFAULT_COLOR_ACCURACY_MODE,
    DEFAULT_COLOR_COUNT,
    DEFAULT_COLOR_PURITY,
    DEFAULT_EXPAND_GROUPS,
    DEFAULT_EXCLUDE_LIGHT_ENTITIES,
    DEFAULT_GRADIENT_BRIGHTNESS,
    DEFAULT_GRADIENT_COLOR_POINTS,
    DEFAULT_GRADIENT_ORDER_MODE,
    DEFAULT_LOW_COLOR_HANDLING,
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_MIN_BRIGHTNESS,
    DEFAULT_MONOCHROME_MODE,
    DEFAULT_PALETTE_ORDERING,
    DEFAULT_PALETTE_COHERENCE,
    DEFAULT_RESTORE_DELAY,
    DEFAULT_ROTATION_MODE,
    DEFAULT_TRANSITION,
    DEFAULT_TRUE_GRADIENT_MODE,
    DEFAULT_WHITE_HANDLING,
    DEFAULT_WHITE_LEVEL,
    DOMAIN,
    GRADIENT_ORDER_MODE_LABELS,
    GRADIENT_ORDER_MODES,
    MAX_AUTO_ROTATE_INTERVAL,
    MIN_AUTO_ROTATE_INTERVAL,
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


def _select_options(options, labels):
    # Convert internal values to Home Assistant's label/value select format.
    return [{"value": key, "label": labels[key]} for key in options]


def _color_purity_options(defaults: dict):
    # Preserve any existing numeric custom value by adding it to the options list
    # while steering new edits toward named presets.
    options = list(COLOR_PURITY_PRESET_OPTIONS)
    current = str(defaults.get(CONF_COLOR_PURITY, DEFAULT_COLOR_PURITY))
    labels = dict(COLOR_PURITY_PRESET_LABELS)
    if current not in labels:
        options.append(current)
        labels[current] = f"Custom / Existing ({current})"
    return _select_options(options, labels)


def _full_schema(defaults: dict):
    """Single stable schema ordered from everyday controls to advanced tuning."""
    return {
        vol.Required(CONF_SONOS_ENTITY, default=defaults.get(CONF_SONOS_ENTITY, "")):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="media_player")),
        vol.Required(CONF_LIGHT_ENTITIES, default=defaults.get(CONF_LIGHT_ENTITIES, [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="light", multiple=True)),
        vol.Optional(CONF_COLOR_ACCURACY_MODE, default=defaults.get(CONF_COLOR_ACCURACY_MODE, DEFAULT_COLOR_ACCURACY_MODE)):
            selector.SelectSelector(selector.SelectSelectorConfig(options=_select_options(COLOR_ACCURACY_MODE_OPTIONS, COLOR_ACCURACY_MODE_LABELS), mode=selector.SelectSelectorMode.LIST)),
        vol.Optional(CONF_COLOR_PURITY, default=str(defaults.get(CONF_COLOR_PURITY, DEFAULT_COLOR_PURITY))):
            selector.SelectSelector(selector.SelectSelectorConfig(options=_color_purity_options(defaults), mode=selector.SelectSelectorMode.LIST)),
        vol.Optional(CONF_WHITE_HANDLING, default=defaults.get(CONF_WHITE_HANDLING, DEFAULT_WHITE_HANDLING)):
            selector.SelectSelector(selector.SelectSelectorConfig(options=_select_options(WHITE_HANDLING_OPTIONS, WHITE_HANDLING_LABELS), mode=selector.SelectSelectorMode.LIST)),
        vol.Optional(CONF_WHITE_LEVEL, default=defaults.get(CONF_WHITE_LEVEL, DEFAULT_WHITE_LEVEL)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=100, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_COLOR_COUNT, default=defaults.get(CONF_COLOR_COUNT, DEFAULT_COLOR_COUNT)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=10, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_TRANSITION, default=defaults.get(CONF_TRANSITION, DEFAULT_TRANSITION)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=10, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_ROTATION_MODE, default=defaults.get(CONF_ROTATION_MODE, DEFAULT_ROTATION_MODE)):
            selector.SelectSelector(selector.SelectSelectorConfig(options=_select_options(ROTATION_MODE_OPTIONS, ROTATION_MODE_LABELS), mode=selector.SelectSelectorMode.LIST)),
        vol.Optional(CONF_AUTO_ROTATE_INTERVAL, default=defaults.get(CONF_AUTO_ROTATE_INTERVAL, DEFAULT_AUTO_ROTATE_INTERVAL)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=MIN_AUTO_ROTATE_INTERVAL, max=MAX_AUTO_ROTATE_INTERVAL, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_RESTORE_DELAY, default=defaults.get(CONF_RESTORE_DELAY, DEFAULT_RESTORE_DELAY)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=60, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_GROUP_ENTITIES, default=defaults.get(CONF_GROUP_ENTITIES, [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="light", multiple=True)),
        vol.Optional(CONF_MEMBER_LIGHT_ENTITIES, default=defaults.get(CONF_MEMBER_LIGHT_ENTITIES, [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="light", multiple=True)),
        vol.Optional(CONF_EXCLUDE_LIGHT_ENTITIES, default=defaults.get(CONF_EXCLUDE_LIGHT_ENTITIES, DEFAULT_EXCLUDE_LIGHT_ENTITIES)):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="light", multiple=True)),
        vol.Optional(CONF_ASSIGNMENT_STRATEGY, default=defaults.get(CONF_ASSIGNMENT_STRATEGY, DEFAULT_ASSIGNMENT_STRATEGY)):
            selector.SelectSelector(selector.SelectSelectorConfig(options=[
                selector.SelectOptionDict(value=ASSIGNMENT_STRATEGY_BALANCED, label="Balanced"),
                selector.SelectOptionDict(value=ASSIGNMENT_STRATEGY_SEQUENTIAL, label="Sequential"),
                selector.SelectOptionDict(value=ASSIGNMENT_STRATEGY_ALTERNATING, label="Alternating bright / dim"),
                selector.SelectOptionDict(value=ASSIGNMENT_STRATEGY_BRIGHTNESS, label="Brightness order"),
            ], mode=selector.SelectSelectorMode.LIST)),
        vol.Optional(CONF_PALETTE_ORDERING, default=defaults.get(CONF_PALETTE_ORDERING, DEFAULT_PALETTE_ORDERING)):
            selector.SelectSelector(selector.SelectSelectorConfig(options=_select_options(PALETTE_ORDERING_OPTIONS, PALETTE_ORDERING_LABELS), mode=selector.SelectSelectorMode.LIST)),
        vol.Optional(CONF_PALETTE_COHERENCE, default=defaults.get(CONF_PALETTE_COHERENCE, DEFAULT_PALETTE_COHERENCE)):
            selector.SelectSelector(selector.SelectSelectorConfig(options=_select_options(PALETTE_COHERENCE_OPTIONS, PALETTE_COHERENCE_LABELS), mode=selector.SelectSelectorMode.LIST)),
        vol.Optional(CONF_TRUE_GRADIENT_MODE, default=defaults.get(CONF_TRUE_GRADIENT_MODE, DEFAULT_TRUE_GRADIENT_MODE)): bool,
        vol.Optional(CONF_GRADIENT_ORDER_MODE, default=defaults.get(CONF_GRADIENT_ORDER_MODE, DEFAULT_GRADIENT_ORDER_MODE)):
            selector.SelectSelector(selector.SelectSelectorConfig(options=_select_options(GRADIENT_ORDER_MODES, GRADIENT_ORDER_MODE_LABELS), mode=selector.SelectSelectorMode.LIST)),
        vol.Optional(CONF_GRADIENT_COLOR_POINTS, default=defaults.get(CONF_GRADIENT_COLOR_POINTS, DEFAULT_GRADIENT_COLOR_POINTS)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=2, max=5, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_GRADIENT_BRIGHTNESS, default=defaults.get(CONF_GRADIENT_BRIGHTNESS, DEFAULT_GRADIENT_BRIGHTNESS)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=255, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_MIN_BRIGHTNESS, default=defaults.get(CONF_MIN_BRIGHTNESS, DEFAULT_MIN_BRIGHTNESS)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=255, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_MAX_BRIGHTNESS, default=defaults.get(CONF_MAX_BRIGHTNESS, DEFAULT_MAX_BRIGHTNESS)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=255, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_MONOCHROME_MODE, default=defaults.get(CONF_MONOCHROME_MODE, DEFAULT_MONOCHROME_MODE)):
            selector.SelectSelector(selector.SelectSelectorConfig(options=[
                selector.SelectOptionDict(value=MONOCHROME_MODE_WARM_NEUTRAL, label="Warm neutral"),
                selector.SelectOptionDict(value=MONOCHROME_MODE_GRAYSCALE, label="Preserve grayscale"),
                selector.SelectOptionDict(value=MONOCHROME_MODE_MUTED_ACCENT, label="Muted accent"),
                selector.SelectOptionDict(value=MONOCHROME_MODE_DISABLED, label="Disabled"),
            ], mode=selector.SelectSelectorMode.LIST)),
        vol.Optional(CONF_LOW_COLOR_HANDLING, default=defaults.get(CONF_LOW_COLOR_HANDLING, DEFAULT_LOW_COLOR_HANDLING)): bool,
        vol.Optional(CONF_ARTWORK_FALLBACK_MODE, default=defaults.get(CONF_ARTWORK_FALLBACK_MODE, DEFAULT_ARTWORK_FALLBACK_MODE)):
            selector.SelectSelector(selector.SelectSelectorConfig(options=_select_options(ARTWORK_FALLBACK_MODES, ARTWORK_FALLBACK_MODE_LABELS), mode=selector.SelectSelectorMode.LIST)),
        vol.Optional(CONF_CACHE, default=defaults.get(CONF_CACHE, DEFAULT_CACHE)): bool,
        vol.Optional(CONF_EXPAND_GROUPS, default=defaults.get(CONF_EXPAND_GROUPS, DEFAULT_EXPAND_GROUPS)): bool,
        vol.Optional(CONF_AIRPLAY_POLL_INTERVAL, default=defaults.get(CONF_AIRPLAY_POLL_INTERVAL, DEFAULT_AIRPLAY_POLL_INTERVAL)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=2, max=60, step=1, mode=selector.NumberSelectorMode.SLIDER)),
    }


def build_schema(defaults: dict):
    return vol.Schema(_full_schema(defaults))


class SonosHueConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Sonos Hue Sync", data=user_input)
        return self.async_show_form(step_id="user", data_schema=build_schema({}))

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Merge user changes over existing data so upgrades keep prior options
            # while removing obsolete legacy mode behavior from the form.
            merged = {**self.entry.data, **self.entry.options, **user_input}
            return self.async_create_entry(title="", data=merged)

        defaults = {**self.entry.data, **self.entry.options}
        if CONF_LIGHT_ENTITIES not in defaults and defaults.get(CONF_LIGHT_GROUP):
            defaults[CONF_LIGHT_ENTITIES] = [defaults[CONF_LIGHT_GROUP]]
        return self.async_show_form(step_id="init", data_schema=build_schema(defaults))
