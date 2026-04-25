from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    ASSIGNMENT_STRATEGY_ALTERNATING,
    ASSIGNMENT_STRATEGY_BALANCED,
    ASSIGNMENT_STRATEGY_BRIGHTNESS,
    ASSIGNMENT_STRATEGY_SEQUENTIAL,
    CONF_ASSIGNMENT_STRATEGY,
    CONF_CACHE,
    CONF_COLOR_COUNT,
    CONF_EXPAND_GROUPS,
    CONF_FILTER_DULL,
    CONF_FILTER_BRIGHT_WHITE,
    CONF_MONOCHROME_MODE,
    CONF_LOW_COLOR_HANDLING,
    CONF_TRUE_GRADIENT_MODE,
    CONF_GRADIENT_COLOR_POINTS,
    CONF_GRADIENT_ORDER_MODE,
    CONF_LIGHT_ENTITIES,
    CONF_GROUP_ENTITIES,
    CONF_MEMBER_LIGHT_ENTITIES,
    CONF_LIGHT_GROUP,
    CONF_SONOS_ENTITY,
    CONF_TRANSITION,
    DEFAULT_ASSIGNMENT_STRATEGY,
    DEFAULT_CACHE,
    DEFAULT_COLOR_COUNT,
    DEFAULT_EXPAND_GROUPS,
    DEFAULT_FILTER_DULL,
    DEFAULT_FILTER_BRIGHT_WHITE,
    DEFAULT_MONOCHROME_MODE,
    DEFAULT_LOW_COLOR_HANDLING,
    DEFAULT_TRUE_GRADIENT_MODE,
    DEFAULT_GRADIENT_COLOR_POINTS,
    DEFAULT_GRADIENT_ORDER_MODE,
    DEFAULT_TRANSITION,
    DOMAIN,
    MONOCHROME_MODE_WARM_NEUTRAL,
    MONOCHROME_MODE_GRAYSCALE,
    MONOCHROME_MODE_MUTED_ACCENT,
    MONOCHROME_MODE_DISABLED,
    GRADIENT_ORDER_MODE_LABELS,
    GRADIENT_ORDER_MODES,
)

def build_schema(defaults: dict):
    return vol.Schema({
        vol.Required(CONF_SONOS_ENTITY, default=defaults.get(CONF_SONOS_ENTITY, "")):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="media_player")),
        vol.Required(CONF_LIGHT_ENTITIES, default=defaults.get(CONF_LIGHT_ENTITIES, [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="light", multiple=True)),
        vol.Optional(CONF_GROUP_ENTITIES, default=defaults.get(CONF_GROUP_ENTITIES, [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="light", multiple=True)),
        vol.Optional(CONF_MEMBER_LIGHT_ENTITIES, default=defaults.get(CONF_MEMBER_LIGHT_ENTITIES, [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="light", multiple=True)),
        vol.Optional(CONF_COLOR_COUNT, default=defaults.get(CONF_COLOR_COUNT, DEFAULT_COLOR_COUNT)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=10, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_TRANSITION, default=defaults.get(CONF_TRANSITION, DEFAULT_TRANSITION)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=10, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_FILTER_DULL, default=defaults.get(CONF_FILTER_DULL, DEFAULT_FILTER_DULL)): bool,
        vol.Optional(CONF_FILTER_BRIGHT_WHITE, default=defaults.get(CONF_FILTER_BRIGHT_WHITE, DEFAULT_FILTER_BRIGHT_WHITE)): bool,
        vol.Optional(CONF_MONOCHROME_MODE, default=defaults.get(CONF_MONOCHROME_MODE, DEFAULT_MONOCHROME_MODE)):
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=MONOCHROME_MODE_WARM_NEUTRAL, label="Warm neutral"),
                        selector.SelectOptionDict(value=MONOCHROME_MODE_GRAYSCALE, label="Preserve grayscale"),
                        selector.SelectOptionDict(value=MONOCHROME_MODE_MUTED_ACCENT, label="Muted accent"),
                        selector.SelectOptionDict(value=MONOCHROME_MODE_DISABLED, label="Disabled"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        vol.Optional(CONF_LOW_COLOR_HANDLING, default=defaults.get(CONF_LOW_COLOR_HANDLING, DEFAULT_LOW_COLOR_HANDLING)): bool,
        vol.Optional(CONF_TRUE_GRADIENT_MODE, default=defaults.get(CONF_TRUE_GRADIENT_MODE, DEFAULT_TRUE_GRADIENT_MODE)): bool,
        vol.Optional(CONF_GRADIENT_COLOR_POINTS, default=defaults.get(CONF_GRADIENT_COLOR_POINTS, DEFAULT_GRADIENT_COLOR_POINTS)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=2, max=5, step=1, mode=selector.NumberSelectorMode.SLIDER)),
        vol.Optional(CONF_GRADIENT_ORDER_MODE, default=defaults.get(CONF_GRADIENT_ORDER_MODE, DEFAULT_GRADIENT_ORDER_MODE)):
            selector.SelectSelector(selector.SelectSelectorConfig(options=[{"value": key, "label": GRADIENT_ORDER_MODE_LABELS[key]} for key in GRADIENT_ORDER_MODES], mode=selector.SelectSelectorMode.DROPDOWN)),
        vol.Optional(CONF_CACHE, default=defaults.get(CONF_CACHE, DEFAULT_CACHE)): bool,
        vol.Optional(CONF_EXPAND_GROUPS, default=defaults.get(CONF_EXPAND_GROUPS, DEFAULT_EXPAND_GROUPS)): bool,
        vol.Optional(CONF_ASSIGNMENT_STRATEGY, default=defaults.get(CONF_ASSIGNMENT_STRATEGY, DEFAULT_ASSIGNMENT_STRATEGY)):
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=ASSIGNMENT_STRATEGY_BALANCED, label="Balanced"),
                        selector.SelectOptionDict(value=ASSIGNMENT_STRATEGY_SEQUENTIAL, label="Sequential"),
                        selector.SelectOptionDict(value=ASSIGNMENT_STRATEGY_ALTERNATING, label="Alternating bright / dim"),
                        selector.SelectOptionDict(value=ASSIGNMENT_STRATEGY_BRIGHTNESS, label="Brightness order"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
    })

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
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self.entry.data, **self.entry.options}
        if CONF_LIGHT_ENTITIES not in defaults and defaults.get(CONF_LIGHT_GROUP):
            defaults[CONF_LIGHT_ENTITIES] = [defaults[CONF_LIGHT_GROUP]]
        return self.async_show_form(step_id="init", data_schema=build_schema(defaults))
