
from dataclasses import dataclass
from typing import Optional

@dataclass
class MediaSnapshot:
    entity_id: str
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    artwork_url: Optional[str] = None
    state: Optional[str] = None
    source: str = "sonos"
    capability: str = "full"


def resolve_media_snapshot(entity_id: str, state):
    attrs = state.attributes if state else {}
    return MediaSnapshot(
        entity_id=entity_id,
        title=attrs.get("media_title"),
        artist=attrs.get("media_artist"),
        album=attrs.get("media_album_name"),
        artwork_url=attrs.get("entity_picture") or attrs.get("media_image_url"),
        state=state.state if state else None,
        source="sonos",
        capability="full",
    )
