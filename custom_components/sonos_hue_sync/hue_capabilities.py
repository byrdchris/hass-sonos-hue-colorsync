from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

# Model IDs observed on Hue gradient devices. This list is intentionally used as
# a fallback, not the only source of truth, because HA/aiohue capability metadata
# can vary between Home Assistant releases and Hue firmware versions.
GRADIENT_MODEL_IDS = {
    # Hue Signe gradient lamps
    "LCX003",
    "LCX004",
    # Hue Play gradient lightstrip sizes commonly report LCX002.
    "LCX002",
    # Hue Play gradient tube, large/compact variants.
    "915005987201",
    "915005987301",
    "915005987401",
    "915005987501",
    "915005988601",
    "915005988602",
    "915005988701",
    "915005988801",
    # Hue gradient lightstrip ambience variants.
    "929002994901",
    "929002994902",
    "929002994903",
    "929003498501",
    "929003498601",
    "929003498701",
}

GRADIENT_TEXT_HINTS = (
    "gradient",
    "signe",
    "play gradient",
    "gradient tube",
    "gradient lightstrip",
    "lightstrip plus gradient",
)


@dataclass(frozen=True)
class HueGradientCapability:
    entity_id: str
    capable: bool
    source: str
    model: str | None = None
    model_id: str | None = None
    friendly_name: str | None = None
    resource_has_gradient: bool | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _device_for_entity(hass: HomeAssistant, entity_id: str):
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entry = entity_registry.async_get(entity_id)
    if not entry or not entry.device_id:
        return entry, None
    return entry, device_registry.async_get(entry.device_id)


def hue_device_info(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    entry, device = _device_for_entity(hass, entity_id)
    state = hass.states.get(entity_id)
    return {
        "entity_id": entity_id,
        "friendly_name": state.attributes.get("friendly_name") if state else None,
        "unique_id": entry.unique_id if entry else None,
        "original_name": entry.original_name if entry else None,
        "registry_name": entry.name if entry else None,
        "device_name": device.name if device else None,
        "device_name_by_user": device.name_by_user if device else None,
        "manufacturer": device.manufacturer if device else None,
        "model": device.model if device else None,
        "model_id": device.model_id if device else None,
        "sw_version": device.sw_version if device else None,
    }


def _looks_gradient_from_text(values: list[Any]) -> bool:
    haystack = " ".join(str(value or "").casefold() for value in values)
    return any(hint in haystack for hint in GRADIENT_TEXT_HINTS)


def gradient_capability_from_ha(hass: HomeAssistant, entity_id: str, resource_gradient_info: Any = None) -> HueGradientCapability:
    """Return the best known gradient capability for a Home Assistant light.

    Capability confidence order:
    1. Hue API resource exposes a gradient feature.
    2. Hue device registry model_id is a known gradient model.
    3. Entity/device names strongly indicate a Hue gradient product.

    The model/name fallback is deliberate: some HA/aiohue versions expose parsed
    gradient objects inconsistently, especially on Play gradient strips/tubes.
    """
    info = hue_device_info(hass, entity_id)
    state = hass.states.get(entity_id)
    model_id = str(info.get("model_id") or "")
    model = str(info.get("model") or "")
    friendly_name = str(info.get("friendly_name") or "")

    if resource_gradient_info is not None:
        return HueGradientCapability(
            entity_id=entity_id,
            capable=True,
            source="hue_resource_gradient_feature",
            model=model or None,
            model_id=model_id or None,
            friendly_name=friendly_name or None,
            resource_has_gradient=True,
            reason="Hue runtime resource exposes a gradient feature.",
        )

    if model_id and model_id in GRADIENT_MODEL_IDS:
        return HueGradientCapability(
            entity_id=entity_id,
            capable=True,
            source="known_hue_gradient_model_id",
            model=model or None,
            model_id=model_id or None,
            friendly_name=friendly_name or None,
            resource_has_gradient=False,
            reason="Device model is known to support Hue gradients.",
        )

    text_values = [
        entity_id,
        friendly_name,
        info.get("original_name"),
        info.get("registry_name"),
        info.get("device_name"),
        info.get("device_name_by_user"),
        model,
        model_id,
    ]
    if state is not None:
        effects = state.attributes.get("effect_list") or []
        if isinstance(effects, list):
            text_values.extend(effects)

    if _looks_gradient_from_text(text_values):
        return HueGradientCapability(
            entity_id=entity_id,
            capable=True,
            source="gradient_name_hint",
            model=model or None,
            model_id=model_id or None,
            friendly_name=friendly_name or None,
            resource_has_gradient=False,
            reason="Entity or device naming indicates a Hue gradient product.",
        )

    return HueGradientCapability(
        entity_id=entity_id,
        capable=False,
        source="not_gradient_capable",
        model=model or None,
        model_id=model_id or None,
        friendly_name=friendly_name or None,
        resource_has_gradient=False,
        reason="No Hue gradient capability, known model ID, or strong gradient name hint was found.",
    )


def is_gradient_capable_entity(hass: HomeAssistant, entity_id: str) -> bool:
    return gradient_capability_from_ha(hass, entity_id).capable
