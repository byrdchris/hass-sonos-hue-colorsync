# Palette cache. Stores album palettes to avoid repeated image processing and reduce flicker.
# brief-code-commented-build: moderate block-level comments added for maintainability.
import time
from collections import OrderedDict

# PaletteCache stores bounded album color results with a simple TTL.
# This avoids repeated processing while preventing stale cache growth.
class PaletteCache:
    def __init__(self, max_size=100, ttl=3600):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def exists(self, key):
        if key in self.cache:
            value, ts = self.cache[key]
            if time.time() - ts < self.ttl:
                return True
            del self.cache[key]
        return False

    def get(self, key):
        value, ts = self.cache.pop(key)
        self.cache[key] = (value, ts)
        return value

    def set(self, key, value):
        if key in self.cache:
            self.cache.pop(key)
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = (value, time.time())
