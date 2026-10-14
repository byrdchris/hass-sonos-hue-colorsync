from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.media_hue_sync.const import (
    DOMAIN,
    SERVICE_APPLY_LAST_PALETTE,
    SERVICE_DISABLE,
    SERVICE_ENABLE,
    SERVICE_EXTRACT_NOW,
    SERVICE_HEALTH_CHECK,
    SERVICE_SHOW_HELP,
    SERVICE_TEST_COLOR,
    SERVICE_TEST_RAINBOW,
)
from custom_components.media_hue_sync.services import async_setup_services


def test_async_setup_services_registers_all_services(mock_hass):
    async def _test():
        registered_services = {}

        def mock_register(domain, service, service_func, schema=None):
            registered_services[service] = {
                "domain": domain,
                "handler": service_func,
                "schema": schema,
            }

        mock_hass.services.async_register.side_effect = mock_register

        mock_coordinator = MagicMock()
        mock_coordinator.async_enable = AsyncMock()
        mock_coordinator.async_disable = AsyncMock()
        mock_coordinator.async_apply_last_palette = AsyncMock()
        mock_coordinator.async_test_color = AsyncMock()
        mock_coordinator.async_process_current_state = AsyncMock()
        mock_coordinator.async_show_help = AsyncMock()
        mock_coordinator.async_test_rainbow = AsyncMock()
        mock_coordinator.async_health_check = AsyncMock()

        mock_hass.data[DOMAIN] = {"entry_1": mock_coordinator}

        await async_setup_services(mock_hass)

        expected_services = {
            SERVICE_ENABLE,
            SERVICE_DISABLE,
            SERVICE_APPLY_LAST_PALETTE,
            SERVICE_TEST_COLOR,
            SERVICE_EXTRACT_NOW,
            SERVICE_TEST_RAINBOW,
            SERVICE_SHOW_HELP,
            SERVICE_HEALTH_CHECK,
        }

        assert set(registered_services.keys()) == expected_services
        for svc in expected_services:
            assert registered_services[svc]["domain"] == DOMAIN
            assert callable(registered_services[svc]["handler"])

        # Test invoking rainbow service
        call_mock = MagicMock()
        await registered_services[SERVICE_TEST_RAINBOW]["handler"](call_mock)
        mock_coordinator.async_test_rainbow.assert_awaited_once()

        # Test invoking show_help service
        await registered_services[SERVICE_SHOW_HELP]["handler"](call_mock)
        mock_coordinator.async_show_help.assert_awaited_once()

        # Test invoking health_check service
        await registered_services[SERVICE_HEALTH_CHECK]["handler"](call_mock)
        mock_coordinator.async_health_check.assert_awaited_once()

        # Test idempotency
        mock_hass.services.async_register.reset_mock()
        await async_setup_services(mock_hass)
        mock_hass.services.async_register.assert_not_called()

    asyncio.run(_test())
