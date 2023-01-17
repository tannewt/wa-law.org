from bs4 import BeautifulSoup, NavigableString
import datetime
import re
import pathlib
import sqlite3
import sys
import subprocess
import url_history
import utils

FORCE_FETCH = False

api_root_url = "http://wslwebservices.leg.wa.gov"

requests = url_history.HistorySession("bill_cache.db")

db = utils.get_db()

rcw_pattern = re.compile("RCW  ([0-9A-Z]+)\\.([0-9A-Z]+)\\.([0-9A-Z]+)")
chapter_pattern = re.compile("([0-9A-Z]+)\\.([0-9A-Z]+) RCW")

short_committee_status_to_acronym = {
    "H": {
        "Approps": "APP",
        "Cap Budget": "CB",
        "Children, Yout": "CYF",
        "Children, Youth": "CYF",
        "Civil R & Judi": "CRJ",
        "Coll & Wkf Dev": "CWD",
        "Comm & Econ De": "CED",
        "Comm & Econ Dev": "CED",
        "Commerce & Gam": "COG",
        "Commerce & Gami": "COG",
        "ConsPro&Bus": "CPB",
        "Education": "ED",
        "Env & Energy": "ENVI",
        "Finance": "FIN",
        "HC/Wellness": "HCW",
        "Hous, Human Sv": "HHSV",
        "Hous, Human Svc": "HHSV",
        "Labor & Workpl": "LAWS",
        "Labor & Workpla": "LAWS",
        "Local Govt": "LG",
        "Public Safety": "PS",
        "RDev, Ag&NR": "RDAN",
        "State Govt & T": "SGOV",
        "State Govt & Tr": "SGOV",
        "Transportation": "TR"
    },
    "S": {
        "Ag/Water/Natur": "AWNP",
        "Ag/Water/Natura": "AWNP",
        "Behavioral Hea": "BH",
        "Behavioral Heal": "BH",
        "Business, Fina": "BFST",
        "Business, Finan": "BFST",
        "EL/K-12": "EDU",
        "Environment, E": "ENET",
        "Environment, En": "ENET",
        "Health & Long": "HLTC",
        "Health & Long T": "HLTC",
        "Higher Ed & Wo": "HEWD",
        "Housing & Loca": "HLG",
        "Housing & Local": "HLG",
        "Human Svcs, Re": "HSRR",
        "Human Svcs, Ree": "HSRR",
        "Labor, Comm &": "LCTA",
        "Labor, Comm & T": "LCTA",
        "Law & Justice": "LAW",
        "State Govt & E": "SGE",
        "State Govt & El": "SGE",
        "Transportation": "TRAN",
        "Ways & Means": "WM",
    }
}

def get_citation(xml):
    t = xml.TitleNumber
    if t:
        t = t.text
    c = xml.ChapterNumber
    if c:
        c = c.text
    s = xml.SectionNumber
    if s:
        s = s.text
    return (t, c, s)

AMEND_INCLUDE = ("add", )
AMEND_EXCLUDE = ("strike", "strikemarkright", "strikemarknone")

section_pattern = re.compile("\\(([a-z]+|[0-9]+)\\)")

sections_through_pattern = re.compile("([0-9]+) through ([0-9]+)")
sections_pattern = re.compile("([0-9]+)")

# Keep track of what paths have already been amended. This makes sure we copy
# the original back in place for the original amendment. Without it, we'll add
# multiple copies of amendments over time.
amended = set()

def format_lists(paragraph):
    new_paragraph = []
    for line in paragraph:
        line = line.strip()
        current_line = []
        last_end = 0
        for result in section_pattern.finditer(line):
            if result.start() != last_end:
                break
            if last_end > 0:
                current_line.append(" [Empty]")
                new_paragraph.append("".join(current_line))
                new_paragraph.append("")
                current_line = []
            last_end = result.end()
            group = result.group(1)
            if group.isnumeric():
                current_line.append(group + ".")
            elif group[0] == "i" and last_group != "h":
                current_line.append("    " * 2 + group + ".")
            else:
                current_line.append("    " * 1 + group + ".")
            last_group = group
        current_line.append(line[last_end:])
        new_paragraph.append("".join(current_line))
        new_paragraph.append("")
    return new_paragraph

