import requests_cache
from bs4 import BeautifulSoup, NavigableString
import re
import pathlib
import sys
import subprocess

PUSH = False

api_root_url = "http://wslwebservices.leg.wa.gov"

requests = requests_cache.CachedSession("bill_cache")

rcw_pattern = re.compile("RCW  ([0-9A-Z]+)\\.([0-9A-Z]+)\\.([0-9A-Z]+)")
chapter_pattern = re.compile("([0-9A-Z]+)\\.([0-9A-Z]+) RCW")

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

# Prep all of the file locations.
title_folders = {}
chapter_files = {}
for p in pathlib.Path(sys.argv[1]).iterdir():
    if p.is_dir():
        if p.name == ".git":
            continue
        title = p.name.split("_", maxsplit=1)[0].lstrip("0")
        title_folders[title] = p
        chapter_files[title] = {}
        for chapter_file in p.iterdir():
            if chapter_file.name == "README.adoc":
                continue
            chapter = chapter_file.name.split("_", maxsplit=1)[0].split(".")[1].lstrip("0")
            chapter_files[title][chapter] = chapter_file

section_pattern = re.compile("\\(([a-z]+|[0-9]+)\\)")

sections_through_pattern = re.compile("([0-9]+) through ([0-9]+)")
sections_pattern = re.compile("([0-9]+)")

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
                current_line = []
            last_end = result.end()
            group = result.group(1)
            if group.isnumeric():
                current_line.append(".")
            elif group[0] == "i" and last_group != "h":
                current_line.append("...")
            else:
                current_line.append("..")
            last_group = group
        current_line.append(line[last_end:])
        new_paragraph.append("".join(current_line))
        new_paragraph.append("")
    return new_paragraph

def amend_section(citation, section_citation, new_text):
    f = chapter_files[citation[0]][citation[1].lstrip("0")]
    new_chapter = []
    in_section = False
    section_header = "== " + ".".join(citation)
    for line in f.read_text().split("\n"):
        if line.startswith("=="):
            in_section = line.startswith(section_header)
            if in_section:
                new_chapter.append(line)
                new_chapter.extend(format_lists(new_text))
        if not in_section:
            new_chapter.append(line)
        elif line.startswith("[ "):
            new_chapter.append("[ " + section_citation + "; " + line[2:])

    f.write_text("\n".join(new_chapter))

def delete_section(citation, section_citation):
    f = chapter_files[citation[0]][citation[1].lstrip("0")]
    new_chapter = []
    in_section = False
    section_header = "== " + ".".join(citation)
    for line in f.read_text().split("\n"):
        if line.startswith("=="):
            in_section = line.startswith(section_header)
        if not in_section:
            new_chapter.append(line)

    f.write_text("\n".join(new_chapter))

def add_section(citation, section_citation, new_text):
    f = chapter_files[citation[0]][citation[1].lstrip("0")]
    new_chapter = []
    for line in f.read_text().split("\n"):
        new_chapter.append(line)
    new_chapter.append(f"== {citation[0]}.{citation[1]}.XXX - TBD")
    new_chapter.extend(format_lists(new_text))
    new_chapter.append("")
    new_chapter.append("[ " + section_citation + "; ]")
    new_chapter.append("")
    f.write_text("\n".join(new_chapter))

def new_chapter(citation, chapter_name, contents):
    print(chapter_name)
    f = title_folders[citation[0]] / (chapter_name.replace(" ", "_") + ".adoc")
    chapter = [
        f"= {citation[0]}.XXX - {chapter_name}",
        ":toc:",
        ""
    ]
    for section_citation, section_number, contents in contents:
        chapter.append(f"== {citation[0]}.XXX.{section_number} - TBD")
        chapter.extend(format_lists(contents))
        chapter.append("")
        chapter.append("[ " + section_citation + "; ]")
        chapter.append("")
    f.write_text("\n".join(chapter))
    run("git add " + str(f.relative_to(sys.argv[1])))

def run(command, stdin="", env={}):
    print(command)
    return subprocess.run(command, shell=True, env=env, check=True, cwd=pathlib.Path(sys.argv[1]), input=stdin, encoding="utf-8")

