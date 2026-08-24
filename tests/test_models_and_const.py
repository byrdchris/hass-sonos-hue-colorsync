from __future__ import annotations

from custom_components.media_hue_sync.const import (
    DOMAIN,
    ARTWORK_STYLE_AUTO,
    ARTWORK_STYLE_OPTIONS,
    NEUTRAL_TONE_OPTIONS,
    PALETTE_COHERENCE_OPTIONS,
    DEFAULT_COLOR_COUNT,
)
from custom_components.media_hue_sync.models import (
    PaletteMetrics,
    AutoStyleDiagnostics,
    CoherenceDiagnostics,
    ResolvedTargetEntities,
)


def test_constants_domain_and_defaults():
    assert DOMAIN == "media_hue_sync"
    assert ARTWORK_STYLE_AUTO in ARTWORK_STYLE_OPTIONS
    assert DEFAULT_COLOR_COUNT == 3


def test_resolved_target_entities_model():
    target = ResolvedTargetEntities(
        selected_entities=["light.living_room_group"],
        resolved_lights=["light.lamp_left", "light.lamp_right"],
        expanded_groups={"light.living_room_group": ["light.lamp_left", "light.lamp_right"]},
        excluded_lights=[],
        unavailable_lights=[],
    )

    assert len(target.resolved_lights) == 2
    assert target.selected_entities == ["light.living_room_group"]
    assert len(target.expanded_groups["light.living_room_group"]) == 2
