from __future__ import annotations

# Data models, TypedDicts, and type definitions for Media Hue Sync.
# brief-code-commented-build: moderate block-level comments added for maintainability.

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

RGB = tuple[int, int, int]
XY = tuple[float, float]

class PaletteMetrics(TypedDict, total=False):
    average_saturation: float
    average_brightness: float
    dark_ratio: float
    bright_neutral_ratio: float
    neutral_ratio: float
    vivid_ratio: float
    contrast: float
    top_color_block_ratio: float
    dominant_color_block_ratio: float
    color_diversity: float

class AutoStyleDiagnostics(TypedDict, total=False):
    enabled: bool
    detected_style: str
    confidence: Literal["low", "medium", "high"]
    reasons: list[str]
    behavior: str
    metrics: PaletteMetrics
    monochrome_guardrail: bool
    scores: dict[str, float]
    applied_style: str
    classifier_style: str
    confidence_fallback_applied: bool

class CoherenceDiagnostics(TypedDict, total=False):
    mode: str
    raw_mode: str
    applied: bool
    removed_colors: list[str]
    preserved_accent_colors: list[str]
    dominant_hue_degrees: float | None
    dominant_cluster_score: float | None
    reason: str | None

class FinalPaletteGuardrails(TypedDict, total=False):
    applied: bool
    reason: str
    detected_style: str | None
    confidence: str | None
    neutral_tone_handling: str | None
    before: list[str]
    after: list[str]

class GradientNeutralReplacement(TypedDict):
    from_color: list[int]
    to_color: list[int]
    reason: str

class GradientDiagnostics(TypedDict, total=False):
    entity_id: str
    gradient_requested: bool
    gradient_applied: bool
    gradient_colors: list[list[int]]
    gradient_points: int
    gradient_order_mode: str
    gradient_representative_color: list[int]
    gradient_representative_color_source: str
    gradient_representative_white_suppressed: bool
    gradient_rotation_offset: int
    gradient_rotation_suppressed: bool
    gradient_luminance_values: list[float]
    gradient_sort_basis: str
    gradient_detail_selection: str
    gradient_order_lock: bool
    gradient_order_lock_reason: str | None
    gradient_brightness: int
    gradient_error: str
    hue_resource_id: str
    hue_resource_name: str
    hue_gradient_info: str
    gradient_detection_source: str
    apply_mode: str
    apply_reason: str

@dataclass
class ResolvedTargetEntities:
    """Represents resolved light entities after group expansion and exclusions."""
    selected_entities: list[str] = field(default_factory=list)
    resolved_lights: list[str] = field(default_factory=list)
    expanded_groups: dict[str, list[str]] = field(default_factory=dict)
    excluded_lights: list[str] = field(default_factory=list)
    unavailable_lights: list[str] = field(default_factory=list)
