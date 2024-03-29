from bs4 import BeautifulSoup
import arrow
import datetime
import url_history
import requests
import urllib3
import pathlib
import pickle
import json
import re
import sys
from urllib.parse import urlparse, parse_qs

import utils

db = utils.get_db()

session = url_history.HistorySession("wsr.db")

FETCH_NEW = False
REPARSE = True

parsed_path = pathlib.Path("parsed_wsr_urls.pickle")
if not REPARSE and parsed_path.exists():
    with parsed_path.open("rb") as f:
        parsed_urls = pickle.load(f)
else:
    parsed_urls = set()

pending_urls = set()
ROOT = "https://lawfilesext.leg.wa.gov/law/wsr/WsrByIssue.htm"
pending_urls.add(ROOT)

bill_re = re.compile("[SH]B ([0-9]{4})")
year_re = re.compile("[SH]B ([0-9]{4}),? \(?(section \d+(\(\d+\))?, )?chapter (\d+), Laws of ([0-9]{4})\)?")
leg_re = re.compile("(\d{4}) (legis|\w* ?session)")
wsr_re = re.compile("WSR \d+-\d+-\d+")
count = 0
skipped = 0
while pending_urls:
    page_url = pending_urls.pop()
    count += 1
    if count % 100 == 0:
        print(f"fetched {count} remaining {len(pending_urls)}")
        with parsed_path.open("wb") as f:
            pickle.dump(parsed_urls, f)

    if (page_url in parsed_urls and (not pending_urls and page_url != ROOT)) or (pending_urls and "/2023/" not in page_url):
        skipped += 1
        continue
    else:
        parsed_urls.add(page_url)

    print(page_url)

    try:
        page = session.get(page_url, fetch_again=False)
    except (requests.exceptions.ConnectionError, requests.exceptions.SSLError, requests.exceptions.TooManyRedirects, requests.exceptions.MissingSchema, requests.exceptions.ConnectTimeout, urllib3.exceptions.LocationParseError) as e:
        print(e, page_url)
        continue
    if page is None:
        print("missing page", page_url)
        continue
    try:
        page = BeautifulSoup(page, 'html.parser')
    except (AssertionError, TypeError):
        print("failed to parse", page_url)
        continue

    for comment in page.find_all(string=re.compile("WSRRegType")):
        print("reg type:", comment.next.text)

    # print(page)
    wac_citations = set()
    rcw_citations = set()
    wsr_citations = set()

    for string in page.find_all(string=wsr_re):
        print(string.parent)
        for match in wsr_re.finditer(str(string)):
            print(match)

    for bill in page.find_all(string=bill_re):
        print(bill.parent)
        # print(type(bill), repr(bill))
        # print(str(bill))
        match = year_re.search(str(bill))
        if not match:
            match = bill_re.search(str(bill))
            if match:
                year_match = leg_re.search(str(bill))
                if year_match:
                    print("year", year_match.groups())
        print(match, match.groups())
        print()

    for link in page.find_all("a"):
        href = link.get("href")
        if not href:
            continue
        try:
            parsed = urlparse(href)
        except ValueError:
            print("parse error", href)
            continue
        if not parsed.hostname:
            continue

        if "lawfilesext.leg.wa.gov" in parsed.hostname:
            if href in parsed_urls:
                continue
            if parsed.path.endswith("pdf"):
                continue
            print(link, parsed.path)
            pending_urls.add(href)

        elif "leg.wa.gov" in parsed.hostname:
            link_text = " ".join(link.stripped_strings)
            query = parse_qs(parsed.query)

            if parsed.path == "/WAC/default.aspx":
                print(query)
                wac_citations += 1
                rcw_citations.add(query["cite"][0])
                continue
            elif parsed.path == "/RCW/default.aspx":
                rcw_citations.add(query["cite"][0])
                continue

            print(parsed)

            if "Year" in query and "BillNumber" in query:
                cur = db.cursor()
                try:
                    year = int(query["Year"][0])
                except ValueError:
                    continue
                if year % 2 == 0:
                    start_year = year - 1
                else:
                    start_year = year
                biennium = f"{start_year:4d}-{(start_year+1) % 100:02d}"
                cur.execute("SELECT rowid FROM bienniums WHERE name = ?;", (biennium,))
                biennium_row = cur.fetchone()
                if not biennium_row:
                    continue
                biennium_rowid = biennium_row[0]
                bill_number = query["BillNumber"][0]
                cur.execute("SELECT rowid FROM bills WHERE number = ? AND biennium_rowid = ?", (int(bill_number), biennium_rowid))
                bill_row = cur.fetchone()
                if not bill_row:
                    past_session += 1
                    continue
                bill_rowid = bill_row[0]

                if bill_number in link_text:
                    text_fragment = "#:~:text=" + link_text
                    cur.execute("INSERT INTO web_articles (organization_rowid, bill_rowid, date_posted, title, url, text_fragment) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (bill_rowid, url) DO UPDATE SET date_posted = excluded.date_posted", (org_rowid, bill_rowid, modified_time, page.title.string.strip(), page_url, text_fragment))
                    link_count += 1
                    continue
                nonspecific += 1
                print(page_url)
                print(link)
                print(link.parent)
                print()
            else:
                # print(page_url)
                # print(link)
                # print()
                pass
    print(rcw_citations)
    print(wac_citations)
    print(f"citations: {len(rcw_citations)} rcw {len(wac_citations)} wac")
    print()
    db.commit()
    # break
