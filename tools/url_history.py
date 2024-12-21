"""Simple HTTP get wrapper that stores the history of fetched urls."""

import asyncio
import httpx
import stamina
import sqlite3
import lzma
import hashlib
import datetime
import urllib3
import time

# import logging

# from http.client import HTTPConnection
# HTTPConnection.debuglevel = 1

# logging.basicConfig() # you need to initialize logging, otherwise you will not see anything from requests
# logging.getLogger().setLevel(logging.DEBUG)
# requests_log = logging.getLogger("urllib3")
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True

headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0'}

__version__ = "0.0.1"

class HistorySession:

    def __init__(self, filename="requests-history.db"):
        self.db = sqlite3.connect(filename)

        self.already_refetched = set()

        cur = self.db.cursor()
        try:
            cur.execute("CREATE TABLE pages (url text, sha256 blob, content_xz blob, first_fetch timestamp, last_fetch timestamp)")
        except sqlite3.OperationalError:
            pass

        cur.execute("PRAGMA user_version;")
        db_version = cur.fetchone()[0]
        if db_version < 1:
            cur.execute("ALTER TABLE pages ADD COLUMN last_modified timestamp")
            cur.execute("PRAGMA user_version = 1;")
            self.db.commit()

    async def get(self, url, fetch_again=False, index=-1, crawl_delay=0, only_after=None):
        now = datetime.datetime.now()
        cur = self.db.cursor()
        cur.execute("SELECT sha256, content_xz, first_fetch, last_fetch FROM pages WHERE url = ? ORDER BY last_fetch ASC", (url,))
        past_fetch = cur.fetchall()
        if index < -1 and len(past_fetch) > 0 and -index > len(past_fetch):
            return None
        if not past_fetch or (fetch_again and url not in self.already_refetched):
            if only_after:
                headers["If-Modified-Since"] = only_after.strftime("%a, %d %b %Y %H:%M:%S GMT")
            elif "If-Modified-Since" in headers:
                del headers["If-Modified-Since"]
            async for attempt in stamina.retry_context(on=httpx.HTTPError, attempts=3):
                with attempt:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(url, headers=headers, follow_redirects=True)
                    if response.status_code == 304:
                        return None
                    response.raise_for_status()

            self.already_refetched.add(url)
            # Hide failing requests if we have an older version
            if response.status_code != httpx.codes.OK:
                if past_fetch:
                    return lzma.decompress(past_fetch[index][1])
                return None
            content = response.content
            sha256 = hashlib.sha256(content).digest()
            last_modified = response.headers.get("Last-Modified", None)
            if past_fetch and sha256 == past_fetch[-1][0]:
                cur.execute("UPDATE pages SET last_fetch = ? WHERE url = ? AND last_fetch = ?", (now, url, past_fetch[-1][3]))
                cur.execute("UPDATE pages SET last_modified = ? WHERE url = ? AND last_fetch = ? AND last_modified IS NULL", (last_modified, url, past_fetch[-1][3]))
            else:
                content_xz = lzma.compress(content)
                cur.execute("INSERT INTO pages (url, sha256, content_xz, last_modified, first_fetch, last_fetch) VALUES (?, ?, ?, ?, ?, ?)", (url, sha256, content_xz, last_modified, now, now))
            self.db.commit()
            await asyncio.sleep(crawl_delay)
            return content
        return lzma.decompress(past_fetch[index][1])

    async def close(self):
        await asyncio.sleep(0)
        self.db.commit()

if __name__ == "__main__":
    session = HistorySession()
    session.get("https://accesshub.pdc.wa.gov/node/90569")
    session.get("https://accesshub.pdc.wa.gov/node/90569", fetch_again=True)