for start_year in range(2021, 2023, 2):
    biennium = f"{start_year:4d}-{(start_year+1) % 100:02d}"
    print(biennium)

    url = api_root_url + f"/SponsorService.asmx/GetRequesters?biennium={biennium}"
    requesters = requests.get(url)
    requesters = BeautifulSoup(requesters.text, "xml")
    count = 0
    for info in requesters.find_all("LegislativeEntity"):
        count += 1
    print(count, "requesters")

    sponsors_by_id = {}

    url = api_root_url + f"/SponsorService.asmx/GetSponsors?biennium={biennium}"
    sponsors = requests.get(url)
    sponsors = BeautifulSoup(sponsors.text, "xml")
    count = 0
    for info in sponsors.find_all("Member"):
        # if count == 0:
        #     print(info)
        sponsors_by_id[info.Id.text] = info
        count += 1
    print(count, "sponsors")


    url = api_root_url + f"/LegislativeDocumentService.asmx/GetAllDocumentsByClass?biennium={biennium}&documentClass=Bills"
    print(url)
    all_bill_docs = BeautifulSoup(requests.get(url, expire_after=24*60*60).text, "xml")
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
        count += 1
    print(count, "bill docs")

    url = api_root_url + f"/LegislationService.asmx/GetLegislationByYear?year={start_year}"
    legislation = requests.get(url)
    legislation = BeautifulSoup(legislation.text, "xml")
    count = 0
    bills_by_sponsor = {}
    for info in legislation.find_all("LegislationInfo"):
        bill_number = info.BillNumber.text
        bill_id = info.BillId.text

        # Skip resolutions
        if bill_id.startswith("HR") or bill_id.startswith("SR") or bill_id.startswith("HJR"):
            continue
        # Skip governor appointments
        if bill_id.startswith("SGA"):
            continue
        # Skip memorials
        if bill_id.startswith("SJM"):
            continue

        bills_url = api_root_url + f"/LegislationService.asmx/GetLegislation?biennium={biennium}&billNumber={bill_number}"
        bills = requests.get(bills_url)
        bills = BeautifulSoup(bills.text, "xml")
        full_info = None
        for bill in bills.find_all("Legislation"):
            if bill_id != bill.BillId.text:
                continue
            full_info = bill
        # if bill_number in ("1336", ):
        #     print(full_info)
        #     print()
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

        count += 1
    print(count, "legislation")
    print()

    url = api_root_url + f"/LegislationService.asmx/GetLegislationByYear?year={start_year+1}"
    legislation = requests.get(url)
    legislation = BeautifulSoup(legislation.text, "xml")
    count = 0
    for info in legislation.find_all("LegislationInfo"):
        bill_number = info.BillNumber.text
        # if count == 0:
        #     print(info)
        #     bill = api_root_url + f"/LegislationService.asmx/GetLegislation?biennium={biennium}&billNumber={bill_number}"
        #     bill = requests.get(bill)
        #     bill = BeautifulSoup(bill.text, "xml")
        #     print(bill)
        # print(amendment.Name.text, amendment.BillId.text)
        count += 1
    print(count, "legislation")

    amendments_by_bill_number = {}

    for year in (start_year, start_year + 1):
        url = api_root_url + f"/AmendmentService.asmx/GetAmendments?year={year}"
        amendments = requests.get(url)
        amendments = BeautifulSoup(amendments.text, "xml")
        count = 0
        for amendment in amendments.find_all("Amendment"):
            bill_number = amendment.BillNumber.text
            if bill_number not in amendments_by_bill_number:
                amendments_by_bill_number[bill_number] = []
            amendments_by_bill_number[bill_number].append(amendment)
            # print(amendment.Name.text, )
            count += 1
        print(count, "amendments")

    for sponsor in bills_by_sponsor:
        if sponsor != "16499" and sponsor != "27211":
            continue
        sponsor_info = sponsors_by_id[sponsor]
        print(sponsor_info)
        sponsor_name = sponsor_info.Name.text
        sponsor_email = sponsor_info.Email.text.lower().replace("@leg.wa.gov", "@wa-law.org")
        gitlab_user = sponsor_info.Email.text.lower().split("@")[0]
        commit_env = {
            "GIT_AUTHOR_NAME": sponsor_name,
            "GIT_COMMITTER_NAME": sponsor_name,
            "GIT_AUTHOR_EMAIL": sponsor_email,
            "GIT_COMMITTER_EMAIL": sponsor_email,
            "GIT_SSH_COMMAND": f"ssh -i ~/repos/wa-law-tools/.ssh/{gitlab_user} -o IdentitiesOnly=yes"
        }
        for bill_number in bills_by_sponsor[sponsor]:
            # Ignore follow up legislation info for now.
            bill = bills_by_sponsor[sponsor][bill_number][0]
            bill_id = bill.BillId.text
            print(bill_id, bill.ShortDescription.text)
            print(bill.LongDescription.text)
            print(bill.HistoryLine.text)
            run("git checkout 2020H2")
            bill_branch = "2021." + bill_id.replace(" ", ".")
            run("git switch -C " + bill_branch)
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
                    url = doc.PdfUrl.text
                    url = url.replace("Pdf", "Xml").replace("pdf", "xml")
                    commit_date = doc.PdfLastModifiedDate.text
                    commit_env["GIT_AUTHOR_DATE"] = commit_date
                    commit_env["GIT_COMMITTER_DATE"] = commit_date
                    commit_message = []
                    print(doc.Name.text, commit_date, url)
                    if doc.ShortFriendlyName.text == "Original Bill":
                        commit_message.append(bill_id + " " + bill.ShortDescription.text)
                        commit_message.append("")
                        commit_message.append(bill.LongDescription.text)
                    else:
                        commit_message.append(doc.ShortFriendlyName.text)
                        commit_message.append("")
                        commit_message.append(doc.LongFriendlyName.text)
                    commit_message.append("")
                    commit_message.append("Sourced from: " + url.replace(" ", "%20"))
                    print(doc.ShortFriendlyName.text)
                    print(doc.LongFriendlyName.text)
                    print()
                    run("git checkout 2020H2 .")
                    text = requests.get(url).content
                    bill_text = BeautifulSoup(text, 'xml')
                    sections = {}
                    new_chapters = {}
                    sections_handled = 0
                    section_count = 0
                    for section in bill_text.find_all("BillSection"):
                        section_number = section.BillSectionNumber
                        if not section_number:
                            continue
                        section_count += 1
                        section_number = section_number.Value.text
                        section_citation = f"2021 c XXX § {section_number}"
                        print("Bill section", section_number, section.attrs)
                        if "action" not in section.attrs:
                            if section["type"] == "new":
                                lines = []
                                for paragraph in section.find_all("P"):
                                    lines.append(paragraph.text)
                                sections[section_number] = lines
                                sections_handled += 1
                            else:
                                print(section)
                        elif section["action"] == "repeal":
                            delete_section(get_citation(section), section_citation)
                            sections_handled += 1
                        elif section["action"] == "amend":
                            # print("##", section.Caption.text)
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
                                                print(paragraph, child)
                                                raise RuntimeError()
                                        if "amendingStyle" not in child.attrs:
                                            # print("no amend style", child.name, child)
                                            pass
                                        elif child["amendingStyle"] in AMEND_INCLUDE:
                                            line.append(child.text.strip())
                                if line:
                                    section_lines.append("".join(line))
                            amend_section(get_citation(section), section_citation, section_lines)
                            sections_handled += 1
                        elif section["action"] == "addsect":
                            section_lines = []
                            for paragraph in section.find_all("P"):
                                section_lines.append(paragraph.text)
                            add_section(get_citation(section), section_citation, section_lines)
                            sections_handled += 1
                        elif section["action"] == "addchap":
                            c = get_citation(section)
                            new_chapters[c] = set()
                            print("add chapter to", )
                            text = section.P.text.split("of this act")[0]
                            for m in sections_pattern.finditer(text):
                                new_chapters[c].add(m[0])
                            for m in sections_through_pattern.finditer(text):
                                new_chapters[c].update((str(x) for x in range(int(m[1]), int(m[2]))))
                            print(text)
                            print(new_chapters[c])
                        elif section["action"] == "addmultisect":
                            # print("add chapter to", get_citation(section))
                            # print(section.P.text)
                            pass
                        elif section["action"] == "effdate":
                            # When sections of the bill go into effect. (PR merge date.)
                            # print("add chapter to", get_citation(section))
                            # print(section.P.text)
                            pass
                        elif section["action"] == "emerg":
                            # Emergency bill that would take immediate effect.
                            # print("add chapter to", get_citation(section))
                            # print(section.P.text)
                            pass
                        elif section["action"] == "repealuncod":
                            # Repeal a section of a session law that is uncodified.
                            pass
                        elif section["action"] == "amenduncod":
                            # Amend a section of a session law that is uncodified.
                            pass
                        elif section["action"] == "addsectuncod":
                            # Add a section of a session law that is uncodified.
                            pass
                        elif section["action"] == "remd":
                            # Reenact and amend a section. Looks like two bills from the same session
                            # changed the same location and the code revisor had to merge them.
                            pass
                        elif section["action"] == "expdate":
                            # Section expiration date.
                            pass
                        elif section["action"] == "recod":
                            # Recode sections.
                            pass
                        elif section["action"] == "decod":
                            # Section expiration date.
                            pass
                        else:
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
                                contents.append((section_citation, section, sections.pop(section)))
                                if contents[-1][2][0].startswith("This chapter shall be known and cited as the "):
                                    chapter_name = contents[-1][2][0].split("the ", maxsplit=1)[1].strip(".")
                            if not chapter_name:
                                raise RuntimeError()
                            new_chapter(c, chapter_name, contents)
                            print()
                            print()
                    if sections:
                        commit_message.append("")
                        for section_number in sections:
                            print(section_number, sections[section_number])
                            commit_message.append("Section " + section_number + ". " + "\n".join(sections[section_number]))

                    run(f"git commit -a --no-signoff --no-gpg-sign --file=-", stdin="\n".join(commit_message), env=commit_env)
                # Push the branch
                if PUSH:
                    run(f"git push -f {gitlab_user} {bill_branch}", env=commit_env)
            print()


        print("------------------------")
        print()
