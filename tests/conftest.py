from __future__ import annotations

# Pytest fixtures and mock Home Assistant environment setup for Media Hue Sync.
# brief-code-commented-build: moderate block-level comments added for maintainability.

from pathlib import Path
import sys
import types
from unittest.mock import MagicMock
import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "media_hue_sync"

# Ensure custom_components package path is available
pkg_root = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
pkg = sys.modules.setdefault("custom_components.media_hue_sync", types.ModuleType("custom_components.media_hue_sync"))
pkg.__path__ = [str(COMPONENT)]

# Provide mock homeassistant package hierarchy for standalone testing
ha_mod = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
ha_core = sys.modules.setdefault("homeassistant.core", types.ModuleType("homeassistant.core"))
ha_core.HomeAssistant = MagicMock

ha_helpers = sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
ha_dr = sys.modules.setdefault("homeassistant.helpers.device_registry", types.ModuleType("homeassistant.helpers.device_registry"))
ha_er = sys.modules.setdefault("homeassistant.helpers.entity_registry", types.ModuleType("homeassistant.helpers.entity_registry"))
ha_dr.async_get = MagicMock()
ha_er.async_get = MagicMock()

ha_components = sys.modules.setdefault("homeassistant.components", types.ModuleType("homeassistant.components"))
ha_select = sys.modules.setdefault("homeassistant.components.select", types.ModuleType("homeassistant.components.select"))
ha_select.SelectEntity = MagicMock

ha_http = sys.modules.setdefault("homeassistant.components.http", types.ModuleType("homeassistant.components.http"))
ha_http_auth = sys.modules.setdefault("homeassistant.components.http.auth", types.ModuleType("homeassistant.components.http.auth"))
ha_http_auth.async_sign_path = MagicMock()

ha_aiohttp = sys.modules.setdefault("homeassistant.helpers.aiohttp_client", types.ModuleType("homeassistant.helpers.aiohttp_client"))
ha_aiohttp.async_get_clientsession = MagicMock()

ha_network = sys.modules.setdefault("homeassistant.helpers.network", types.ModuleType("homeassistant.helpers.network"))
ha_network.get_url = MagicMock()

ha_events = sys.modules.setdefault("homeassistant.helpers.event", types.ModuleType("homeassistant.helpers.event"))
ha_events.async_track_state_change_event = MagicMock()
ha_events.async_track_time_interval = MagicMock()

ha_config_entries = sys.modules.setdefault("homeassistant.config_entries", types.ModuleType("homeassistant.config_entries"))
ha_config_entries.ConfigEntry = MagicMock


@pytest.fixture
def mock_hass():
    """Create a lightweight mock of the Home Assistant core object."""
    hass = MagicMock()
    hass.states = MagicMock()
    hass.services = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def sample_palette():
    """Return a standard 5-color test RGB palette."""
    return [
        (220, 40, 40),   # Vivid red
        (40, 180, 220),  # Cyan
        (240, 200, 50),  # Yellow
        (80, 80, 80),    # Neutral gray
        (250, 250, 250), # White
    ]
