import utils
import pathlib

db = utils.get_db(readonly=True)

cur = db.cursor()

bills_path = pathlib.Path("bill/2023-24/")

cur.execute("SELECT bills.rowid, prefix, id, bills.description, COUNT(testifiers.sign_in_time) as ts FROM bills, testifiers, agenda_items WHERE bills.rowid = agenda_items.bill_rowid AND agenda_items.rowid = testifiers.agenda_item_rowid GROUP BY testifiers.agenda_item_rowid ORDER BY ts DESC")
index_lines = []
for row in cur:
    counts = db.cursor()
    counts.execute("SELECT position, COUNT(testifiers.position_rowid) FROM positions, testifiers, agenda_items WHERE positions.rowid = testifiers.position_rowid AND agenda_items.rowid = testifiers.agenda_item_rowid AND bill_rowid = ? GROUP BY testifiers.position_rowid", (row[0],))
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

cur.execute("SELECT rowid FROM sessions WHERE name = ?;", (str(2023),))
session_rowid = cur.fetchone()[0]

cur.execute("SELECT rowid, prefix, id, bills.description FROM bills WHERE session_rowid = ? AND version = '1'", (session_rowid,))
for rowid, prefix, bill_number, description in cur:
    print(prefix, bill_number)
    bill_readme = []

    bill_path = bills_path / prefix.lower() / str(bill_number)

    for revision in ("1",):
        revision_path = bill_path / revision

        bill_readme.append("* [Original Bill](" + str(revision_path.relative_to(bill_path)) + "/)")

        revision_readme = [f"# {prefix} {bill_number} - {description}"]
        revision_readme.append("")
        revision_readme.append("[Source]()")
        section_cursor = db.cursor()
        section_cursor.execute("SELECT bill_section, markdown FROM sections WHERE bill_rowid = ? ORDER BY bill_section ASC", (rowid,))
        for bill_section, markdown in section_cursor:
            revision_readme.append(f"## Section {bill_section}")
            if markdown:
                revision_readme.append(markdown)
        revision_path.mkdir(parents=True, exist_ok=True)
        rm = revision_path / "README.md"
        print(rm)
        rm.write_text("\n".join(revision_readme))


    rm = bill_path / "README.md"
    rm.write_text("\n".join(bill_readme))
