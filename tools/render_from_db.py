import utils
import pathlib

db = utils.get_db(readonly=True)

cur = db.cursor()

bills_path = pathlib.Path("bill/2023-24/")

cur.execute("SELECT bills.rowid, prefix, id, description, COUNT(testifiers.sign_in_time) as ts FROM bills, testifiers WHERE bills.rowid = testifiers.bill_rowid GROUP BY testifiers.bill_rowid ORDER BY ts DESC")
index_lines = []
for row in cur:
    counts = db.cursor()
    counts.execute("SELECT position, COUNT(testifiers.position_rowid) FROM positions, testifiers WHERE positions.rowid = testifiers.position_rowid AND bill_rowid = ? GROUP BY testifiers.position_rowid", (row[0],))
    position_counts = dict(counts)
    prefix = row[1]
    bill_number = row[2]
    description = row[3]
    pro = position_counts.get("Pro", 0)
    con = position_counts.get("Con", 0)
    other = position_counts.get("Other", 0)
    bill_path = pathlib.Path(prefix.lower()) / str(bill_number)
    index_lines.append(f"* [{prefix} {bill_number}]({bill_path}) - {description} {pro}👍 {con}👎 {other}❓")

bills_index = bills_path / "README.md"
bills_index.write_text("\n".join(index_lines))
