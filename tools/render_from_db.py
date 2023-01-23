import utils
import pathlib

db = utils.get_db(readonly=True)

cur = db.cursor()

bills_path = pathlib.Path("bill/2023-24/")

biennium = "2023-24"

REVISION_TO_NAME = {
    "1": "Original Bill",
    "S": "Substitute Bill"
}

POSITION_TO_EMOJI = {
    "Pro": "👍",
    "Con": "👎",
    "Other": "❓"
}

cur.execute("SELECT bills.rowid, prefix, number, COUNT(testifiers.sign_in_time) as ts FROM bills, testifiers, agenda_items WHERE bills.rowid = agenda_items.bill_rowid AND agenda_items.rowid = testifiers.agenda_item_rowid GROUP BY testifiers.agenda_item_rowid ORDER BY ts DESC, number ASC")
index_lines = []
for row in cur:
    counts = db.cursor()
    counts.execute("SELECT position, COUNT(testifiers.position_rowid) FROM positions, testifiers, agenda_items WHERE positions.rowid = testifiers.position_rowid AND agenda_items.rowid = testifiers.agenda_item_rowid AND bill_rowid = ? GROUP BY testifiers.position_rowid", (row[0],))
    position_counts = dict(counts)
    prefix = row[1]
    bill_number = row[2]
    latest_revision = db.cursor()
    latest_revision.execute("SELECT description FROM revisions WHERE bill_rowid = ? ORDER BY modified_time DESC", (row[0],))
    description = latest_revision.fetchone()[0]
    pro = position_counts.get("Pro", 0)
    con = position_counts.get("Con", 0)
    other = position_counts.get("Other", 0)
    bill_path = pathlib.Path(prefix.lower()) / str(bill_number)
    index_lines.append(f"* [{prefix} {bill_number}]({bill_path}) - {description} {pro}👍 {con}👎 {other}❓")

bills_index = bills_path / "README.md"
bills_index.write_text("\n".join(index_lines))

cur.execute("SELECT rowid FROM bienniums WHERE name = ?;", ("2023-24",))
biennium_rowid = cur.fetchone()[0]

cur.execute("SELECT rowid, prefix, number FROM bills WHERE biennium_rowid = ?", (biennium_rowid,))

vips = set()
vio = set()

for bill_rowid, prefix, bill_number in cur:
    breadcrumb = f"[wa-law.org](/) > [bill](/bill/) > [{biennium}](/bill/{biennium}/) > [{prefix} {bill_number}](/bill/{biennium}/{prefix.lower()}/{bill_number}/)"
    bill_readme = [
        breadcrumb,
        "",
        f"# {prefix} {bill_number}",
        f"[leg.wa.gov](https://app.leg.wa.gov/billsummary?BillNumber={bill_number}&Year=2023&Initiative=false)",
        "",
        "## Revisions"
    ]

    bill_path = bills_path / prefix.lower() / str(bill_number)

    revisions = db.cursor()
    revisions.execute("SELECT rowid, version, description, source_url FROM revisions WHERE bill_rowid = ? ORDER BY modified_time", (bill_rowid,))

    for revision_rowid, revision, description, source_url in revisions:
        if revision not in REVISION_TO_NAME:
            print(bill_number, revision)
        revision_path = bill_path / revision

        bill_readme.append(f"* [{REVISION_TO_NAME[revision]}](" + str(revision_path.relative_to(bill_path)) + "/)")

        revision_readme = [
            breadcrumb + f" > [{REVISION_TO_NAME[revision]}](/bill/{biennium}/{prefix.lower()}/{bill_number}/{revision}/)",
            "",
            f"# {prefix} {bill_number} - {description}"
        ]
        revision_readme.append("")
        source_url = source_url.replace(" ", "%20")
        revision_readme.append(f"[Source]({source_url})")
        revision_readme.append("")
        section_cursor = db.cursor()
        section_cursor.execute("SELECT name, raw_text, markdown FROM sections WHERE revision_rowid = ? ORDER BY number ASC", (revision_rowid,))
        for bill_section, raw_text, markdown in section_cursor:
            revision_readme.append(f"## Section {bill_section}")
            if markdown:
                revision_readme.append(markdown)
            elif raw_text:
                blockquote = raw_text.splitlines()
                blockquote = "\n> ".join(blockquote)
                revision_readme.append(blockquote)
                revision_readme.append("")
        revision_path.mkdir(parents=True, exist_ok=True)
        rm = revision_path / "README.md"
        rm.write_text("\n".join(revision_readme))
    bill_readme.append("")

    bill_readme.append("## Positions")
    for position in POSITION_TO_EMOJI:
        positions = db.cursor()
        positions.execute("SELECT rowid FROM positions WHERE position = ?", (position,))
        p_rowid = positions.fetchone()[0]
        count = db.cursor()
        count.execute("SELECT COUNT(testifiers.position_rowid) FROM testifiers, agenda_items WHERE testifiers.position_rowid = ? AND agenda_items.rowid = testifiers.agenda_item_rowid AND bill_rowid = ? GROUP BY testifiers.position_rowid", (p_rowid, bill_rowid))
        count = count.fetchone()
        if count:
            count = count[0]
        else:
            count = 0
        emoji = POSITION_TO_EMOJI[position]
        bill_readme.append(f"### {count} {emoji} - {position}")

        testifiers = db.cursor()
        testifiers.execute("SELECT first_name, last_name, organization FROM testifiers, agenda_items WHERE testifying AND testifiers.position_rowid = ? AND agenda_items.rowid = testifiers.agenda_item_rowid AND bill_rowid = ?", (p_rowid, bill_rowid))
        testifiers = testifiers.fetchall()
        if testifiers:
            bill_readme.append("#### Testifying")
            for first_name, last_name, organization in testifiers:
                lobbyist = db.cursor()
                lobbyist.execute("SELECT people.rowid, lobbyist_employment.lobbying_firm_rowid FROM people, lobbyist_employment WHERE first_name = ? AND last_name = ? AND people.rowid = lobbyist_employment.person_rowid", (first_name, last_name))
                lobbyist = lobbyist.fetchone()
                if lobbyist:
                    vips.add(lobbyist[0])
                    lobbyist = "💵"
                else:
                    lobbyist = ""
                if organization:
                    organization = organization.strip()
                    org = db.cursor()
                    org.execute("SELECT rowid, canonical_entry, slug FROM organizations WHERE name = ?", (organization,))
                    org = org.fetchone()
                    if org:
                        # Check the canonical version
                        if org[1]:
                            canonical = db.cursor()
                            canonical.execute("SELECT rowid, canonical_entry, slug FROM organizations WHERE rowid = ?", (org[1],))
                            org = canonical.fetchone()
                        vio.add(org[0])
                        slug = org[2]
                        organization = f"[{organization}](/org/{slug}/)"
                    organization = " - " + organization
                bill_readme.append(f"* {lobbyist}{first_name} {last_name}{organization}")
        bill_readme.append("")


    rm = bill_path / "README.md"
    rm.write_text("\n".join(bill_readme))


orgs_path = pathlib.Path("org/")
for org_rowid in vio:
    cur = db.cursor()
    cur.execute("SELECT name, canonical_entry, slug FROM organizations WHERE rowid = ?", (org_rowid,))
    name, canonical, slug = cur.fetchone()

    org_path = orgs_path / slug
    org_path.mkdir(parents=True, exist_ok=True)
    org_readme_path = org_path / "README.md"
    org_readme = [
        f"# {name}",
        f"## Active bills"
    ]
    org_readme_path.write_text("\n".join(org_readme))
