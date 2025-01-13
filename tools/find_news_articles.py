from bs4 import BeautifulSoup
import arrow
import datetime
import url_history
import urllib.robotparser
import httpx
import httpcore
import pathlib
import pickle
import json
import re
import sys
import asyncio
from urllib.parse import urlparse, parse_qs

from rich.progress import *

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
    ],
    "tdn.com": [
    "/ads/",
    "/obituaries/",
    "/sports/",
    "/online/",
    "/life-entertainment"
    ]
}

# regular expression pattern to match a date in the format yyyy/mm/dd
DATE_PATTERN = r"(\d{4})[/-](\d{2})[/-](\d{2})"

after_date = arrow.get(2024, 12, 1)

def parse_date(content):
    if not content:
        return None
    try:
        return arrow.get(content).datetime
    except arrow.parser.ParserError:
        pass
    for other_format in ("H:mm A ZZZ MMMM D, YYYY","M/DD/YYYY H:mm:ss A", "M/D/YYYY H:mm:ss A"):
        try:
            return arrow.get(content, other_format).datetime
        except arrow.parser.ParserError:
            pass
    # print("other parse failed:", content)
    return None

FETCH_NEW = True
REPARSE = False

parsed_path = pathlib.Path("parsed_urls.pickle")
if parsed_path.exists():
    with parsed_path.open("rb") as f:
        parsed_urls = pickle.load(f)
else:
    parsed_urls = set()

link_count = 0
leg_links = 0
past_session = 0
nonspecific = 0

i = 0

