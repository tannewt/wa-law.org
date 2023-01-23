import sqlite3

def add_or_update_section(path, section, contents):
    """This adds or updates a section within the markdown file. The section
       starts at the line that matches section and goes until another line that
       starts with the same number of hashes."""
    lines = path.read_text().split("\n")
    if section not in lines:
        path.write_text("\n".join(lines + ["", section] + contents))
        return
    start = lines.index(section)
    lines_before = lines[:start+1]
    end = start + 1
    hashes = section.split(" ", maxsplit=1)[0]
    section_prefix = hashes + " "
    while end < len(lines):
        if lines[end].startswith(section_prefix):
            break
        end += 1
    lines_after = lines[end:]

    path.write_text("\n".join(lines_before + contents + lines_after))

def remove_section(path, section):
    """This adds or updates a section within the markdown file. The section
       starts at the line that matches section and goes until another line that
       starts with the same number of hashes."""
    lines = path.read_text().split("\n")
    if section not in lines:
        return
    start = lines.index(section)
    lines_before = lines[:start]
    end = start + 1
    hashes = section.split(" ", maxsplit=1)[0]
    section_prefix = hashes + " "
    while end < len(lines):
        if lines[end].startswith(section_prefix):
            break
        end += 1
    lines_after = lines[end:]

    path.write_text("\n".join(lines_before + lines_after))

REPLACEMENTS = {
    "Assn": "Association",
    "Wa": "Washington",
    "Natl": "National",
    "Nw": "Northwest"
}

UNCAPITALIZE = {
    "Of": "of",
    "For": "for",
    "The": "the",
    "And": "and"
}

def canonicalize_org(org_name):
    pieces = []
    for i, piece in enumerate(org_name.split()):
        piece = piece.capitalize()
        if piece in REPLACEMENTS:
            piece = REPLACEMENTS[piece]
        if i > 0 and piece in UNCAPITALIZE:
            piece = UNCAPITALIZE[piece]
        pieces.append(piece)
    return " ".join(pieces)

