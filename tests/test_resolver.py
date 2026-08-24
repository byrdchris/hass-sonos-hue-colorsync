from __future__ import annotations

from unittest.mock import MagicMock
from custom_components.media_hue_sync.resolver import (
    _supports_any_color,
    _unique,
    _unique_id_looks_grouped,
    ResolveResult,
)


def test_unique_preserves_order():
    items = ["light.a", "light.b", "light.a", "light.c", "light.b"]
    assert _unique(items) == ["light.a", "light.b", "light.c"]


def test_supports_any_color():
    state_color = MagicMock()
    state_color.attributes = {"supported_color_modes": ["hs", "rgb"]}
    assert _supports_any_color(state_color) is True

    state_onoff = MagicMock()
    state_onoff.attributes = {"supported_color_modes": ["onoff"]}
    assert _supports_any_color(state_onoff) is False


def test_unique_id_looks_grouped():
    entry_room = MagicMock()
    entry_room.unique_id = "room_123_grouped_light"
    assert _unique_id_looks_grouped(entry_room) is True

    entry_single = MagicMock()
    entry_single.unique_id = "00:17:88:01:08:12:34:56-0b"
    assert _unique_id_looks_grouped(entry_single) is False
