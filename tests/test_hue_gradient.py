from __future__ import annotations

from custom_components.media_hue_sync.hue_gradient import (
    _dedupe_colors,
    _gradient_representative_color,
    _gradient_sort_key,
    _perceived_luminance,
    _raw_gradient_payload,
    _replace_gradient_neutral_points,
    _select_luminance_spread,
    gradient_palette_for_light,
    rgb_to_xy,
)


def test_rgb_to_xy_bounds():
    # Pure red, green, blue conversions to CIE 1931 xy coordinates
    x_red, y_red = rgb_to_xy((255, 0, 0))
    assert 0.60 <= x_red <= 0.75
    assert 0.25 <= y_red <= 0.38

    x_white, y_white = rgb_to_xy((255, 255, 255))
    assert 0.30 <= x_white <= 0.35
    assert 0.30 <= y_white <= 0.35


def test_perceived_luminance_ordering():
    lum_black = _perceived_luminance((0, 0, 0))
    lum_blue = _perceived_luminance((0, 0, 255))
    lum_red = _perceived_luminance((255, 0, 0))
    lum_green = _perceived_luminance((0, 255, 0))
    lum_white = _perceived_luminance((255, 255, 255))

    assert lum_black < lum_blue < lum_red < lum_green < lum_white


def test_gradient_palette_dark_to_light():
    palette = [(255, 255, 255), (0, 0, 0), (255, 0, 0)]
    points = gradient_palette_for_light(palette, (255, 0, 0), 3, order_mode="dark_to_light")

    assert len(points) == 3
    # First point should be darkest, last point brightest
    assert _perceived_luminance(points[0]) <= _perceived_luminance(points[1]) <= _perceived_luminance(points[2])


def test_gradient_palette_light_to_dark():
    palette = [(255, 255, 255), (0, 0, 0), (255, 0, 0)]
    points = gradient_palette_for_light(palette, (255, 0, 0), 3, order_mode="light_to_dark")

    assert len(points) == 3
    # First point should be brightest, last point darkest
    assert _perceived_luminance(points[0]) >= _perceived_luminance(points[1]) >= _perceived_luminance(points[2])


def test_replace_gradient_neutral_points():
    raw_points = [(240, 240, 240), (20, 20, 20), (0, 180, 220)]
    full_palette = [(0, 180, 220), (220, 0, 120), (240, 240, 240)]

    replaced, diag = _replace_gradient_neutral_points(
        raw_points, full_palette, mode="auto", order_mode="same_order"
    )

    assert diag["gradient_neutral_suppression_applied"] is True
    assert len(replaced) == 3


def test_raw_gradient_payload_structure():
    points = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    payload = _raw_gradient_payload(points, transition_seconds=2.0, brightness=200)

    assert payload["on"]["on"] is True
    assert payload["dynamics"]["duration"] == 2000
    assert len(payload["gradient"]["points"]) == 3
