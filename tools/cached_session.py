import requests_cache
import datetime

class CustomCachedSession(requests_cache.CachedSession):
    def request(self, method: str, url: str, force_fetch=False, **kwargs):
        response = super().request(method, url, **kwargs)
        if response.from_cache and force_fetch: 
            response = super().request(method, url, expire_after=0, **kwargs)
            self.cache.save_response(response)
        return response
