
import time
from collections import OrderedDict

class PaletteCache:
    def __init__(self, max_size=100, ttl=3600):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def exists(self, key):
        if key in self.cache:
            v, t = self.cache[key]
            if time.time() - t < self.ttl:
                return True
            del self.cache[key]
        return False

    def get(self, key):
        v, t = self.cache.pop(key)
        self.cache[key] = (v, t)
        return v

    def set(self, key, value):
        if key in self.cache:
            self.cache.pop(key)
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = (value, time.time())
