import utils

db = utils.get_db()

cur = db.cursor()

cur.execute("SELECT rowid, bill_rowid, action_date, history_line FROM bill_history ORDER BY bill_rowid, history_line, action_date")

last_row = None
changed = False
duplicates = []
for row in cur:
	print(row)
	if last_row is None:
		last_row = row
		continue
	
	rowid, bill, date, line = row
	last_rowid, last_bill, last_date, last_line = last_row
	last_row = row
	if " " in last_date:
		new_date = last_date.replace(" ", "T")
		if last_bill == bill and last_line == line and new_date == date:
			duplicates.append(rowid)
			print("duplicate")

for duplicate in duplicates:
	cur.execute("DELETE FROM bill_history WHERE rowid = ?;", (duplicate,))

while True:
	cur.execute("SELECT rowid, bill_rowid, action_date, history_line FROM bill_history WHERE action_date like '% %'")
	row = cur.fetchone()
	if not row:
		break
	rowid, bill, date, line = row
	if " " not in date:
		continue
	new_date = date.replace(" ", "T")

	cur.execute("UPDATE bill_history SET action_date = ? WHERE rowid = ?;", (new_date, rowid))
	print("fixed", rowid)


db.commit()
