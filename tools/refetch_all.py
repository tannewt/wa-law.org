import sqlite3
import sys
import url_history


requests = url_history.HistorySession(sys.argv[-1])

cur = requests.db.cursor()
cur.execute("SELECT url FROM pages GROUP BY url")
urls = list((x[0] for x in cur))
for url in urls:
    requests.get(url, fetch_again=True)
