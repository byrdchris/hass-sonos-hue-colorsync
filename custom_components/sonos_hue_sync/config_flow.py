
import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "sonos_hue_sync"

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input:
            return self.async_create_entry(title="Sonos Hue Sync", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("sonos_entity"): str,
                vol.Required("hue_bridge_ip"): str,
                vol.Required("hue_app_key"): str,
                vol.Required("hue_group"): str
            })
        )
