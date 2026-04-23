
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import *

class SonosHueConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Sonos Hue Sync", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_SONOS_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="media_player")
                ),
                vol.Required(CONF_LIGHT_GROUP): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="light")
                ),
                vol.Optional(CONF_COLOR_COUNT, default=3): int,
                vol.Optional(CONF_TRANSITION, default=2): int,
                vol.Optional(CONF_FILTER_DULL, default=True): bool,
                vol.Optional(CONF_CACHE, default=True): bool,
            })
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_COLOR_COUNT, default=data.get(CONF_COLOR_COUNT, 3)): int,
                vol.Optional(CONF_TRANSITION, default=data.get(CONF_TRANSITION, 2)): int,
                vol.Optional(CONF_FILTER_DULL, default=data.get(CONF_FILTER_DULL, True)): bool,
                vol.Optional(CONF_CACHE, default=data.get(CONF_CACHE, True)): bool,
            })
        )
