import sqlite3
import utils

db = utils.get_db()

cur = db.cursor()
update = db.cursor()
cur.execute("SELECT rowid, first_name FROM testifiers WHERE first_name LIKE '% %'")
for rowid, name in cur:
    print(rowid, name)
    try:
        update.execute("UPDATE testifiers SET first_name = ? WHERE rowid = ?", (name.strip(), rowid))
    except sqlite3.IntegrityError:
        update.execute("DELETE FROM testifiers WHERE rowid = ?", (rowid,))
db.commit()
