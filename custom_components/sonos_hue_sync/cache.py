
import time
from collections import OrderedDict
class PaletteCache:
    def __init__(self,max_size=100,ttl=3600):
        self.cache=OrderedDict()
        self.max_size=max_size
        self.ttl=ttl
    def exists(self,k):
        if k in self.cache:
            v,t=self.cache[k]
            if time.time()-t<self.ttl: return True
            del self.cache[k]
        return False
    def get(self,k):
        v,t=self.cache.pop(k)
        self.cache[k]=(v,t)
        return v
    def set(self,k,v):
        if k in self.cache: self.cache.pop(k)
        elif len(self.cache)>=self.max_size: self.cache.popitem(last=False)
        self.cache[k]=(v,time.time())
