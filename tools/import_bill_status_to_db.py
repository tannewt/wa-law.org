from bs4 import BeautifulSoup, NavigableString
import datetime
import re
import pathlib
import sqlite3
import sys
import subprocess
import url_history
import utils

FORCE_FETCH = True

api_root_url = "http://wslwebservices.leg.wa.gov"

requests = url_history.HistorySession("bill_cache.db")

db = utils.get_db()

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

    statuses = requests.get(api_root_url + "/LegislationService.asmx/GetLegislativeStatusChangesByDateRange?biennium=2023-24&beginDate=2023-01-01&endDate=2025-01-01", fetch_again=FORCE_FETCH)
    print(statuses)
