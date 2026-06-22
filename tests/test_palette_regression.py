#!/usr/bin/env python3
"""Deterministic album-cover palette regression checks for Sonos Hue Sync.

Run from the repository root with:
    python3 tests/test_palette_regression.py

The images are synthetic but album-cover-like: flat graphic covers, dark covers,
monochrome photography-style covers, warm portraits, vivid pop/electronic covers,
and randomized mixed covers. The goal is to catch palette regressions before a
release archive is built.
"""
from __future__ import annotations

import colorsys
import io
import random
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "media_hue_sync"

# Load palette.py without importing the Home Assistant integration package
# __init__.py, which requires Home Assistant at test time.
import importlib.util
import types

pkg_root = types.ModuleType("custom_components")
pkg = types.ModuleType("custom_components.media_hue_sync")
pkg.__path__ = [str(COMPONENT)]
sys.modules.setdefault("custom_components", pkg_root)
sys.modules.setdefault("custom_components.media_hue_sync", pkg)

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

const = load_module("custom_components.media_hue_sync.const", COMPONENT / "const.py")
palette_mod = load_module("custom_components.media_hue_sync.palette", COMPONENT / "palette.py")

AUTO_STYLE_ACCURACY = const.AUTO_STYLE_ACCURACY
AUTO_STYLE_BALANCED = const.AUTO_STYLE_BALANCED
AUTO_STYLE_VIVID = const.AUTO_STYLE_VIVID
CONF_ARTWORK_STYLE = const.CONF_ARTWORK_STYLE
CONF_AUTO_STYLE_BEHAVIOR = const.CONF_AUTO_STYLE_BEHAVIOR
CONF_COLOR_COUNT = const.CONF_COLOR_COUNT
CONF_NEUTRAL_TONE_HANDLING = const.CONF_NEUTRAL_TONE_HANDLING
ARTWORK_STYLE_AUTO = const.ARTWORK_STYLE_AUTO
NEUTRAL_TONE_NATURAL = const.NEUTRAL_TONE_NATURAL
NEUTRAL_TONE_REDUCE_WHITES = const.NEUTRAL_TONE_REDUCE_WHITES
NEUTRAL_TONE_WARM_AMBIENT = const.NEUTRAL_TONE_WARM_AMBIENT
PALETTE_COHERENCE_DOMINANT_ACCENT = const.PALETTE_COHERENCE_DOMINANT_ACCENT
PALETTE_COHERENCE_DOMINANT_ONLY = const.PALETTE_COHERENCE_DOMINANT_ONLY
extract_palette_from_bytes = palette_mod.extract_palette_from_bytes
apply_palette_coherence = palette_mod._apply_palette_coherence
rgb_to_hex = palette_mod.rgb_to_hex

RGB = tuple[int, int, int]


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def hsv(rgb: RGB) -> tuple[float, float, float]:
    r, g, b = [v / 255 for v in rgb]
    return colorsys.rgb_to_hsv(r, g, b)


def hue_distance_degrees(a: float, b: float) -> float:
    diff = abs(a - b)
    return min(diff, 1.0 - diff) * 360.0


def max_saturation(palette: Iterable[RGB]) -> float:
    return max((hsv(c)[1] for c in palette), default=0.0)


def mean_red_dominance(palette: Iterable[RGB]) -> float:
    vals = []
    for r, g, b in palette:
        vals.append(max(0, r - max(g, b)) / 255)
    return sum(vals) / max(1, len(vals))


def graphic_cover(background: RGB, accents: list[RGB] | None = None) -> Image.Image:
    img = Image.new("RGB", (256, 256), background)
    draw = ImageDraw.Draw(img)
    accents = accents or []
    for i, color in enumerate(accents):
        x0 = 18 + i * 38
        draw.rectangle((x0, 34, x0 + 26, 218), fill=color)
    draw.rectangle((26, 178, 232, 210), fill=(12, 12, 12))
    return img


def dark_cover(hue_rgb: RGB) -> Image.Image:
    img = Image.new("RGB", (256, 256), (6, 8, 18))
    draw = ImageDraw.Draw(img)
    draw.ellipse((34, 34, 224, 224), fill=hue_rgb)
    draw.rectangle((0, 190, 256, 256), fill=(3, 4, 10))
    return img.filter(ImageFilter.GaussianBlur(radius=1.2))


def monochrome_cover() -> Image.Image:
    img = Image.new("RGB", (256, 256), (18, 18, 18))
    draw = ImageDraw.Draw(img)
    for i in range(0, 256, 8):
        value = 35 + int(i * 0.7)
        draw.rectangle((i, 0, i + 8, 256), fill=(value, value, value))
    draw.ellipse((80, 40, 180, 210), fill=(168, 168, 168))
    return img


def random_album(seed: int) -> tuple[Image.Image, RGB]:
    rng = random.Random(seed)
    base_h = rng.random()
    s = rng.uniform(0.45, 0.95)
    v = rng.uniform(0.28, 0.88)
    base = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(base_h, s, v))
    img = Image.new("RGB", (256, 256), base)
    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(3, 9)):
        h = (base_h + rng.uniform(-0.08, 0.08)) % 1.0
        c = tuple(int(x * 255) for x in colorsys.hsv_to_rgb(h, rng.uniform(0.35, 0.9), rng.uniform(0.18, 0.95)))
        x0, y0 = rng.randint(0, 210), rng.randint(0, 210)
        draw.rectangle((x0, y0, x0 + rng.randint(20, 90), y0 + rng.randint(20, 90)), fill=c)
    return img, base


