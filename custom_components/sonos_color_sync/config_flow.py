"""Config flow for Sonos Color Sync."""
import logging
from typing import Any, Dict, List, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    BooleanSelector,
)

from . import DOMAIN
from .const import (
    CONF_CACHE_ENABLED,
    CONF_COLOR_COUNT,
    CONF_FILTER_DULL,
    CONF_HUE_LIGHTS,
    CONF_POLL_INTERVAL,
    CONF_SONOS_ENTITY,
    CONF_TRANSITION_TIME,
)

_LOGGER = logging.getLogger(__name__)


def _get_hue_light_entities(hass) -> List[str]:
    """Return all light entity IDs from the Hue integration."""
    hue_lights = []
    try:
        entity_registry = hass.helpers.entity_registry.async_get(hass)
        for entity in entity_registry.entities.values():
            if (
                entity.domain == "light"
                and entity.platform == "hue"
                and not entity.disabled
            ):
                hue_lights.append(entity.entity_id)
    except Exception as e:
        _LOGGER.warning("Could not get Hue entities: %s", e)
    return sorted(hue_lights)


def _get_sonos_entities(hass) -> List[str]:
    """Return all Sonos media_player entity IDs."""
    sonos = []
    try:
        entity_registry = hass.helpers.entity_registry.async_get(hass)
        for entity in entity_registry.entities.values():
            if entity.domain == "media_player" and entity.platform == "sonos":
                sonos.append(entity.entity_id)
    except Exception as e:
        _LOGGER.warning("Could not get Sonos entities: %s", e)

    # Fallback: scan states if registry returns nothing
    if not sonos:
        for state in hass.states.async_all("media_player"):
            if "sonos" in state.attributes.get("device_name", "").lower():
                sonos.append(state.entity_id)

    return sorted(sonos) or ["media_player.sonos"]


def _build_schema(hass, defaults: Optional[Dict] = None) -> vol.Schema:
    """Build the config schema with live entity lists."""
    d = defaults or {}

    sonos_entities = _get_sonos_entities(hass)
    hue_lights = _get_hue_light_entities(hass)

    return vol.Schema(
        {
            vol.Required(
                CONF_SONOS_ENTITY,
                default=d.get(CONF_SONOS_ENTITY, sonos_entities[0] if sonos_entities else ""),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=sonos_entities,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_HUE_LIGHTS,
                default=d.get(CONF_HUE_LIGHTS, []),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=hue_lights,
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(
                CONF_POLL_INTERVAL,
                default=d.get(CONF_POLL_INTERVAL, 5),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=60, step=1, mode=NumberSelectorMode.SLIDER)
            ),
            vol.Optional(
                CONF_COLOR_COUNT,
                default=d.get(CONF_COLOR_COUNT, 3),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=10, step=1, mode=NumberSelectorMode.SLIDER)
            ),
            vol.Optional(
                CONF_TRANSITION_TIME,
                default=d.get(CONF_TRANSITION_TIME, 2),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=10, step=1, mode=NumberSelectorMode.SLIDER)
            ),
            vol.Optional(
                CONF_FILTER_DULL,
                default=d.get(CONF_FILTER_DULL, True),
            ): BooleanSelector(),
            vol.Optional(
                CONF_CACHE_ENABLED,
                default=d.get(CONF_CACHE_ENABLED, True),
            ): BooleanSelector(),
        }
    )


class SonosColorSyncConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return SonosColorSyncOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Coerce number selector values to int
            user_input[CONF_POLL_INTERVAL] = int(user_input[CONF_POLL_INTERVAL])
            user_input[CONF_COLOR_COUNT] = int(user_input[CONF_COLOR_COUNT])
            user_input[CONF_TRANSITION_TIME] = int(user_input[CONF_TRANSITION_TIME])

            return self.async_create_entry(
                title=f"Sonos Color Sync ({user_input.get(CONF_SONOS_ENTITY, '')})",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(self.hass),
        )


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
            user_input[CONF_POLL_INTERVAL] = int(user_input[CONF_POLL_INTERVAL])
            user_input[CONF_COLOR_COUNT] = int(user_input[CONF_COLOR_COUNT])
            user_input[CONF_TRANSITION_TIME] = int(user_input[CONF_TRANSITION_TIME])

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, **user_input},
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(self.hass, dict(self.config_entry.data)),
        )