def get_db(readonly=False):
    if readonly:
        return sqlite3.connect("file:wa-laws.db?mode=ro", uri=True)
    db = sqlite3.connect("wa-laws.db")

    db.execute("CREATE TABLE IF NOT EXISTS bienniums("
                    "start_year integer,"
                    "end_year integer,"
                    "name text,"
                    "UNIQUE(name)"
                ")")

    db.execute("CREATE TABLE IF NOT EXISTS sessions("
                    "biennium_rowid integer,"
                    "year integer,"
                    "name text,"
                    "FOREIGN KEY(biennium_rowid) REFERENCES bienniums(rowid)"
                    "UNIQUE(name)"
                ")")

    # db.execute("DROP TABLE IF EXISTS people")
    db.execute("CREATE TABLE IF NOT EXISTS people("
                    "first_name text,"
                    "last_name text,"
                    "bio text,"
                    "slug text,"
                    "UNIQUE(slug)"
                ")")

    # db.execute("DROP TABLE IF EXISTS lobbying_firms")
    db.execute("CREATE TABLE IF NOT EXISTS lobbying_firms("
                    "name text,"
                    "pdc_url text,"
                    "UNIQUE(name),"
                    "UNIQUE(pdc_url)"
                    ")")

    # db.execute("DROP TABLE IF EXISTS organizations")
    db.execute("CREATE TABLE IF NOT EXISTS organizations("
                    "name text,"
                    "canonical_entry integer,"
                    "slug text,"
                    "url text,"
                    "UNIQUE(slug),"
                    "UNIQUE(name),"
                    "FOREIGN KEY(canonical_entry) REFERENCES organizations(rowid)"
                ")")

    # db.execute("DROP TABLE IF EXISTS lobbyist_employment")
    db.execute("CREATE TABLE IF NOT EXISTS lobbyist_employment("
                    "person_rowid integer,"
                    "lobbying_firm_rowid integer,"
                    "organization_rowid integer,"
                    "year integer,"
                    "UNIQUE(person_rowid, lobbying_firm_rowid, organization_rowid, year),"
                    "FOREIGN KEY(person_rowid) REFERENCES people(rowid),"
                    "FOREIGN KEY(lobbying_firm_rowid) REFERENCES lobbying_firms(rowid),"
                    "FOREIGN KEY(organization_rowid) REFERENCES organizations(rowid)"
                ")")

    # db.execute(("DROP TABLE IF EXISTS bills"))
    # Bills live for a biennium.
    db.execute(("CREATE TABLE IF NOT EXISTS bills("
                    "biennium_rowid integer,"
                    "prefix text,"
                    "number integer,"
                    "previous_version int,"
                    "sponsor_rowid int,"
                    "companion_bill int,"
                    "FOREIGN KEY(previous_version) REFERENCES bills(rowid),"
                    "FOREIGN KEY(sponsor_rowid) REFERENCES people(rowid),"
                    "FOREIGN KEY(companion_bill) REFERENCES bills(rowid),"
                    "UNIQUE(biennium_rowid, number)"
                    ")"))
    db.execute(("CREATE TABLE IF NOT EXISTS revisions("
                    "bill_rowid integer,"
                    "version text,"
                    "description text,"
                    "source_url text,"
                    "modified_time timestamp,"
                    "base_revision integer,"
                    "next_revision integer,"
                    # Session versions are filled in once a bill is passed.
                    "session_rowid integer,"
                    "session_law_chapter integer,"
                    "FOREIGN KEY(base_revision) REFERENCES revisions(rowid),"
                    "FOREIGN KEY(next_revision) REFERENCES revisions(rowid),"
                    "UNIQUE(bill_rowid, session_law_chapter),"
                    "UNIQUE(bill_rowid, version))"))

    db.execute("CREATE TABLE IF NOT EXISTS agencies (name text, UNIQUE(name))")
    db.execute(("CREATE TABLE IF NOT EXISTS committees ("
                "id integer,"
                "session_rowid integer,"
                "name text,"
                "agency_rowid integer,"
                "acronym text,"
                "FOREIGN KEY(session_rowid) REFERENCES sessions(rowid),"
                "FOREIGN KEY(agency_rowid) REFERENCES agency(rowid),"
                "UNIQUE(session_rowid, id),"
                "UNIQUE(session_rowid, acronym)"
                ")"))
    # db.execute("DROP TABLE IF EXISTS meetings")
    db.execute(("CREATE TABLE IF NOT EXISTS meetings ("
                "mId integer,"
                "committee_rowid integer,"
                "start_time timestamp,"
                "notes text,"
                "FOREIGN KEY(committee_rowid) REFERENCES committees(rowid),"
                "UNIQUE(mId)"
                ")"))
    # db.execute("DROP TABLE IF EXISTS agenda_items")
    db.execute(("CREATE TABLE IF NOT EXISTS agenda_items ("
                "meeting_rowid integer,"
                "bill_rowid integer,"
                "caId integer,"
                "description text,"
                "FOREIGN KEY(bill_rowid) REFERENCES bills(rowid),"
                "FOREIGN KEY(meeting_rowid) REFERENCES meetings(rowid),"
                "UNIQUE(caId)"
                ")"))
    db.execute(("CREATE TABLE IF NOT EXISTS testimony_options ("
                "option text,"
                "UNIQUE(option)"
                ")"))
    db.execute(("CREATE TABLE IF NOT EXISTS testimony_links ("
                "agenda_item_rowid integer,"
                "option_rowid integer,"
                "url text,"
                "FOREIGN KEY(agenda_item_rowid) REFERENCES agenda_items(rowid),"
                "FOREIGN KEY(option_rowid) REFERENCES testimony_options(rowid),"
                "UNIQUE(agenda_item_rowid, option_rowid)"
                ")"))
    # db.execute("DROP TABLE IF EXISTS testifiers")
    # db.execute("DROP TABLE IF EXISTS positions")
    db.execute("CREATE TABLE IF NOT EXISTS positions (position text, UNIQUE(position))")
    db.execute(("CREATE TABLE IF NOT EXISTS testifiers ("
                    "agenda_item_rowid integer,"
                    "first_name text,"
                    "last_name text,"
                    "person_rowid integer,"
                    "organization text,"
                    "position_rowid integer,"
                    "testifying boolean,"
                    "sign_in_time timestamp,"
                    "FOREIGN KEY(agenda_item_rowid) REFERENCES agenda_items(rowid),"
                    "FOREIGN KEY(position_rowid) REFERENCES positions(rowid),"
                    "FOREIGN KEY(person_rowid) REFERENCES people(rowid),"
                    "UNIQUE(agenda_item_rowid, first_name, last_name, sign_in_time)"
    ")"))
    db.execute(("CREATE TABLE IF NOT EXISTS sections ("
                    "revision_rowid integer,"
                    "name text," # Usually a number but not always
                    "number integer," # Always a number
                    "chapter_rowid integer,"
                    "rcw_section text,"
                    "base_sl_revision integer,"
                    "previous_iteration integer,"
                    "raw_text text," # Usually a diff from the bill
                    "markdown text," # The new version of the text formatted in markdown
                    "effective date,"
                    "expires date,"
                    "FOREIGN KEY(revision_rowid) REFERENCES revisions(rowid),"
                    "FOREIGN KEY(chapter_rowid) REFERENCES chapters(rowid),"
                    "FOREIGN KEY(base_sl_revision) REFERENCES sections(rowid),"
                    "FOREIGN KEY(previous_iteration) REFERENCES sections(rowid),"
                    "UNIQUE(revision_rowid, number)"
                    ")"))
    db.execute("CREATE TABLE IF NOT EXISTS titles ("
                    "title_number text,"
                    "caption text,"
                    "UNIQUE(title_number)"
                    ")")
    db.execute("CREATE TABLE IF NOT EXISTS chapters ("
                    "title_rowid integer,"
                    "chapter_number text,"
                    "caption text,"
                    "FOREIGN KEY(title_rowid) REFERENCES titles(rowid),"
                    "UNIQUE(title_rowid, chapter_number)"
                    ")")
    return db
