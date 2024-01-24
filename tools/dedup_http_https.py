import sqlite3
import utils

db = utils.get_db()

cur = db.cursor()
delete = db.cursor()
cur.execute("SELECT rowid, url, text_fragment FROM web_articles WHERE url LIKE 'http:%'")
for rowid, url, text_fragment in cur:
    https = url.replace("http:", "https:")
    delete.execute("SELECT COUNT(url) FROM web_articles WHERE url = ? and text_fragment = ?", (https, text_fragment))
    count = delete.fetchone()[0]
    print(rowid, url, text_fragment, count)
    if count == 0:
        continue

    delete.execute("DELETE FROM web_articles WHERE rowid = ?", (rowid,))
db.commit()
