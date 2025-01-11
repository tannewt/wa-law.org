import utils

db = utils.get_db()

cur = db.cursor()

fixed_count = 0
cur.execute("SELECT rowid, start_time FROM meetings WHERE start_time like '% %'")
updater = db.cursor()
for row in cur:
	rowid, date = row
	if " " not in date:
		continue
	new_date = date.replace(" ", "T")

	# print("fixed", rowid, date)
	updater.execute("UPDATE meetings SET start_time = ? WHERE rowid = ?;", (new_date, rowid))
	fixed_count += 1
	if fixed_count % 1000 == 0:
		print(fixed_count)


	db.commit()
