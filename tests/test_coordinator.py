from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from custom_components.media_hue_sync.const import (
    CONF_LIGHT_ENTITIES,
    CONF_SONOS_ENTITY,
    DOMAIN,
)
from custom_components.media_hue_sync.coordinator import SonosHueCoordinator


def test_coordinator_setup_and_listener_lifecycle(mock_hass):
    async def _test():
        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_SONOS_ENTITY: "media_player.living_room",
            CONF_LIGHT_ENTITIES: ["light.living_room_light"],
        }
        mock_entry.options = {}
        mock_entry.entry_id = "test_entry_id"

        coordinator = SonosHueCoordinator(mock_hass, mock_entry)

        # Ensure setting _restore_delay_task and _auto_rotate_task works without AttributeError
        assert coordinator._restore_delay_task is None
        assert coordinator._auto_rotate_task is None

        # Verify async_setup succeeds
        await coordinator.async_setup()
        assert coordinator.last_processing_reason == "setup_waiting_for_event_or_button"

        # Verify async_refresh_listener succeeds without AttributeError
        await coordinator.async_refresh_listener()

        # Verify async_unload succeeds without AttributeError
        await coordinator.async_unload()

    asyncio.run(_test())
