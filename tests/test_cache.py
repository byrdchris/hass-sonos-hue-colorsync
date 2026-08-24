from __future__ import annotations

import time
from custom_components.media_hue_sync.cache import PaletteCache


def test_cache_set_get_and_exists():
    cache = PaletteCache(max_size=3, ttl=10)
    palette = [(255, 0, 0), (0, 255, 0)]

    assert not cache.exists("album1")
    cache.set("album1", palette)
    assert cache.exists("album1")
    assert cache.get("album1") == palette


def test_cache_lru_eviction():
    cache = PaletteCache(max_size=2, ttl=10)
    cache.set("k1", [(1, 1, 1)])
    cache.set("k2", [(2, 2, 2)])
    assert cache.exists("k1")
    assert cache.exists("k2")

    # Adding 3rd item should evict oldest (k1)
    cache.set("k3", [(3, 3, 3)])
    assert not cache.exists("k1")
    assert cache.exists("k2")
    assert cache.exists("k3")


def test_cache_ttl_expiration():
    cache = PaletteCache(max_size=5, ttl=0.1)
    cache.set("quick", [(10, 10, 10)])
    assert cache.exists("quick")

    time.sleep(0.15)
    assert not cache.exists("quick")
