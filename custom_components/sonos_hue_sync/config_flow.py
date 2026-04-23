from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_CACHE,
    CONF_COLOR_COUNT,
    CONF_FILTER_DULL,
    CONF_LIGHT_ENTITIES,
    CONF_LIGHT_GROUP,
    CONF_SONOS_ENTITY,
    CONF_TRANSITION,
    DEFAULT_CACHE,
    DEFAULT_COLOR_COUNT,
    DEFAULT_FILTER_DULL,
    DEFAULT_TRANSITION,
    DOMAIN,
)

def build_schema(defaults: dict):
    return vol.Schema(
        {
            vol.Required(
                CONF_SONOS_ENTITY,
                default=defaults.get(CONF_SONOS_ENTITY, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="media_player")
            ),
            vol.Required(
                CONF_LIGHT_ENTITIES,
                default=defaults.get(CONF_LIGHT_ENTITIES, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="light", multiple=True)
            ),
            vol.Optional(
                CONF_COLOR_COUNT,
                default=defaults.get(CONF_COLOR_COUNT, DEFAULT_COLOR_COUNT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, step=1, mode=selector.NumberSelectorMode.SLIDER)
            ),
            vol.Optional(
                CONF_TRANSITION,
                default=defaults.get(CONF_TRANSITION, DEFAULT_TRANSITION),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=10, step=1, mode=selector.NumberSelectorMode.SLIDER)
            ),
            vol.Optional(
                CONF_FILTER_DULL,
                default=defaults.get(CONF_FILTER_DULL, DEFAULT_FILTER_DULL),
            ): bool,
            vol.Optional(
                CONF_CACHE,
                default=defaults.get(CONF_CACHE, DEFAULT_CACHE),
            ): bool,
        }
    )

class SonosHueConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    # Kept at VERSION=1 to avoid migration issues for existing test installs.
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
