from bs4 import BeautifulSoup
import arrow
import datetime
import url_history
import urllib.robotparser
import requests
import urllib3
import json
import re
import sys
from urllib.parse import urlparse, parse_qs

import utils

db = utils.get_db()

EXCLUDE = {
    "www.seattletimes.com": [
                "/sports/",
                "/nation-world/",
                "/news/",
                "/entertainment/",
                "/sponsored/",
                "/explore/",
                "/business/",
                "/life/"
    ],
    "southseattleemerald.com": [
        "/tag/",
        "/category/"
    ],
    "publicola.com": [
        "/tag/",
        "/category/"
    ],
    "www.washingtonbus.org": [
        "/tag/",
        "/category/"
    ],
    "mynorthwest.com": [
        "/tag/"
    ]
}

session = url_history.HistorySession("org-website.db")

# regular expression pattern to match a date in the format yyyy/mm/dd
DATE_PATTERN = r"(\d{4})/(\d{2})/(\d{2})"

after_date = arrow.get(2022, 12, 1)

def parse_date(content):
    if not content:
        return None
    try:
        return arrow.get(content).datetime
    except arrow.parser.ParserError:
        pass
    for other_format in ("H:mm A ZZZ MMMM D, YYYY",):
        try:
            return arrow.get(content, other_format).datetime
        except arrow.parser.ParserError:
            pass
    print("other parse failed:", content)
    return None

FETCH_NEW = True

link_count = 0
leg_links = 0
past_session = 0
nonspecific = 0