def config(neutral: str = NEUTRAL_TONE_NATURAL, behavior: str = AUTO_STYLE_BALANCED) -> dict:
    return {
        CONF_COLOR_COUNT: 6,
        CONF_ARTWORK_STYLE: ARTWORK_STYLE_AUTO,
        CONF_AUTO_STYLE_BEHAVIOR: behavior,
        CONF_NEUTRAL_TONE_HANDLING: neutral,
        "low_color_handling": True,
        "palette_coherence": PALETTE_COHERENCE_DOMINANT_ACCENT,
    }



def cyan_magenta_cover() -> Image.Image:
    # Cyan-dominant album-like art with intentional vivid magenta accents.
    img = Image.new("RGB", (256, 256), (0, 190, 224))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 256, 256), fill=(0, 192, 224))
    draw.rectangle((24, 42, 232, 92), fill=(16, 96, 128))
    draw.rectangle((52, 134, 76, 212), fill=(224, 0, 128))
    draw.rectangle((172, 138, 196, 216), fill=(192, 0, 112))
    draw.rectangle((0, 220, 256, 256), fill=(48, 80, 112))
    return img


def assert_vivid_accent_policy_keeps_magenta() -> None:
    # Regression for cyan-dominant covers with a real magenta accent.
    raw = [(0, 192, 224), (48, 80, 112), (16, 96, 128), (32, 160, 160), (22, 134, 156), (11, 184, 208), (224, 0, 128), (192, 0, 112)]
    cfg = {"palette_coherence": PALETTE_COHERENCE_DOMINANT_ACCENT}
    palette = apply_palette_coherence(raw[:6], raw, 6, cfg)
    magenta = sum(1 for c in palette if 0.83 <= hsv(c)[0] <= 0.97 and hsv(c)[1] > 0.55 and hsv(c)[2] > 0.30)
    assert magenta >= 1, f"Dominant + Vivid Accent lost magenta: {[rgb_to_hex(c) for c in palette]}"


def assert_dominant_only_can_remove_magenta() -> None:
    raw = [(0, 192, 224), (48, 80, 112), (16, 96, 128), (32, 160, 160), (22, 134, 156), (11, 184, 208), (224, 0, 128), (192, 0, 112)]
    cfg = {"palette_coherence": PALETTE_COHERENCE_DOMINANT_ONLY}
    palette = apply_palette_coherence(raw[:6], raw, 6, cfg)
    magenta = sum(1 for c in palette if 0.83 <= hsv(c)[0] <= 0.97 and hsv(c)[1] > 0.55 and hsv(c)[2] > 0.30)
    assert magenta == 0, f"Dominant Colors Only should preserve cohesive dominant look: {[rgb_to_hex(c) for c in palette]}"

def assert_not_red_shift_for_green() -> None:
    img = graphic_cover((141, 199, 29), accents=[(178, 224, 63), (73, 96, 27)])
    cfg = config(NEUTRAL_TONE_REDUCE_WHITES, AUTO_STYLE_ACCURACY)
    palette = extract_palette_from_bytes(png_bytes(img), cfg)
    greens = sum(1 for r, g, b in palette if g >= r and g >= b and g > 60)
    assert greens >= 3, f"green graphic cover lost green identity: {[rgb_to_hex(c) for c in palette]}"
    assert mean_red_dominance(palette) < 0.12, f"green cover red-shifted: {[rgb_to_hex(c) for c in palette]}"


def assert_monochrome_does_not_turn_red() -> None:
    cfg = config(NEUTRAL_TONE_NATURAL, AUTO_STYLE_VIVID)
    palette = extract_palette_from_bytes(png_bytes(monochrome_cover()), cfg)
    assert max_saturation(palette) < 0.18, f"monochrome cover gained color cast: {[rgb_to_hex(c) for c in palette]}"


def assert_warm_ambient_does_not_recolor_blue() -> None:
    img = dark_cover((20, 70, 180))
    cfg = config(NEUTRAL_TONE_WARM_AMBIENT, AUTO_STYLE_BALANCED)
    palette = extract_palette_from_bytes(png_bytes(img), cfg)
    blueish = sum(1 for c in palette if hsv(c)[0] > 0.52 and hsv(c)[0] < 0.75 and hsv(c)[1] > 0.20)
    assert blueish >= 1, f"dark blue cover lost blue identity under Warm Ambient: {[rgb_to_hex(c) for c in palette]}"
    assert mean_red_dominance(palette) < 0.18, f"Warm Ambient introduced excessive red/brown: {[rgb_to_hex(c) for c in palette]}"


def assert_random_covers_keep_hue_family() -> None:
    failures = []
    for seed in range(50):
        img, expected = random_album(seed)
        expected_h, expected_s, _ = hsv(expected)
        if expected_s < 0.35:
            continue
        palette = extract_palette_from_bytes(png_bytes(img), config())
        colorized = [c for c in palette if hsv(c)[1] >= 0.22]
        if not colorized:
            failures.append((seed, [rgb_to_hex(c) for c in palette], "no colorized palette"))
            continue
        best = min(hue_distance_degrees(hsv(c)[0], expected_h) for c in colorized)
        if best > 65:
            failures.append((seed, [rgb_to_hex(c) for c in palette], f"hue drift {best:.1f}"))
    assert not failures, f"random album hue-family failures: {failures[:5]}"


def main() -> None:
    checks = [
        assert_not_red_shift_for_green,
        assert_monochrome_does_not_turn_red,
        assert_warm_ambient_does_not_recolor_blue,
        assert_vivid_accent_policy_keeps_magenta,
        assert_dominant_only_can_remove_magenta,
        assert_random_covers_keep_hue_family,
    ]
    for check in checks:
        check()
    print("palette_regression: PASS - 55 synthetic album-cover cases")


if __name__ == "__main__":
    main()
