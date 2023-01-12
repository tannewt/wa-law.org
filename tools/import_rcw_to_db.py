import string
import pathlib
import url_history
import re
import sys
import parse
import utils
from bs4 import BeautifulSoup
from mdit_py_plugins.anchors.index import slugify

FORCE_FETCH = False
rcw_root_url = "https://apps.leg.wa.gov/rcw/"

requests = url_history.HistorySession("rcw_cache.db")

root = requests.get(rcw_root_url, fetch_again=FORCE_FETCH)

db = utils.get_db()

soup = BeautifulSoup(root.decode("utf-8"), 'html.parser')

sections = soup.find(id="ContentPlaceHolder1_dgSections")
titles = {}
for row in sections.find_all("tr"):
    data = row.find_all("td")
    link = data[0].find("a")
    directory_name = link.text[len("Title "):]
    title_name = data[1].text.strip()
    titles[directory_name] = {"link": link["href"], "title": title_name, "chapters": {}}

all_citations = set()

section_pattern = re.compile("\\(([a-z]+|[0-9]+|[A-Z]+)\\)")

count = 0
for title in titles:
    info = titles[title]
    print("title", title, info["title"])
    cur = db.cursor()
    cur.execute("INSERT INTO titles VALUES (?, ?)", (title, info["title"]))
    title_rowid = cur.lastrowid
    db.commit()
    title_page = requests.get(rcw_root_url + info["link"], fetch_again=FORCE_FETCH).decode("utf-8")
    soup = BeautifulSoup(title_page, 'html.parser')
    table = soup.find("table")
    for row in table.find_all("tr"):
        link = row.find("a")
        section_info = {}
        data = row.find_all("td")
        chapter_number = link.text.strip().split(".")[1]
        chapter_title = data[1].text.strip()
        cur.execute("INSERT INTO chapters VALUES (?, ?, ?)", (title_rowid, chapter_number, chapter_title))
        chapter_rowid = cur.lastrowid
        db.commit()
        info["chapters"][link.text.strip()] = {"link": link["href"] + "&full=true",
                                               "title": data[1].text.strip(),
                                               "sections": section_info}

        chapter_page = requests.get(link["href"] + "&full=true", fetch_again=FORCE_FETCH).decode("utf-8")
        chapter = BeautifulSoup(chapter_page, 'html.parser')
        sections = chapter.find(id="ContentPlaceHolder1_dlSectionContent")
        if not sections:
            continue
        for section in sections.find_all("span"):
            divs = section.find_all("div", recursive=False)
            if not divs:
                continue
            try:
                number_link = divs[0].find_all("a")[1]
            except IndexError:
                number_link = None
            # TODO: Chapter 11.130 has articles to partition sections.
            if not number_link:
                continue
            number = number_link.text
            name = divs[1].h3.text
            full_div = 2
            if "CHANGE IN" in divs[full_div].text:
                full_div = 3
            full_text = [d.text.replace("  ", " ") for d in divs[full_div].find_all("div")]
            citations = []
            section_info[number] = {"title": name, "body": full_text, "citations": citations}
            print(number, name)
            # if number == "35A.80.010":
            #     print(section)
            #     print("full", full_text)
            if len(divs) == full_div + 1:
                continue
            full_citations = divs[full_div+1].text
            full_citations = full_citations.replace("(i)", ";").replace("(ii)", ";")
            full_citations = full_citations.replace("(1)", ";").replace("(2)", ";")
            full_citations = full_citations.replace(". Prior:", ";").replace("prior:", ";")
            raw_citations = full_citations.strip("[] .").split(";")
            if not raw_citations:
                continue
            if ". Formerly RCW" in raw_citations[-1]:
                raw_citations[-1] = raw_citations[-1].split(". Formerly RCW")[0]
            history = [x.strip() for x in raw_citations]
            links = {}
            for link in divs[full_div+1].find_all("a"):
                links[link.text] = link["href"]
            chapter_citations = []
            latest_session = None
            for citation in history:
                # print(citation)
                if "repealed by" in citation:
                    cs = citation.strip("()").split(" repealed by ")
                elif "expired" in citation:
                    cs = citation.strip("()").split(" expired ")[:1]
                else:
                    cs = [citation]
                for c in cs:
                    pieces = c.rsplit(maxsplit=4)
                    citations.append((c, links.get(c, None)))
                    c = c.strip("()")
                    if len(pieces) == 5 and pieces[1] == "c" and pieces[3] == "§":
                        try:
                            year = int(pieces[0].split(maxsplit=1)[0][:4])
                            cur.execute("INSERT OR IGNORE INTO sessions (year, name) VALUES (?, ?)", (year, pieces[0]))
                            cur.execute("SELECT rowid FROM sessions WHERE name = ?;", (pieces[0],))
                            session_rowid = cur.fetchone()[0]
                            if latest_session is None:
                                latest_session = session_rowid
                        except ValueError:
                            pass
                    else:
                        print(c)
                    chapter_citation = c.split("§")[0].strip()
                    all_citations.add(chapter_citation)

            # print()
    # print(titles)
    # if count > 2:
    #     break
    count += 1

ordered = sorted(all_citations)
print("total citations", len(ordered))
# print(ordered[:2000])