org_cur = db.cursor()
org_cur.execute("SELECT rowid, url FROM organizations WHERE url IS NOT NULL")
org_cur = org_cur.fetchall()
i = 0
for org_rowid, domain in org_cur:
    if len(sys.argv) > 1 and domain not in sys.argv[1:]:
        print("skipping", domain)
        continue
    print(i, len(org_cur), domain)
    i += 1
    url_base = "https://" + domain

    rp = urllib.robotparser.RobotFileParser()
    robots_url = url_base + "/robots.txt"
    rp.set_url(robots_url)
    print("Fetching", robots_url)
    robots = session.get(robots_url, fetch_again=True)
    rp.parse(robots.decode("utf-8").splitlines())

    if rp.site_maps():
        sitemaps = set(rp.site_maps())
    else:
        sitemaps = set([url_base + "/sitemap.xml"])

    crawl_delay = rp.crawl_delay("*")
    if not crawl_delay:
        crawl_delay = 0
    crawl_delay = min(10, crawl_delay)

    if rp.request_rate("*"):
        raise NotImplementedError()

    pages = set()
    print("Getting sitemaps")
    while sitemaps:
        sitemap = sitemaps.pop()
        print(sitemap)
        sitemap = session.get(sitemap, fetch_again=FETCH_NEW, crawl_delay=crawl_delay, only_after=after_date)
        if sitemap is None:
            continue
        # print(sitemap)
        sitemap = BeautifulSoup(sitemap, 'xml')
        for subsitemap in sitemap.find_all("sitemap"):
            lastmod = subsitemap.lastmod
            if lastmod:
                lastmod = lastmod.text
                if lastmod.startswith("-0001"):
                    continue
                lastmod = arrow.get(lastmod)
                # Don't bother with old stuff yet.
                if lastmod < after_date:
                    continue
            if domain == "www.spokesman.com":
                parsed = urlparse(subsitemap.loc.text)
                query = parse_qs(parsed.query)
                if "p" in query and int(query["p"][0]) > 10:
                    continue

            sitemaps.add(subsitemap.loc.text)

        for url in sitemap.find_all("url"):
            url_text = url.loc.text
            if domain in EXCLUDE:
                include = True
                for exclude in EXCLUDE[domain]:
                    if exclude in url_text:
                        include = False
                        break
                if not include:
                    continue
            if url.lastmod is not None:
                lastmod = url.lastmod.text
                if lastmod.startswith("-0001"):
                    continue
                lastmod = arrow.get(url.lastmod.text)
                # Don't bother with old stuff yet.
                if lastmod < after_date:
                    continue
            url_loc = url.loc.text
            if "capitolhill" in url_loc and "/2023/" not in url_loc:
                continue
            if "gorgenewscenter.com" in url_loc and "/2023/" not in url_loc:
                continue
            if "kuow.org" in url_loc and url_loc.count("http") > 1:
                url_loc = url_loc[url_loc.index("http", 6):]
            # print(url.loc.text)
            pages.add(url_loc)
        # if len(pages) > 100:
        #     break
    print()

    print(f"Fetching {len(pages)} pages")
    count = 0
    while pages:
        page_url = pages.pop()
        count += 1
        if count % 100 == 0:
            print(f"fetched {count} remaining {len(pages)}")
        if not rp.can_fetch("*", page_url):
            print("Can't fetch", page_url)
            continue
        try:
            page = session.get(page_url, fetch_again=False)
        except (requests.exceptions.ConnectionError, requests.exceptions.SSLError, requests.exceptions.TooManyRedirects, requests.exceptions.MissingSchema, requests.exceptions.ConnectTimeout, urllib3.exceptions.LocationParseError) as e:
            print(e, page_url)
            continue
        if page is None:
            print("missing page", page_url)
            continue
        try:
            if "southseattleemerald" in page_url:
                print(page_url)
            page = BeautifulSoup(page, 'html.parser')
        except (AssertionError, TypeError):
            print("failed to parse", page_url)
            continue
        canonical_url = page.find("link", rel="canonical")
        if canonical_url:
            parsed_canonical = urlparse(canonical_url.get("href"))
            if parsed_canonical.hostname and parsed_canonical.hostname != domain:
                continue

        meta_robots = page.find("meta", attrs={"name":"robots"})
        if meta_robots and "noindex" in meta_robots.text:
            print("noindex", page_url)
            continue

        meta_published_time = page.find("meta", attrs={"property":"article:published_time"})
        modified_time = None
        if not meta_published_time:
            meta_published_time = page.find("meta", attrs={"property":"og:article:published_time"})
        if not meta_published_time:
            meta_published_time = page.find("meta", attrs={"itemprop":"datePublished"})
        if meta_published_time:
            content = meta_published_time["content"]
            modified_time = parse_date(content)

        if not modified_time:
            ld_json = page.find("script", attrs={"type":"application/ld+json"})
            if ld_json:
                try:
                    ld_json = json.loads(ld_json.text)
                except json.decoder.JSONDecodeError as e:
                    print("json parse error:", e)
                    print(ld_json.text)
                    ln_json = {}
                # print(page_url)
                # print(ld_json)
                if "@graph" in ld_json:
                    graph = ld_json["@graph"][0]
                    for key in ("datePublished", "dateCreated"):
                        if key in graph:
                            modified_time = arrow.get(graph[key]).datetime
                            break

        if not modified_time:
            meta_modified_time = page.find("meta", attrs={"property":"article:modified_time"})
            if not meta_modified_time:
                meta_modified_time = page.find("meta", attrs={"itemprop":"dateModified"})
            if meta_modified_time:
                modified_time = parse_date(meta_modified_time["content"])

        if not modified_time:
            timeago_time = page.find("abbr", attrs={"class":"timeago"})
            if timeago_time:
                modified_time = arrow.get(timeago_time["title"]).datetime

        # search for the date in the URL
        if not modified_time:
            match = re.search(DATE_PATTERN, page_url)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                modified_time = datetime.datetime(year=year, month=month, day=day)

        if page_url == "https://www.king5.com/article/news/local/whatcom-county-rail-safety-push/281-ddb560d4-5a36-4eae-860c-6a1c10f6ef7e":
            print(page_url, modified_time)

        # print(page)
        for link in page.find_all("a"):
            href = link.get("href")
            if not href:
                continue
            try:
                parsed = urlparse(href)
            except ValueError:
                print("parse error", href)
                continue
            if not parsed.hostname or "leg.wa.gov" not in parsed.hostname or "pages" in parsed.path:
                continue
            leg_links += 1
            link_text = " ".join(link.stripped_strings)
            query = parse_qs(parsed.query)

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
        db.commit()
print("bill links", link_count)
print("leg links", leg_links)
print("nonspecific", nonspecific)
print("past session", past_session)
