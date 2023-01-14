import lzma
import sqlite3
import sys

db = sqlite3.connect("file:" + sys.argv[-2] + "?mode=ro", uri=True)
cur = db.cursor()
cur.execute("SELECT url, content_xz, first_fetch, last_fetch FROM pages WHERE instr(url, ?) > 0 ORDER BY url, first_fetch", (sys.argv[-1],))
for url, content_xz, first_fetch, last_fetch in cur:
    print(url, first_fetch, last_fetch)
    print(lzma.decompress(content_xz))
    print()