async def scrape(progress, session, org_rowid, domain):
    global i, link_count, leg_links, past_session, nonspecific
    task = progress.add_task(f"{i} {domain}")
    if len(sys.argv) > 1 and domain not in sys.argv[1:]:
        progress.update(task, visible=False)
        return
    if "seattletimes" in domain:
        progress.update(task, visible=False)
        return
    i += 1
    url_base = "https://" + domain

    rp = urllib.robotparser.RobotFileParser()
    robots_url = url_base + "/robots.txt"
    rp.set_url(robots_url)
    robots = None
    try:
        robots = await session.get(robots_url, fetch_again=True)
    except (httpx.HTTPStatusError, httpx.ConnectError) as e:
        print(f"Unable to get {robots_url}", e)

    if robots:
        rp.parse(robots.decode("utf-8").splitlines())

    if robots is not None and rp.site_maps():
        sitemaps = set(rp.site_maps())
    else:
        sitemaps = set([url_base + "/sitemap.xml"])

    crawl_delay = None
    if robots:
        crawl_delay = rp.crawl_delay("*")
    if not crawl_delay:
        crawl_delay = 0
    crawl_delay = min(10, crawl_delay)

    if robots is not None and rp.request_rate("*"):
        raise NotImplementedError()

    running_total = len(sitemaps)
    pages = set()
    while sitemaps:
        sitemap = sitemaps.pop()
        progress.update(task, advance=1, total=running_total)
        try:
            sitemap = await session.get(sitemap, fetch_again=FETCH_NEW, crawl_delay=crawl_delay, only_after=after_date)
        except (asyncio.TimeoutError, httpx.HTTPStatusError, httpx.ConnectError) as e:
            print(f"Unable to get sitemap {sitemap} {e}")
            continue
        if sitemap is None:
            continue
        # print(sitemap)
        sitemap = BeautifulSoup(sitemap, 'xml')
        for subsitemap in sitemap.find_all("sitemap"):
            lastmod = subsitemap.lastmod
            if "southseattleemerald" in subsitemap.loc.text:
                # Don't use lastmod because old sitemaps still have it updated.
                lastmod = None
            if lastmod:
                lastmod = lastmod.text
                if lastmod.startswith("-0001"):
                    continue
                lastmod = arrow.get(lastmod)
                # Don't bother with old stuff yet.
                if lastmod < after_date:
                    continue
            elif "date=" in subsitemap.loc.text:
                # Fallback to a date in the sitemap url if available.
                parsed = urlparse(subsitemap.loc.text)
                query = parse_qs(parsed.query)
                if "date" in query and arrow.get(query["date"][0]) < after_date:
                    continue
            elif "yearmonth=" in subsitemap.loc.text:
                # Fallback to a date in the sitemap url if available.
                parsed = urlparse(subsitemap.loc.text)
                query = parse_qs(parsed.query)
                if "yearmonth" in query and arrow.get(query["yearmonth"][0] + "-01") < after_date:
                    continue
            else:
                match = re.search(DATE_PATTERN, subsitemap.loc.text)
                if match:
                    year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))
                    lastmod = datetime.datetime(year=year, month=month, day=day, tzinfo=arrow.now().tzinfo)
                    if lastmod < after_date:
                        continue
                    elif subsitemap.lastmod:
                        # Use the true lastmod if our date is within range.
                        lastmod = subsitemap.lastmod


            if domain == "www.spokesman.com":
                parsed = urlparse(subsitemap.loc.text)
                query = parse_qs(parsed.query)
                if "p" in query and int(query["p"][0]) > 10:
                    continue

            sitemaps.add(subsitemap.loc.text)
            running_total += 1

        for url in sitemap.find_all("url"):
            url_text = url.loc.text
            if url.find("video"):
                continue
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
            if "capitolhill" in url_loc and "/2024/" not in url_loc:
                continue
            if "gorgenewscenter.com" in url_loc and "/2024/" not in url_loc:
                continue
            if "kuow.org" in url_loc and url_loc.count("http") > 1:
                url_loc = url_loc[url_loc.index("http", 6):]
            # print(url.loc.text)
            pages.add(url_loc)
        # if len(pages) > 100:
        #     break

    # Find RSS feed
    homepage = None
    try:
        homepage = await session.get(url_base, fetch_again=FETCH_NEW, crawl_delay=crawl_delay)
    except (asyncio.TimeoutError, httpx.HTTPStatusError, httpx.ConnectError) as e:
        print(f"Unable to get homepage {url_base} {e}")
    except url_history.Blocked:
        print(f"Blocked by CloudFlare {url_base}")
        progress.update(task, visible=False)
        return

    try:
        homepage = BeautifulSoup(homepage, 'html.parser')
    except (AssertionError, TypeError):
        print(f"failed to parse: {url_base}")
    if homepage:
        rss_url = homepage.find("link", rel="alternate", type="application/rss+xml")
        if rss_url:
            print("rss", rss_url["href"])
            feed = None

            try:
                feed = await session.get(url_base + rss_url["href"], fetch_again=FETCH_NEW, crawl_delay=crawl_delay, only_after=after_date)
            except (asyncio.TimeoutError, httpx.HTTPStatusError, httpx.ConnectError) as e:
                print(f"Unable to get homepage {url_base} {e}")

            if feed:
                # Iterate over all items and add their urls to pages.
                feed = BeautifulSoup(feed, 'xml')
                for item in feed.find_all("item"):
                    link = item.find("link")
                    if link:
                        print(link.text)
                        pages.add(link.text)
        

    count = 0
    skipped = 0

    progress.update(task, total=len(pages) + running_total)
    for page_url in pages:
        progress.update(task, advance=1)
        if page_url in parsed_urls and not REPARSE:
            skipped += 1
            continue
        else:
            parsed_urls.add(page_url)

        if robots is not None and not rp.can_fetch("*", page_url):
            # print(f"Can't fetch {page_url}")
            continue
        try:
            page = await session.get(page_url, fetch_again=False, crawl_delay=crawl_delay)
            print(f"Fetch {page_url} delay {crawl_delay}")
        except (httpx.HTTPStatusError, httpx.ReadTimeout, httpx.ConnectError, httpcore.ReadTimeout, asyncio.TimeoutError) as e:
            print(f"{e} {page_url}")
            continue
        except url_history.Blocked:
            print(f"Blocked by CloudFlare {page_url}")
            progress.update(task, visible=False)
            return
        if page is None:
            print(f"missing page {page_url}")
            continue
        try:
            page = BeautifulSoup(page, 'html.parser')
        except (AssertionError, TypeError):
            print(f"failed to parse: {page_url}")
            continue
        canonical_url = page.find("link", rel="canonical")
        if canonical_url:
            parsed_canonical = urlparse(canonical_url.get("href"))
            if parsed_canonical.hostname and parsed_canonical.hostname != domain:
                continue

        meta_robots = page.find("meta", attrs={"name":"robots"})
        if meta_robots and "noindex" in meta_robots.text:
            # print(f"noindex {page_url}")
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
                    # print(f"json parse error: {e}")
                    # print(ld_json.text)
                    ln_json = {}
                # print(page_url)
                # print(ld_json)
                if "@graph" in ld_json:
                    graph = ld_json["@graph"][0]
                    for key in ("datePublished", "dateCreated"):
                        if key in graph:
                            try:
                                modified_time = parse_date(graph[key])
                                break
                            except arrow.parser.ParserError:
                                # print(f"invalid date on {page_url}")
                                # print(graph[key])
                                pass
                if not modified_time:
                    for key in ("datePublished", "dateCreated", "dateModified"):
                        if key in ld_json:
                            modified_time = parse_date(ld_json[key])
                            break

        if not modified_time:
            meta_modified_time = page.find("meta", attrs={"property":"article:modified_time"})
            if not meta_modified_time:
                meta_modified_time = page.find("meta", attrs={"itemprop":"dateModified"})
            if not meta_modified_time:
                meta_modified_time = page.find(attrs={"property":"dc:date"})
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
                try:
                    modified_time = datetime.datetime(year=year, month=month, day=day)
                except ValueError:
                    # print(f"Invalid modified time {page_url}")
                    modified_time = None

        # print(page)
        for link in page.find_all("a"):
            href = link.get("href")
            if not href:
                continue
            try:
                parsed = urlparse(href)
            except ValueError:
                # print(f"parse error {href}")
                continue
            if not parsed.hostname or "leg.wa.gov" not in parsed.hostname or "pages" in parsed.path:
                continue
            leg_links += 1
            link_text = " ".join(link.stripped_strings)
            query = parse_qs(parsed.query)

            if "Year" in query and "BillNumber" in query:
                # Crosscut includes briefs in multiple pages so ignore all but
                # the content.
                if "crosscut.com" in page_url:
                    is_content = False
                    for parent in link.parents:
                        if parent.get("id", None) == "block-crosscut-content":
                            is_content = True
                            break
                    if not is_content:
                        continue

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

                page_text = " ".join(page.stripped_strings)
                if page_text.count(link_text) == 1:
                    text_fragment = "#:~:text=" + link_text
                    cur.execute("INSERT INTO web_articles (organization_rowid, bill_rowid, date_posted, title, url, text_fragment) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (bill_rowid, url) DO UPDATE SET date_posted = excluded.date_posted", (org_rowid, bill_rowid, modified_time, page.title.string.strip(), page_url, text_fragment))
                    link_count += 1
                    continue

                nonspecific += 1
                # print("nonspecific", link_text)
                # print(page_url)
                # print(link)
                # print(link.parent)
            else:
                # print("skipped", query)
                # print(page_url)
                # print(link)
                # print()
                pass
            db.commit()
    
    progress.update(task, visible=False)

    with parsed_path.open("wb") as f:
        pickle.dump(parsed_urls, f)


org_cur = db.cursor()
org_cur.execute("SELECT rowid, url FROM organizations WHERE url IS NOT NULL")
org_cur = org_cur.fetchall()

# Add scrape calls to asyncio task group
async def main():
    session = url_history.HistorySession("org-website.db")
    with Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    MofNCompleteColumn()) as progress:
        async with asyncio.TaskGroup() as tg:
            for org_rowid, domain in org_cur:
                tg.create_task(scrape(progress, session, org_rowid, domain))
    await session.close()

asyncio.run(main())

print(f"bill links {link_count}")
print(f"leg links {leg_links}")
print(f"nonspecific {nonspecific}")
print(f"past session {past_session}")
