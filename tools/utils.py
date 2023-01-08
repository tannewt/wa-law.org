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

def get_db(readonly=False):
    db = sqlite3.connect("wa-laws.db")
    if readonly:
        return db

    db.execute(("CREATE TABLE IF NOT EXISTS sessions("
                    "year integer,"
                    "name text)"))
    db.execute(("CREATE TABLE IF NOT EXISTS bills("
                    "year integer,"
                    "session_rowid integer,"
                    "prefix text,"
                    "id integer,"
                    "version text,"
                    "previous_version int,"
                    "next_version int,"
                    "description text,"
                    "session_law_chapter integer,"
                    "FOREIGN KEY(previous_version) REFERENCES bills(rowid),"
                    "FOREIGN KEY(next_version) REFERENCES bills(rowid),"
                    "UNIQUE(session_rowid, session_law_chapter),"
                    "UNIQUE(year, id, version))"))
    # db.execute(("CREATE TABLE meetings ("
    #                 ""))
    # db.execute(("CREATE TABLE agenda_items ("
    #             "meeting_rowid integer,"
    #             "caId integer,"
    #             "FOREIGN KEY(next_version) REFERENCES bills(rowid)"
    #             ")"))
    db.execute("DROP TABLE IF EXISTS testifiers")
    db.execute("DROP TABLE IF EXISTS positions")
    db.execute("CREATE TABLE IF NOT EXISTS positions (position text, UNIQUE(position))")
    db.execute(("CREATE TABLE IF NOT EXISTS testifiers ("
                    "bill_rowid integer,"
                    "agenda_item_rowid integer,"
                    "first_name text,"
                    "last_name text,"
                    "organization text,"
                    "position_rowid integer,"
                    "testifying boolean,"
                    "sign_in_time timestamp,"
                    "FOREIGN KEY(bill_rowid) REFERENCES bills(rowid),"
                    "FOREIGN KEY(position_rowid) REFERENCES positions(rowid)"
    ")"))
    db.execute(("CREATE TABLE IF NOT EXISTS sections ("
                    "bill_rowid integer,"
                    "bill_section text,"
                    "chapter_rowid integer,"
                    "rcw_section text,"
                    "base_sl_revision integer,"
                    "previous_iteration integer,"
                    "markdown text,"
                    "effective date,"
                    "expires date,"
                    "FOREIGN KEY(bill_rowid) REFERENCES bills(rowid),"
                    "FOREIGN KEY(chapter_rowid) REFERENCES chapters(rowid),"
                    "FOREIGN KEY(base_sl_revision) REFERENCES sections(rowid),"
                    "FOREIGN KEY(previous_iteration) REFERENCES sections(rowid))"))
    db.execute("CREATE TABLE IF NOT EXISTS titles ("
                    "title_number text,"
                    "caption text)")
    db.execute("CREATE TABLE IF NOT EXISTS chapters ("
                    "title_rowid integer,"
                    "chapter_number text,"
                    "caption text,"
                    "FOREIGN KEY(title_rowid) REFERENCES titles(rowid)"
                    ")")
    return db