def new_chapter(revision_path, citation, chapter_name, contents):
    print("new chapter", citation, chapter_name)
    # f = title_folders[citation[0]] / (chapter_name.replace(" ", "_") + ".md")
    # chapter = [
    #     f"= {citation[0]}.XXX - {chapter_name}",
    #     ":toc:",
    #     ""
    # ]
    # for section_citation, section_number, contents in contents:
    #     chapter.append(f"== {citation[0]}.XXX.{section_number} - TBD")
    #     chapter.extend(format_lists(contents))
    #     chapter.append("")
    #     chapter.append("[ " + section_citation + "; ]")
    #     chapter.append("")
    # new = revision_path / f
    # new.parent.mkdir(parents=True, exist_ok=True)
    # new.write_text("\n".join(chapter))

bills_path = pathlib.Path("bill/")
all_bills_readme = ["# All Bills by Biennium"]

for start_year in range(2023, 2025, 2):
    biennium = f"{start_year:4d}-{(start_year+1) % 100:02d}"
    print(biennium)

    cur = db.cursor()
    cur.execute("INSERT OR IGNORE INTO bienniums (start_year, end_year, name) VALUES (?, ?, ?)", (start_year, start_year+1, biennium))
    cur.execute("SELECT rowid FROM bienniums WHERE name = ?;", (biennium,))
    biennium_rowid = cur.fetchone()[0]

    cur.execute("INSERT OR IGNORE INTO sessions (biennium_rowid, year, name) VALUES (?, ?, ?)", (biennium_rowid, start_year, str(start_year)))
    cur.execute("SELECT rowid FROM sessions WHERE name = ?;", (str(start_year),))
    session_rowid = cur.fetchone()[0]

    bills_by_status = {"committee": {}, "passed": []}

    url = api_root_url + f"/SponsorService.asmx/GetRequesters?biennium={biennium}"
    requesters = requests.get(url)
    requesters = BeautifulSoup(requesters.decode("utf-8"), "xml")
    count = 0
    for info in requesters.find_all("LegislativeEntity"):
        count += 1
    print(count, "requesters")

    sponsors_by_id = {}

    url = api_root_url + f"/SponsorService.asmx/GetSponsors?biennium={biennium}"
    sponsors = requests.get(url)
    sponsors = BeautifulSoup(sponsors.decode("utf-8"), "xml")
    count = 0
    for info in sponsors.find_all("Member"):
        if count == 0:
            print(info)
        sponsors_by_id[info.Id.text] = info
        count += 1
    print(count, "sponsors")

    url = api_root_url + f"/CommitteeService.asmx/GetCommittees?biennium={biennium}"
    print(url)
    committees = requests.get(url)
    committees = BeautifulSoup(committees.decode("utf-8"), "xml")
    last_agency = None
    committees_by_agency = {}
    # TODO: Table of contents
    for committee in committees.find_all("Committee"):
        agency = committee.Agency.text
        name = committee.Name.text
        acronym = committee.Acronym.text
        print(agency, name, acronym)
        if last_agency != agency:
            # biennium_readme.append(f"[{agency}](#{agency.lower()})")
            committees_by_agency[agency] = []
        last_agency = agency
        committees_by_agency[agency].append((acronym, name))
        slug = name.lower().replace(" ", "-")
        # biennium_readme.append(f"* [{name}](#{slug})")

    url = api_root_url + f"/LegislativeDocumentService.asmx/GetAllDocumentsByClass?biennium={biennium}&documentClass=Bills"
    print(url)
    all_bill_docs = BeautifulSoup(requests.get(url, fetch_again=FORCE_FETCH).decode("utf-8"), "xml")
    docs_by_number = {}
    count = 0
    for doc in all_bill_docs.find_all("LegislativeDocument"):
        bill_number = doc.BillId.text
        if not bill_number:
            continue
        bill_number = bill_number.split()[-1]
        if bill_number not in docs_by_number:
            docs_by_number[bill_number] = []
        docs_by_number[bill_number].append(doc)
        # print(bill_number)
        count += 1
    print(count, "bill docs")

    url = api_root_url + f"/LegislationService.asmx/GetLegislationByYear?year={start_year}"
    legislationOdd = requests.get(url, fetch_again=FORCE_FETCH)
    legislationOdd = BeautifulSoup(legislationOdd.decode("utf-8"), "xml")
    url = api_root_url + f"/LegislationService.asmx/GetLegislationByYear?year={start_year+1}"
    legislationEven = requests.get(url, fetch_again=FORCE_FETCH)
    legislationEven = BeautifulSoup(legislationEven.decode("utf-8"), "xml")
    url = api_root_url + f"/LegislationService.asmx/GetPreFiledLegislationInfo?"
    legislationPrefiled = requests.get(url, fetch_again=FORCE_FETCH)
    legislationPrefiled = BeautifulSoup(legislationPrefiled.decode("utf-8"), "xml")
    count = 0
    bills_by_sponsor = {}
    bills_by_number = {}
    sponsor_by_bill_number = {}
    for info in legislationOdd.find_all("LegislationInfo") + legislationEven.find_all("LegislationInfo") + legislationPrefiled.find_all("LegislationInfo"):
        bill_number = info.BillNumber.text
        bill_id = info.BillId.text

        # Skip bills that may have been from the previous year.
        if bill_number in bills_by_number:
            continue

        # Skip resolutions
        if bill_id.startswith("HR") or bill_id.startswith("ESR") or bill_id.startswith("SR") or bill_id.startswith("HJR") or bill_id.startswith("SJR") or bill_id.startswith("HCR") or bill_id.startswith("SCR"):
            continue
        # Skip governor appointments
        if bill_id.startswith("SGA"):
            continue
        # Skip memorials
        if bill_id.startswith("SJM"):
            continue

        bills_url = api_root_url + f"/LegislationService.asmx/GetLegislation?biennium={biennium}&billNumber={bill_number}"
        # if bill_number == "1007":
        print(bills_url)
        bills = requests.get(bills_url, fetch_again=FORCE_FETCH)
        bills = BeautifulSoup(bills.decode("utf-8"), "xml")
        full_info = None
        for bill in bills.find_all("Legislation"):
            full_info = bill
            sponsor_id = full_info.PrimeSponsorID.text
            if bill_number not in docs_by_number:
                print(bill_number, "missing doc")
            if sponsor_id not in sponsors_by_id:
                print(sponsor_id, "missing sponsor for bill", bill_id)
            if sponsor_id not in bills_by_sponsor:
                bills_by_sponsor[sponsor_id] = {}
            if bill_number not in bills_by_sponsor[sponsor_id]:
                bills_by_sponsor[sponsor_id][bill_number] = []
            bills_by_sponsor[sponsor_id][bill_number].append(full_info)
            if bill_number not in bills_by_number:
                bills_by_number[bill_number] = []
            bills_by_number[bill_number].append(full_info)
        sponsor_by_bill_number[bill_number] = sponsor_id

        count += 1
        if count % 100 == 0:
            print("loaded", count)
    print(count, "legislation")
    print()

    amendments_by_bill_number = {}

    for year in (start_year, start_year + 1):
        url = api_root_url + f"/AmendmentService.asmx/GetAmendments?year={year}"
        amendments = requests.get(url)
        amendments = BeautifulSoup(amendments.decode("utf-8"), "xml")
        count = 0
        for amendment in amendments.find_all("Amendment"):
            bill_number = amendment.BillNumber.text
            if bill_number not in amendments_by_bill_number:
                amendments_by_bill_number[bill_number] = []
            amendments_by_bill_number[bill_number].append(amendment)
            # print(amendment.Name.text, )
            count += 1
        print(count, "amendments")

    # for sponsor in bills_by_sponsor:
    #     sponsor_info = sponsors_by_id[sponsor]
    #     if sponsor_info.LastName.text != "Ryu":
    #         continue
    #     print(sponsor_info)
    # sys.exit()
    #     sponsor_name = sponsor_info.Name.text
    #     sponsor_email = sponsor_info.Email.text.lower().replace("@leg.wa.gov", "@wa-law.org")
    #     gitlab_user = sponsor_info.Email.text.lower().split("@")[0]
    #     for bill_number in bills_by_sponsor[sponsor]:
    bill_link_by_number = {}
    for i, bill_number in enumerate(bills_by_number):
            # if bill_number != "1000":
            #     continue
            sponsor = sponsor_by_bill_number[bill_number]
            status = ""
            bill = None
            bill_id = None
            for b in bills_by_sponsor[sponsor][bill_number]:
                # Find the shortest billId because we don't want engrossed or substitutes.
                if bill_id is None or len(b.BillId.text) < len(bill_id):
                    bill_id = b.BillId.text
                if b.Active.text != "true":
                    continue
                # print(b.CurrentStatus.Status.text, b.CurrentStatus.HistoryLine.text)
                status = b.CurrentStatus.Status.text
                bill = b

            if bill is None:
                raise RuntimeError("no active bill", bill_number)

            short_description = ""
            if bill.ShortDescription is not None:
                short_description = bill.ShortDescription.text
            elif bill.LongDescription is not None:
                short_description = bill.LongDescription.text
            else:
                print("missing description")
                print(bill)
            if status.startswith("C "):
                bills_by_status["passed"].append(bill_link)
            elif " " in status and not status.startswith("Gov") and not status.startswith("Del"):
                agency, short_committee = status.split(" ", maxsplit=1)
                acronym = None
                if short_committee in short_committee_status_to_acronym[agency]:
                    acronym = short_committee_status_to_acronym[agency][short_committee]
                # Do pass and do pass substitute
                elif short_committee.endswith("DPS"):
                    acronym = short_committee[:-3]
                elif short_committee.endswith("DP"):
                    acronym = short_committee[:-2]
            else:
                if status not in bills_by_status:
                    bills_by_status[status] = []
                bills_by_status[status].append(bill_link)

            print(bill_id, sponsor, short_description)
            # print(bill.CurrentStatus.IntroducedDate.text, bill.CurrentStatus.ActionDate.text)
            # print(bill.CurrentStatus.Status.text)
            if bill_number in amendments_by_bill_number:
                for amendment in amendments_by_bill_number[bill_number]:
                    # print(amendment.Name.text, amendment.SponsorName.text, amendment.Description.text, amendment.FloorAction.text)
                    # print(amendment)
                    # print()
                    url = amendment.PdfUrl.text
                    url = url.replace("Pdf", "Xml").replace("pdf", "xml")
                    # print(url)
                    # response = requests.get(url)
                    # if not response.ok:
                    #     print("missing xml version")
                    #     print(amendment)
                    # amendment_text = BeautifulSoup(response.content, 'xml')
                    # for section in amendment_text.find_all("AmendSection"):
                    #     # print(section.AmendItem.P.text)
                    #     new_sections = section.find_all("BillSection")
                    #     if not new_sections:
                    #         print(section)
                    #     print()
                    #print(amendment)
                    # print()
                    # print()
                # print(amendment)
            else:
                print("no amendments")
            if bill_number in docs_by_number:
                for doc in docs_by_number[bill_number]:
                    pdf_url = doc.PdfUrl.text
                    url = pdf_url.replace("Pdf", "Xml").replace("pdf", "xml")
                    commit_date = doc.PdfLastModifiedDate.text.split(".", maxsplit=1)[0]
                    commit_date = datetime.datetime.strptime(commit_date, "%Y-%m-%dT%H:%M:%S")
                    revision = "1"
                    if "-" in doc.Name.text:
                        revision = doc.Name.text.split("-")[1]
                    print(doc.Name.text, revision, commit_date, url)
                    
                    cur = db.cursor()
                    prefix = bill_id.split()[0]
                    cur.execute("INSERT OR IGNORE INTO bills (biennium_rowid, prefix, number) VALUES (?, ?, ?)", (biennium_rowid, prefix, bill_number))
                    cur.execute("SELECT rowid FROM bills WHERE biennium_rowid = ? AND number = ?", (biennium_rowid, bill_number))
                    bill_rowid = cur.fetchone()[0]

                    try:
                        cur.execute("INSERT INTO revisions(bill_rowid, version, description, source_url, modified_time) VALUES (?, ?, ?, ?, ?)", (bill_rowid, revision, short_description, pdf_url, commit_date))
                    except sqlite3.IntegrityError:
                        # Already imported
                        continue
                    cur.execute("SELECT rowid from revisions WHERE bill_rowid = ? AND version = ?", (bill_rowid, revision))
                    revision_rowid = cur.fetchone()[0]
                    db.commit()

                    print(url)
                    text = requests.get(url, fetch_again=FORCE_FETCH).decode("utf-8")
                    revision_text = BeautifulSoup(text, 'xml')
                    sections = {}
                    new_chapters = {}
                    sections_handled = 0
                    section_count = 0
                    for section in revision_text.find_all("BillSection"):
                        section_number = section.BillSectionNumber
                        if not section_number:
                            continue
                        section_count += 1
                        section_number = section_number.Value.text
                        section_citation = f"2021 c XXX § {section_number}"

                        rcw_citation = get_citation(section)
                        if rcw_citation and rcw_citation[0]:
                            print(rcw_citation)
                            cur.execute("INSERT OR IGNORE INTO titles (title_number) VALUES (?)", (rcw_citation[0],))
                            cur.execute("SELECT rowid FROM titles WHERE title_number = ?;", (rcw_citation[0],))
                            title_rowid = cur.fetchone()[0]
                            if rcw_citation[1]:
                                cur.execute("INSERT OR IGNORE INTO chapters (title_rowid, chapter_number) VALUES (?, ?)", (title_rowid, rcw_citation[1]))
                                cur.execute("SELECT rowid FROM chapters WHERE title_rowid = ? AND chapter_number = ?;", (title_rowid, rcw_citation[1]))
                                chapter_rowid = cur.fetchone()[0]
                            else:
                                chapter_rowid = None
                        else:
                            title_rowid = None
                            chapter_rowid = None
                        print("Bill section", section_number, section.attrs)
                        if "action" not in section.attrs:
                            if section["type"] == "new":
                                lines = []
                                for paragraph in section.find_all("P"):
                                    lines.append(paragraph.text)
                                sections[section_number] = lines
                                section_text = "\n".join(format_lists(lines))
                                cur.execute("INSERT INTO sections(revision_rowid, name, number, chapter_rowid, previous_iteration, markdown) VALUES (?, ?, ?, ?, ?, ?)", (revision_rowid, section_number, section_count, None, None, section_text))
                                db.commit()
                                sections_handled += 1
                            else:
                                pass
                                print(section)
                        elif section["action"] == "repeal":
                            cur.execute("INSERT INTO sections(revision_rowid, name, number, chapter_rowid, rcw_section, base_sl_revision) VALUES (?, ?, ?, ?, ?, ?)", (revision_rowid, section_number, section_count, chapter_rowid, rcw_citation[2], None))
                            db.commit()
                            sections_handled += 1
                        elif section["action"] == "amend":
                            # print("##", section.Caption.text)
                            rcw_citation = get_citation(section)
                            if section.History is None:
                                base_bill_rowid = None
                                base_section_rowid = None
                            else:
                                history = section.History.text
                                base_section = history.split()
                                base_session = " ".join(base_section[:base_section.index("c")])
                                base_chapter = int(base_section[base_section.index("c") + 1])
                                base_section = base_section[base_section.index("§") + 1].strip(";.")
                                cur.execute("SELECT rowid FROM sessions WHERE name = ?", (base_session,))
                                base_session_rowid = cur.fetchone()[0]
                                # TODO: Create revisions and sections for RCW
                                # print(rcw_citation, base_session_rowid, base_chapter)
                                # cur.execute("SELECT rowid FROM revisions WHERE session_rowid = ? AND session_law_chapter = ?;", (base_session_rowid, base_chapter))
                                # base_revision_rowid = cur.fetchone()[0]
                                # cur.execute("SELECT rowid FROM sections WHERE revision_rowid = ? AND name = ?", (base_revision_rowid, base_section))
                                # base_section_rowid = cur.lastrowid
                                base_section_rowid = None
                            section_lines = []

                            for paragraph in section.find_all("P"):
                                line = []
                                for child in paragraph.children:
                                    if isinstance(child, NavigableString):
                                        s = str(child)
                                        # Only non-whitespace strings. Don't always strip though
                                        # because we want the spaces on the edge of text.
                                        if s.strip():
                                            line.append(s)
                                    else:
                                        if child.name != "TextRun":
                                            if child.name == "SectionCite":
                                                line.append(child.text)
                                            elif child.name == "Hyphen" and child["type"] == "nobreak":
                                                line.append("‑")
                                            elif child.name not in ("Leader",):
                                                # print(paragraph, child)
                                                raise RuntimeError()
                                        if "amendingStyle" not in child.attrs:
                                            # print("no amend style", child.name, child)
                                            pass
                                        elif child["amendingStyle"] in AMEND_INCLUDE:
                                            stripped = child.text.strip()
                                            if not stripped:
                                                continue
                                            # Ignore changed bullets
                                            if stripped[0] == "(" and stripped[-1] == ")":
                                                line.append(child.text)
                                            else:
                                                line.append(stripped)
                                if line:
                                    section_lines.append("".join(line))
                            section_text = "\n".join(format_lists(section_lines))

                            cur.execute("INSERT INTO sections(revision_rowid, name, number, chapter_rowid, rcw_section, base_sl_revision, markdown) VALUES (?, ?, ?, ?, ?, ?, ?)", (revision_rowid, section_number, section_count, chapter_rowid, rcw_citation[2], base_section_rowid, section_text))
                            db.commit()
                            sections_handled += 1
                        elif section["action"] == "addsect":
                            section_lines = []
                            for paragraph in section.find_all("P"):
                                section_lines.append(paragraph.text)
                            section_text = "\n".join(format_lists(section_lines))
                            rcw_citation = get_citation(section)
                            if rcw_citation[0] is None:
                                print(section, section.attrs)
                                continue

                            cur.execute("INSERT INTO sections(revision_rowid, name, number, chapter_rowid, markdown) VALUES (?, ?, ?, ?, ?)", (revision_rowid, section_number, section_count, chapter_rowid, section_text))
                            db.commit()
                            sections_handled += 1
                        elif section["action"] == "addchap":
                            c = get_citation(section)
                            new_chapters[c] = set()
                            print("add chapter to", )
                            if section.P is None:
                                print(section)
                                continue
                            text = section.P.text.split("of this act")[0]
                            for m in sections_pattern.finditer(text):
                                new_chapters[c].add(m[0])
                            for m in sections_through_pattern.finditer(text):
                                new_chapters[c].update((str(x) for x in range(int(m[1]), int(m[2]))))
                            # print(text)
                            # print(new_chapters[c])
                        # elif section["action"] == "addmultisect":
                        #     # print("add chapter to", get_citation(section))
                        #     # print(section.P.text)
                        #     pass
                        # elif section["action"] == "effdate":
                        #     # When sections of the bill go into effect. (PR merge date.)
                        #     # print("add chapter to", get_citation(section))
                        #     # print(section.P.text)
                        #     pass
                        elif section["action"] == "emerg":
                            # Emergency bill that would take immediate effect.
                            text = section.P.text
                            print("emerg")
                            d = " ".join(text.rsplit(maxsplit=3)[1:]).strip(".")
                            try:
                                d = datetime.datetime.strptime(d, "%B %d, %Y")
                            except ValueError:
                                d = None
                            if d:
                                if text.startswith("This act"):
                                    cur.execute("UPDATE sections SET effective = ? WHERE revision_rowid = ?", (d, revision_rowid))
                                    sections_handled += 1
                                else:
                                    print(text)
                            cur.execute("INSERT INTO sections(revision_rowid, name, number, raw_text) VALUES (?, ?, ?, ?)", (revision_rowid, section_number, section_count, text))
                            db.commit()
                        # elif section["action"] == "repealuncod":
                        #     # Repeal a section of a session law that is uncodified.
                        #     pass
                        # elif section["action"] == "amenduncod":
                        #     # Amend a section of a session law that is uncodified.
                        #     pass
                        # elif section["action"] == "addsectuncod":
                        #     # Add a section of a session law that is uncodified.
                        #     pass
                        # elif section["action"] == "remd":
                        #     # Reenact and amend a section. Looks like two bills from the same session
                        #     # changed the same location and the code revisor had to merge them.
                        #     pass
                        # elif section["action"] == "expdate":
                        #     # Section expiration date.
                        #     pass
                        # elif section["action"] == "recod":
                        #     # Recode sections.
                        #     pass
                        # elif section["action"] == "decod":
                        #     # Section expiration date.
                        #     pass
                        else:
                            if section.P:
                                text = section.P.text
                                cur.execute("INSERT INTO sections(revision_rowid, name, number, raw_text) VALUES (?, ?, ?, ?)", (revision_rowid, section_number, section_count, text))
                                db.commit()
                            print(section, section.attrs)
                    print(f"{sections_handled}/{section_count}")
                    if new_chapters:
                        for c in new_chapters:
                            contents = []
                            chapter_name = ""
                            chapter_sections = sorted(new_chapters[c], key=int)
                            print(chapter_sections)
                            for section in chapter_sections:
                                section_citation = f"2021 c XXX § {section}"
                                if section not in sections or not sections[section]:
                                    print("missing section", section)
                                    continue
                                contents.append((section_citation, section, sections.pop(section)))
                                if contents[-1][2][0].startswith("This chapter shall be known and cited as the "):
                                    chapter_name = contents[-1][2][0].split("the ", maxsplit=1)[1].strip(".")
                            if not chapter_name:
                                print("Missing chapter name")
                                continue
                            new_chapter(revision_path, c, chapter_name, contents)
                            print()
                            print()
                    if sections:
                        for section_number in sections:
                            # print(section_number, sections[section_number])
                            pass

            print()


        # print("------------------------")
        # print()

    print()
    break
