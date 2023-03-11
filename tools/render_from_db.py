import datetime
import utils
import pathlib

db = utils.get_db(readonly=True)

cur = db.cursor()

bills_path = pathlib.Path("bill/2023-24/")

biennium = "2023-24"

REVISION_TO_NAME = {
    "1": "Original Bill",
    "S": "Substitute Bill",
    "S.E": "Engrossed Substitute",
    "S2": "Second Substitute",
    "S2.E": "Engrossed Second Substitute",
    "S.SL": "Session Law",
    "S.PL": "Passed Legislature"
}

POSITION_TO_EMOJI = {
    "Pro": "👍",
    "Con": "👎",
    "Other": "❓"
}

now = datetime.datetime.now()

cur.execute("SELECT bills.rowid, prefix, number, COUNT(testifiers.sign_in_time) as ts, meetings.start_time, meetings.mId, committees.acronym FROM committees, bills, testifiers, agenda_items, meetings WHERE datetime(meetings.start_time) > datetime(?) AND committees.rowid = meetings.committee_rowid AND meetings.rowid = agenda_items.meeting_rowid AND bills.rowid = agenda_items.bill_rowid AND agenda_items.rowid = testifiers.agenda_item_rowid GROUP BY testifiers.agenda_item_rowid ORDER BY datetime(start_time) ASC, acronym ASC, ts ASC, number ASC", (now,))
index_lines = []
index_lines.append("# 2023-24 Bills")
index_lines.append("## Upcoming hearings")
for row in cur:
    counts = db.cursor()
    counts.execute("SELECT position, COUNT(testifiers.position_rowid) FROM positions, testifiers, agenda_items WHERE positions.rowid = testifiers.position_rowid AND agenda_items.rowid = testifiers.agenda_item_rowid AND bill_rowid = ? GROUP BY testifiers.position_rowid", (row[0],))
    position_counts = dict(counts)
    prefix = row[1]
    bill_number = row[2]
    start_time = datetime.datetime.strptime(row[4].split("+")[0], "%Y-%m-%d %H:%M:%S")
    start_time_str = start_time.strftime("%a %m/%d %I:%M %p")
    latest_revision = db.cursor()
    latest_revision.execute("SELECT description FROM revisions WHERE bill_rowid = ? ORDER BY modified_time DESC", (row[0],))
    description = latest_revision.fetchone()[0]
    pro = position_counts.get("Pro", 0)
    con = position_counts.get("Con", 0)
    other = position_counts.get("Other", 0)
    bill_path = pathlib.Path(prefix.lower()) / str(bill_number)
    index_lines.append(f"* [{row[6]} {start_time_str}](https://app.leg.wa.gov/committeeschedules/Home/Agenda/{row[5]}) [{prefix} {bill_number}]({bill_path}) - {description} {pro}👍 {con}👎 {other}❓")
index_lines.append("")

index_lines.append("## Heard bills")
cur.execute("SELECT bills.rowid, prefix, number, COUNT(testifiers.sign_in_time) as ts FROM bills, testifiers, agenda_items, meetings WHERE datetime(meetings.start_time) < datetime(?) AND meetings.rowid = agenda_items.meeting_rowid AND bills.rowid = agenda_items.bill_rowid AND agenda_items.rowid = testifiers.agenda_item_rowid GROUP BY testifiers.agenda_item_rowid ORDER BY ts DESC, number ASC", (now,))
for row in cur:
    counts = db.cursor()
    counts.execute("SELECT position, COUNT(testifiers.position_rowid) FROM positions, testifiers, agenda_items WHERE positions.rowid = testifiers.position_rowid AND agenda_items.rowid = testifiers.agenda_item_rowid AND bill_rowid = ? GROUP BY testifiers.position_rowid", (row[0],))
    position_counts = dict(counts)
    prefix = row[1]
    bill_number = row[2]
    status = db.cursor()
    status.execute("SELECT status from bill_status, bill_statuses WHERE bill_rowid = ? AND bill_status_rowid = bill_statuses.rowid ORDER BY action_date DESC LIMIT 1", (row[0],))
    status = status.fetchone()[0]
    latest_revision = db.cursor()
    latest_revision.execute("SELECT description FROM revisions WHERE bill_rowid = ? ORDER BY modified_time DESC", (row[0],))
    description = latest_revision.fetchone()[0]
    pro = position_counts.get("Pro", 0)
    con = position_counts.get("Con", 0)
    other = position_counts.get("Other", 0)
    bill_path = pathlib.Path(prefix.lower()) / str(bill_number)
    index_lines.append(f"* [{prefix} {bill_number}]({bill_path}) - {description} {pro}👍 {con}👎 {other}❓ - {status}")


bills_index = bills_path / "README.md"
bills_index.write_text("\n".join(index_lines))

cur.execute("SELECT rowid FROM bienniums WHERE name = ?;", ("2023-24",))
biennium_rowid = cur.fetchone()[0]

cur.execute("SELECT rowid, prefix, number FROM bills WHERE biennium_rowid = ?", (biennium_rowid,))

vips = set()
vio = set()

