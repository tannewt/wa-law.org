import asyncio
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

async def main():
    session = url_history.HistorySession("org-website.db")
    for start_year in range(2023, 2027, 2):
        biennium = f"{start_year:4d}-{(start_year+1) % 100:02d}"
        print(biennium)

        cur = db.cursor()
        cur.execute("SELECT rowid FROM bienniums WHERE name = ?;", (biennium,))
        biennium_rowid = cur.fetchone()[0]

        cur.execute("INSERT OR IGNORE INTO sessions (biennium_rowid, year, name) VALUES (?, ?, ?)", (biennium_rowid, start_year, str(start_year)))
        cur.execute("SELECT rowid FROM sessions WHERE name = ?;", (str(start_year),))
        session_rowid = cur.fetchone()[0]

        url = api_root_url + f"/LegislationService.asmx/GetLegislativeStatusChangesByDateRange?biennium={biennium}&beginDate={start_year}-01-01&endDate={start_year + 2}-01-01"
        print(url)
        statuses = await session.get(url, fetch_again=FORCE_FETCH)

        statuses = BeautifulSoup(statuses, 'xml')
        for status_element in statuses.find_all("LegislativeStatus"):
            print(status_element)
            bill_id = status_element.BillId.text
            bill_number = bill_id.split()[-1]
            cur.execute("SELECT rowid FROM bills WHERE biennium_rowid = ? AND number = ?", (biennium_rowid, bill_number))
            bill_rowid = cur.fetchone()
            if not bill_rowid:
                print("Skipping", bill_number)
                continue
            bill_rowid = bill_rowid[0]

            status = status_element.Status.text.strip()
            history_line = status_element.HistoryLine
            # print("status:", status)
            action_date = datetime.datetime.strptime(status_element.ActionDate.text, "%Y-%m-%dT%H:%M:%S")
            print(status, history_line, action_date)
            cur.execute("INSERT OR IGNORE INTO bill_statuses (biennium_rowid, status) VALUES (?, ?)", (biennium_rowid, status))
            cur.execute("SELECT rowid FROM bill_statuses WHERE biennium_rowid = ? AND status = ?", (biennium_rowid, status))
            bill_status_rowid = cur.fetchone()[0]

            cur.execute("INSERT OR IGNORE INTO bill_status (bill_rowid, bill_status_rowid, action_date) VALUES (?, ?, ?)", (bill_rowid, bill_status_rowid, action_date))
            
            if history_line:
                history_line = history_line.text
                cur.execute("INSERT OR IGNORE INTO bill_history (bill_rowid, action_date, history_line) VALUES (?, ?, ?)", (bill_rowid, action_date, history_line))
            db.commit()
    await session.close()

asyncio.run(main())
