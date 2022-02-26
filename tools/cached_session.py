import requests_cache
import datetime

class CustomCachedSession(requests_cache.CachedSession):
    def request(self, method: str, url: str, force_fetch=False, **kwargs):
        response = super().request(method, url, **kwargs)
        if response.from_cache and force_fetch: 
            response = super().request(method, url, expire_after=0, **kwargs)
            if response.status_code != 200:
                print(url, response.status_code)
                return response
            # Delete by url to ensure we clear the cache.
            self.cache.delete_url(url)
            self.cache.save_response(response)
        return response
