import csv
import pathlib
import url_history
import utils

db = utils.get_db()

requests = url_history.HistorySession("lobbying_cache.db")

FORCE_FETCH = False

lobbyists = requests.get("https://www.pdc.wa.gov/political-disclosure-reporting-data/browse-search-data/download?dsid=e7sd-jbuy&fname=lobbyists-agents-table&query=select%20agent_name%20as%20agent_name%2Cemployment_year%20as%20employment_year%2Clobbyist_firm_name%20as%20lobbyist_firm_name%2Cemployer_title%20as%20employer_title%2Clobbyist_phone%20as%20lobbyist_phone%2Clobbyist_email%20as%20lobbyist_email%2Clobbyist_address%20as%20lobbyist_address%2Ctraining_certified%20as%20training_certified%2Cagent_bio%2Cagent_pic_url%2Clobbyist_firm_url%20where%201%20%3D%201%20order%20by%20agent_name%20asc%2Cemployment_year%20desc%2C%3Aid%20limit%2010000000", fetch_again=FORCE_FETCH)

csvfile = lobbyists.decode("utf-8").split("\n")

agents = set()
employers = set()

for row in csv.DictReader(csvfile):
    first_name, last_name = row["agent_name"].strip().split(maxsplit=1)
    if not last_name.startswith("von"):
        last_name = last_name.capitalize()
    first_name = first_name.capitalize()
    if first_name == "Ziply":
        first_name = "Jessica"
        last_name = "Epley"

    cur = db.cursor()
    
    cur.execute("SELECT rowid FROM people WHERE first_name = ? AND last_name = ?", (first_name, last_name))
    person = cur.fetchone()
    if not person:
        cur.execute("INSERT INTO people VALUES (?, ?, ?, ?)", (first_name, last_name, row["agent_bio"], first_name + "." + last_name))
        person = cur.lastrowid
    else:
        person = person[0]
    employer_name = utils.canonicalize_org(row["employer_title"])

    cur.execute("SELECT rowid FROM organizations WHERE name = ?", (employer_name,))
    employer_rowid = cur.fetchone()
    if not employer_rowid:
        slug = employer_name.lower().replace(" ", "_")
        cur.execute("INSERT INTO organizations(name, slug) VALUES (?, ?)", (employer_name, slug))
        employer_rowid = cur.lastrowid
    else:
        employer_rowid = employer_rowid[0]

    firm_name = row["lobbyist_firm_name"]
    cur.execute("SELECT rowid FROM lobbying_firms WHERE name = ?", (firm_name,))
    firm_rowid = cur.fetchone()
    if not firm_rowid:
        cur.execute("INSERT INTO lobbying_firms(name, pdc_url) VALUES (?, ?)", (firm_name, row["lobbyist_firm_url"]))
        firm_rowid = cur.lastrowid
    else:
        firm_rowid = firm_rowid[0]

    year = int(row["employment_year"])
    cur.execute("INSERT OR IGNORE INTO lobbyist_employment VALUES (?, ?, ?, ?)", (person, firm_rowid, employer_rowid, year))

    db.commit()

alternative_path = pathlib.Path("data/organization_names.csv")
alternative_org_names = csv.reader(alternative_path.open())
# drop the header row
next(alternative_org_names)
for alternative, canonical in alternative_org_names:
    print(alternative, canonical)
    slug = canonical.lower().replace(" ", "_")
    cur.execute("INSERT OR IGNORE INTO organizations (name, slug) VALUES (?, ?)", (canonical, slug))
    cur.execute("SELECT rowid FROM organizations WHERE name = ?", (canonical,))
    canonical_rowid = cur.fetchone()
    if not canonical_rowid:
        print("missing", canonical)
        continue
    canonical_rowid = canonical_rowid[0]

    alternative_slug = alternative.lower().replace(" ", "_")
    cur.execute("INSERT INTO organizations(name, slug, canonical_entry) VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET canonical_entry = excluded.canonical_entry", (alternative, alternative_slug, canonical_rowid))

db.commit()
