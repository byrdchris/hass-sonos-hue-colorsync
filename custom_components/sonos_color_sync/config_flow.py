"""Config flow for Sonos Color Sync."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import DOMAIN
from .const import (
    CONF_CACHE_ENABLED,
    CONF_COLOR_COUNT,
    CONF_FILTER_DULL,
    CONF_HUE_APP_KEY,
    CONF_HUE_BRIDGE_IP,
    CONF_LIGHT_GROUP,
    CONF_POLL_INTERVAL,
    CONF_SONOS_ENTITY,
    CONF_TRANSITION_TIME,
)

_LOGGER = logging.getLogger(__name__)


class SonosColorSyncConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_SONOS_ENTITY],
                data=user_input,
            )

        # Get available Sonos media players
        sonos_entities = []
        for entity_id, entity in self.hass.states.async_all():
            if "media_player" in entity_id and "sonos" in entity.attributes.get(
                "device_name", ""
            ).lower():
                sonos_entities.append(entity_id)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SONOS_ENTITY): vol.In(
                        sonos_entities if sonos_entities else ["media_player.sonos"]
                    ),
                    vol.Required(CONF_HUE_BRIDGE_IP): str,
                    vol.Optional(CONF_HUE_APP_KEY, default=""): str,
                    vol.Optional(CONF_LIGHT_GROUP, default=""): str,
                    vol.Optional(CONF_POLL_INTERVAL, default=5): vol.Range(
                        min=1, max=60
                    ),
                    vol.Optional(CONF_COLOR_COUNT, default=3): vol.Range(
                        min=1, max=10
                    ),
                    vol.Optional(CONF_TRANSITION_TIME, default=2): vol.Range(
                        min=0, max=10
                    ),
                    vol.Optional(CONF_FILTER_DULL, default=True): bool,
                    vol.Optional(CONF_CACHE_ENABLED, default=True): bool,
                }
            ),
            description_placeholders={
                "leave_blank": "Leave app key blank to start pairing"
            },
        )

    async def async_step_import(self, import_data: Dict[str, Any]) -> config_entries.FlowResult:
        """Import config from YAML."""
        return await self.async_step_user(import_data)


class SonosColorSyncOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Manage options."""
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, **user_input},
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        data = self.config_entry.data

        # Get available Sonos media players
        sonos_entities = []
        for entity_id, entity in self.hass.states.async_all():
            if "media_player" in entity_id and "sonos" in entity.attributes.get(
                "device_name", ""
            ).lower():
                sonos_entities.append(entity_id)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SONOS_ENTITY, default=data.get(CONF_SONOS_ENTITY)
                    ): vol.In(sonos_entities if sonos_entities else ["media_player.sonos"]),
                    vol.Required(
                        CONF_HUE_BRIDGE_IP, default=data.get(CONF_HUE_BRIDGE_IP, "")
                    ): str,
                    vol.Optional(
                        CONF_HUE_APP_KEY, default=data.get(CONF_HUE_APP_KEY, "")
                    ): str,
                    vol.Optional(
                        CONF_LIGHT_GROUP, default=data.get(CONF_LIGHT_GROUP, "")
                    ): str,
                    vol.Optional(
                        CONF_POLL_INTERVAL, default=data.get(CONF_POLL_INTERVAL, 5)
                    ): vol.Range(min=1, max=60),
                    vol.Optional(
                        CONF_COLOR_COUNT, default=data.get(CONF_COLOR_COUNT, 3)
                    ): vol.Range(min=1, max=10),
                    vol.Optional(
                        CONF_TRANSITION_TIME, default=data.get(CONF_TRANSITION_TIME, 2)
                    ): vol.Range(min=0, max=10),
                    vol.Optional(
                        CONF_FILTER_DULL, default=data.get(CONF_FILTER_DULL, True)
                    ): bool,
                    vol.Optional(
                        CONF_CACHE_ENABLED, default=data.get(CONF_CACHE_ENABLED, True)
                    ): bool,
                }
            ),
        )