now = datetime.datetime.now()

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

    articles = db.cursor()
    articles.execute("SELECT organizations.name, organizations.slug, web_articles.url, text_fragment, title, date_posted FROM web_articles, organizations WHERE bill_rowid = ? AND web_articles.organization_rowid = organizations.rowid ORDER BY date_posted DESC", (bill_rowid,))
    articles = articles.fetchall()
    if articles:
        bill_readme.append("## Articles")
        for org, org_slug, url, text_fragment, title, date_posted in articles:
            # mtime = date_posted
            # if date_posted:
            #     mtime = date_posted.strftime("%m/%d/%Y")
            bill_readme.append(f"* [{org}](/org/{org_slug}/) - [{title}]({url}{text_fragment})")
        bill_readme.append("")

    bill_readme.append("## Meetings")
    meetings = db.cursor()
    meetings.execute("SELECT agenda_items.rowid, meetings.committee_rowid, start_time, meetings.notes, agenda_items.description FROM agenda_items, meetings WHERE agenda_items.meeting_rowid = meetings.rowid AND agenda_items.bill_rowid = ? ORDER BY start_time DESC, agenda_items.description", (bill_rowid,))

    for item_rowid, committee_rowid, start_time, notes, description in meetings:
        committee = db.cursor()
        committee.execute("SELECT name, acronym FROM committees WHERE rowid = ?", (committee_rowid,))
        committee = committee.fetchone()

        start_time = datetime.datetime.strptime(start_time.split("+")[0], "%Y-%m-%d %H:%M:%S")
        start_time_str = start_time.strftime("%a %m/%d %I:%M %p")

        bill_readme.append(f"### {start_time_str} - {committee[0]} ({committee[1]}): {description}")
        if start_time >= now:
            testify_options = db.cursor()
            testify_options.execute("SELECT option, url FROM testimony_links, testimony_options WHERE testimony_links.option_rowid = testimony_options.rowid AND agenda_item_rowid = ?", (item_rowid,))
            bill_readme.append("Sign up to testify:")
            for option, url in testify_options:
                bill_readme.append(f"* [{option}](https://app.leg.wa.gov{url})")
            bill_readme.append("")
        for position in POSITION_TO_EMOJI:
            positions = db.cursor()
            positions.execute("SELECT rowid FROM positions WHERE position = ?", (position,))
            p_rowid = positions.fetchone()[0]
            count = db.cursor()
            count.execute("SELECT COUNT(position_rowid) FROM testifiers WHERE position_rowid = ? AND agenda_item_rowid = ? GROUP BY position_rowid", (p_rowid, item_rowid))
            count = count.fetchone()
            if count:
                count = count[0]
            else:
                count = 0
            emoji = POSITION_TO_EMOJI[position]
            bill_readme.append(f"#### {count} {emoji} - {position}")

            testifiers = db.cursor()
            testifiers.execute("SELECT first_name, last_name, organization FROM testifiers WHERE testifying AND position_rowid = ? AND agenda_item_rowid = ? ORDER BY sign_in_time", (p_rowid, item_rowid))
            testifiers = testifiers.fetchall()
            if testifiers:
                bill_readme.append("Testifying:")
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
        f"# {name}"
    ]

    last_bill_number = None
    bill_info = ()
    testifiers = []
    position_totals = {"Pro": 0, "Con": 0, "Other": 0}
    cur.execute("SELECT bill_rowid, prefix, number, position, testifying, first_name, last_name FROM testifiers, agenda_items, bills, positions WHERE agenda_items.rowid = agenda_item_rowid AND bill_rowid = bills.rowid AND position_rowid = positions.rowid AND organization = ? ORDER BY number, sign_in_time", (name,))
    for bill_rowid, prefix, number, position, testifying, first_name, last_name in cur:
        if number != last_bill_number:
            if last_bill_number:
                old_bill_rowid, old_prefix, old_bill_number = bill_info
                bill_cur = db.cursor()
                bill_cur.execute("SELECT description FROM revisions WHERE bill_rowid = ? ORDER BY modified_time DESC LIMIT 1", (old_bill_rowid,))
                description = bill_cur.fetchone()[0]
                org_readme.append("")
                positions = " ".join(POSITION_TO_EMOJI[p] + str(position_totals[p]) if position_totals[p] > 0 else "" for p in POSITION_TO_EMOJI)
                org_readme.append(f"## [{old_prefix} {old_bill_number}](/bill/{biennium}/{old_prefix.lower()}/{old_bill_number}/) - {description} {positions}")
                org_readme.extend(testifiers)
            bill_info = (bill_rowid, prefix, number)
            last_bill_number = number
            position_totals = {"Pro": 0, "Con": 0, "Other": 0}
            testifiers = []
        position_totals[position] += 1
        if testifying:
            lobbyist = db.cursor()
            lobbyist.execute("SELECT people.rowid, lobbyist_employment.lobbying_firm_rowid FROM people, lobbyist_employment WHERE first_name = ? AND last_name = ? AND people.rowid = lobbyist_employment.person_rowid", (first_name, last_name))
            lobbyist = lobbyist.fetchone()
            if lobbyist:
                lobbyist = "💵"
            else:
                lobbyist = ""
            testifiers.append(f"* {POSITION_TO_EMOJI[position]}{lobbyist} {first_name} {last_name}")

    if bill_info:
        old_bill_rowid, old_prefix, old_bill_number = bill_info
        bill_cur = db.cursor()
        bill_cur.execute("SELECT description FROM revisions WHERE bill_rowid = ? ORDER BY modified_time DESC LIMIT 1", (old_bill_rowid,))
        description = bill_cur.fetchone()[0]
        positions = " ".join(POSITION_TO_EMOJI[p] + str(position_totals[p])  if position_totals[p] > 0 else "" for p in POSITION_TO_EMOJI)
        org_readme.append("")
        org_readme.append(f"## [{old_prefix} {old_bill_number}](/bill/{biennium}/{old_prefix.lower()}/{old_bill_number}/) - {description} {positions}")
        org_readme.extend(testifiers)
    org_readme_path.write_text("\n".join(org_readme))
