from bs4 import BeautifulSoup
import arrow
import url_history
import urllib.robotparser
import requests
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

after_date = arrow.get(2022, 12, 1)

FETCH_NEW = False

link_count = 0
leg_links = 0
past_session = 0
nonspecific = 0

org_cur = db.cursor()
org_cur.execute("SELECT rowid, url FROM organizations WHERE url IS NOT NULL")
org_cur = org_cur.fetchall()
i = 0
for org_rowid, domain in org_cur:
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
            # print(url.loc.text)
            pages.add(url.loc.text)
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
        except (requests.exceptions.TooManyRedirects, requests.exceptions.MissingSchema, requests.exceptions.ConnectTimeout) as e:
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

        meta_modified_time = page.find("meta", attrs={"property":"article:modified_time"})
        modified_time = None
        if meta_modified_time:
            modified_time = arrow.get(meta_modified_time["content"]).datetime
        # print(page)
        for link in page.find_all("a"):
            href = link.get("href")
            if not href:
                continue
            parsed = urlparse(href)
            if not parsed.hostname or "leg.wa.gov" not in parsed.hostname or "pages" in parsed.path:
                continue
            leg_links += 1
            link_text = " ".join(link.stripped_strings)
            query = parse_qs(parsed.query)

            if "Year" in query and "BillNumber" in query:
                cur = db.cursor()
                year = int(query["Year"][0])
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
                    cur.execute("INSERT OR IGNORE INTO web_articles (organization_rowid, bill_rowid, date_posted, title, url, text_fragment) VALUES (?, ?, ?, ?, ?, ?)", (org_rowid, bill_rowid, modified_time, page.title.string.strip(), page_url, text_fragment))
                    link_count += 1
                    continue
                nonspecific += 1
                print(page_url)
                print(link)
                print(link.parent)
                print()
            else:
                print(page_url)
                print(link)
                print()
        db.commit()
print("bill links", link_count)
print("leg links", leg_links)
print("nonspecific", nonspecific)
print("past session", past_session)
