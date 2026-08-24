from __future__ import annotations

from unittest.mock import MagicMock
from custom_components.media_hue_sync.assignment import (
    assign_colors,
    _reorder_palette_for_strategy,
)
from custom_components.media_hue_sync.const import (
    ASSIGNMENT_STRATEGY_ALTERNATING,
    ASSIGNMENT_STRATEGY_BALANCED,
    ASSIGNMENT_STRATEGY_BRIGHTNESS,
    ASSIGNMENT_STRATEGY_SEQUENTIAL,
)


def test_reorder_palette_sequential():
    palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    reordered = _reorder_palette_for_strategy(palette, ASSIGNMENT_STRATEGY_SEQUENTIAL)
    assert reordered == palette


def test_reorder_palette_brightness():
    # white (lum ~1.0), red (lum ~0.21), black (lum 0.0)
    palette = [(0, 0, 0), (255, 255, 255), (255, 0, 0)]
    reordered = _reorder_palette_for_strategy(palette, ASSIGNMENT_STRATEGY_BRIGHTNESS)
    assert reordered[0] == (255, 255, 255)
    assert reordered[-1] == (0, 0, 0)


def test_reorder_palette_alternating():
    # white, gray, black, light-gray
    palette = [(0, 0, 0), (255, 255, 255), (100, 100, 100), (200, 200, 200)]
    reordered = _reorder_palette_for_strategy(palette, ASSIGNMENT_STRATEGY_ALTERNATING)
    # Brightest first (255), then darkest (0), then next brightest (200), then next darkest (100)
    assert reordered[0] == (255, 255, 255)
    assert reordered[1] == (0, 0, 0)
    assert reordered[2] == (200, 200, 200)
    assert reordered[3] == (100, 100, 100)


def test_assign_colors_distribution(mock_hass):
    lights = ["light.living_room_1", "light.living_room_2", "light.living_room_3"]
    palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

    assignments = assign_colors(mock_hass, lights, palette, ASSIGNMENT_STRATEGY_SEQUENTIAL)
    assert len(assignments) == 3
    assert assignments["light.living_room_1"] == (255, 0, 0)
    assert assignments["light.living_room_2"] == (0, 255, 0)
    assert assignments["light.living_room_3"] == (0, 0, 255)
