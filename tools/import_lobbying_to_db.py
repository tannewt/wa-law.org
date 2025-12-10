import asyncio
import csv
import pathlib

import url_history
import utils

db = utils.get_db()

FORCE_FETCH = True


async def main():
    session = url_history.HistorySession("lobbying_cache.db")

    lobbyists = await session.get(
        "https://data.wa.gov/api/v3/views/bp5b-jrti/export.csv?accessType=DOWNLOAD&app_token=NWOYpe94rjpZSIJNQPqTHf1Fm",
        fetch_again=FORCE_FETCH,
    )

    csvfile = lobbyists.decode("utf-8").split("\n")

    for row in csv.DictReader(csvfile):
        merged_employers = []
        for employer in row["employers"].split(","):
            if employer[0] == " ":
                merged_employers[-1] += "," + employer
            else:
                merged_employers.append(employer)
        if " " not in row["agent_name"]:
            continue
        first_name, last_name = row["agent_name"].strip().split(maxsplit=1)
        if not last_name.startswith("von"):
            last_name = last_name.capitalize()
        first_name = first_name.capitalize()
        if first_name == "Ziply":
            first_name = "Jessica"
            last_name = "Epley"

        cur = db.cursor()

        cur.execute(
            "SELECT rowid FROM people WHERE first_name = ? AND last_name = ?",
            (first_name, last_name),
        )
        person = cur.fetchone()
        if not person:
            cur.execute(
                "INSERT INTO people VALUES (?, ?, ?, ?)",
                (first_name, last_name, row["agent_bio"], first_name + "." + last_name),
            )
            person = cur.lastrowid
        else:
            person = person[0]

        employer_rowids = []
        for employer_name in merged_employers:
            employer_name = utils.canonicalize_org(employer_name)

            cur.execute(
                "SELECT rowid FROM organizations WHERE name = ?", (employer_name,)
            )
            employer_rowid = cur.fetchone()
            if not employer_rowid:
                slug = employer_name.lower().replace(" ", "_")
                cur.execute(
                    "INSERT INTO organizations(name, slug) VALUES (?, ?)",
                    (employer_name, slug),
                )
                employer_rowid = cur.lastrowid
            else:
                employer_rowid = employer_rowid[0]
            employer_rowids.append(employer_rowid)

        firm_name = row["lobbyist_firm_name"]
        firm_url = row["filer_id"]
        print(firm_name, firm_url)
        cur.execute("SELECT rowid FROM lobbying_firms WHERE name = ?", (firm_name,))
        firm_rowid = cur.fetchone()
        if not firm_rowid:
            cur.execute(
                "SELECT rowid FROM lobbying_firms WHERE pdc_url = ?", (firm_url,)
            )
            firm_rowid = cur.fetchone()
            if not firm_rowid:
                cur.execute(
                    "INSERT INTO lobbying_firms(name, pdc_url) VALUES (?, ?)",
                    (firm_name, firm_url),
                )
                firm_rowid = cur.lastrowid
            else:
                firm_rowid = firm_rowid[0]
        else:
            firm_rowid = firm_rowid[0]

        year = int(row["employment_year"])
        for employer_rowid in employer_rowids:
            cur.execute(
                "INSERT OR IGNORE INTO lobbyist_employment VALUES (?, ?, ?, ?)",
                (person, firm_rowid, employer_rowid, year),
            )

        db.commit()

    alternative_path = pathlib.Path("data/organization_names.csv")
    alternative_org_names = csv.reader(alternative_path.open())
    # drop the header row
    next(alternative_org_names)
    for alternative, canonical in alternative_org_names:
        print(alternative, canonical)
        slug = canonical.lower().replace(" ", "_")
        cur.execute(
            "INSERT OR IGNORE INTO organizations (name, slug) VALUES (?, ?)",
            (canonical, slug),
        )
        cur.execute("SELECT rowid FROM organizations WHERE name = ?", (canonical,))
        canonical_rowid = cur.fetchone()
        if not canonical_rowid:
            print("missing", canonical)
            continue
        canonical_rowid = canonical_rowid[0]

        alternative_slug = alternative.lower().replace(" ", "_")
        cur.execute(
            "INSERT INTO organizations(name, slug, canonical_entry) VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET canonical_entry = excluded.canonical_entry",
            (alternative, alternative_slug, canonical_rowid),
        )

    db.commit()

    org_urls_path = pathlib.Path("data/organization_urls.csv")
    org_urls = csv.reader(org_urls_path.open())
    # drop the header row
    next(org_urls)
    for canonical, homepage in org_urls:
        print(canonical, homepage)
        slug = canonical.lower().replace(" ", "_")
        cur.execute(
            "INSERT OR IGNORE INTO organizations (name, slug, url) VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET url = excluded.url",
            (canonical, slug, homepage),
        )

    await session.close()
    db.commit()


asyncio.run(main())
