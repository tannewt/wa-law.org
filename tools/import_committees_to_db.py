from committee_data import *

from bs4 import BeautifulSoup
import pathlib
import arrow
import utils
import datetime

AgendaItem = namedtuple("AgendaItem", ["agendaId", "mId", "aId", "caId", "text"])

db = utils.get_db()
cur = db.cursor()

FORCE_FETCH = True

for start_year in range(2023, 2025, 2):
    biennium = f"{start_year:4d}-{(start_year+1) % 100:02d}"
    cur.execute("SELECT rowid FROM bienniums WHERE name = ?", (biennium,))
    biennium_rowid = cur.fetchone()[0]
    cur.execute("SELECT rowid FROM sessions WHERE name = ?", (str(start_year),))
    session_rowid = cur.fetchone()[0]
    print(biennium)
    now = arrow.now()

    all_meetings, meetings_by_bill = load_biennium_meetings_by_bill(start_year, now, FORCE_FETCH)

    print("-----")
    biennium_path = pathlib.Path(f"bill/{biennium}")
    active = {}
    heard = {}
    for bill_number in meetings_by_bill:
        meetings = meetings_by_bill[bill_number]
        meetings.sort(key=lambda x: x[0])

        cur.execute("SELECT rowid FROM bills WHERE number = ? AND biennium_rowid = ?", (bill_number, biennium_rowid))
        bill_rowid = cur.fetchone()
        if bill_rowid is None:
            print("skipping", bill_number)
            continue
        bill_rowid = bill_rowid[0]

        activity = ""

        testify = False

        for dt, meeting, item, meeting_dict in meetings:
            mId = meeting.AgendaId.text
            chamber = meeting.Agency.text
            if not activity:
                activity = item.HearingTypeDescription.text + " " + dt.format("ddd, MMM D h:mm a")
            committees = meeting.find_all("Committee")
            if len(committees) > 1:
                print(committees)
                continue
            # doc link: https://app.leg.wa.gov/committeeschedules/Home/Documents/29441

            committee = committees[0]
            cur.execute("INSERT OR IGNORE INTO agencies VALUES (?)", (committee.Agency.text,))
            cur.execute("SELECT rowid FROM agencies WHERE name = ?", (committee.Agency.text,))
            agency_rowid = cur.fetchone()[0]

            committee_name = committee.Name.text.replace("&amp;", "&")
            if ";" in committee_name:
                raise RuntimeError()

            cur.execute("INSERT OR IGNORE INTO committees VALUES (?, ?, ?, ?, ?)", (int(committee.Id.text), session_rowid, committee_name, agency_rowid, committee.Acronym.text))
            cur.execute("SELECT rowid FROM committees WHERE id = ?", (int(committee.Id.text),))
            committee_rowid = cur.fetchone()[0]

            # print("[live]()") # tId=2
            # print("[written]()") # tId=4
            # print("[+/-]()") # tId=3

            cur.execute("INSERT OR IGNORE INTO meetings(mId, committee_rowid, start_time, notes) VALUES (?, ?, ?, ?)", (mId, committee_rowid, dt.datetime, meeting.Notes.text))
            cur.execute("SELECT rowid FROM meetings WHERE mId = ?;", (mId,))
            meeting_rowid = cur.fetchone()[0]
            db.commit()

            # Look back in our fetch history if the latest page doesn't have any items. They
            # disappear after a meeting happens.
            items = []
            history_index = -1
            url = csi_root_url + f"/Home/GetAgendaItems/?chamber=House&meetingFamilyId={mId}"
            while not items:
                response = requests.get(url, fetch_again=FORCE_FETCH, index=history_index)
                if not response:
                    print(url)
                    break
                history_index -= 1
                xml_items = BeautifulSoup(response.decode("utf-8"), "lxml")
                for item in xml_items.find_all(class_="agendaItem"):
                    chamber, mId, aId, caId = [x.strip(" ')") for x in item["onclick"].split(",")[1:]]
                    items.append(AgendaItem(agendaId, mId, aId, caId, item.text))


            for item in items:
                if bill_number not in item.text:
                    continue
                cur.execute("INSERT OR IGNORE INTO agenda_items VALUES (?, ?, ?, ?)", (meeting_rowid, bill_rowid, item.caId, item.text))
                cur.execute("SELECT rowid FROM agenda_items WHERE caId = ?", (item.caId,))
                item_rowid = cur.fetchone()[0]

                url = csi_root_url + f"/{chamber}/TestimonyTypes/?chamber={chamber}&meetingFamilyId={item.mId}&agendaItemFamilyId={item.aId}&agendaItemId={item.caId}"
                testimonyOptions = requests.get(url)
                testimonyOptions = BeautifulSoup(testimonyOptions.decode("utf-8"), "lxml")
                for option in testimonyOptions.find_all("a"):

                    cur.execute("INSERT OR IGNORE INTO testimony_options VALUES (?)", (option.text,))
                    cur.execute("SELECT rowid FROM testimony_options WHERE option = ?", (option.text,))
                    option_rowid = cur.fetchone()[0]
                    
                    cur.execute("INSERT OR IGNORE INTO testimony_links VALUES (?, ?, ?)", (item_rowid, option_rowid, option["href"]))
                db.commit()

        if activity:
            active[bill_number] = activity

    print("Getting testifiers")
    item_cur = db.cursor()
    item_cur.execute("SELECT rowid, caId FROM agenda_items WHERE caId IS NOT NULL")
    for agenda_item_rowid, caId in item_cur:
        url = csi_root_url + f"/Home/GetOtherTestifiers/?agendaItemId={caId}"
        testifiers = requests.get(url, fetch_again=FORCE_FETCH)
        if not testifiers:
            print("failed to load", url)
            continue
        testifiers = BeautifulSoup(testifiers.decode("utf-8"), "lxml")
        for table in testifiers.find_all("table"):
            if table["id"] not in ("testifyingDataTable", "notTestifyingDataTable"):
                print(table["id"])
                raise RuntimeError()
            testifying = table["id"] == "testifyingDataTable"
            for row in table.find_all("tr"):
                cols = [c.text for c in row.find_all("td")]
                if not cols:
                    continue
                last_name, first_name = cols[1].split(", ", maxsplit=1)
                last_name = last_name.strip()
                first_name = first_name.strip()
                organization = cols[2].strip()
                position = cols[3]
                sign_in_time = datetime.datetime.strptime(cols[4], "%m/%d/%Y %H:%M:%S %p")
                cur.execute("INSERT OR IGNORE INTO positions VALUES (?)", (position,))
                cur.execute("SELECT rowid FROM positions WHERE position = ?;", (position,))
                position_rowid = cur.fetchone()[0]

                # print(cols)
                # print(last_name, first_name, testifying, organization, position, sign_in_time)
                cur.execute("INSERT OR IGNORE INTO testifiers (agenda_item_rowid, first_name, last_name, organization, position_rowid, testifying, sign_in_time) VALUES"
                                                   "(?, ?, ?, ?, ?, ?, ?)",
                                                   (agenda_item_rowid, first_name, last_name, organization, position_rowid, testifying, sign_in_time))

                db.commit()
        # https://app.leg.wa.gov
    print(len(all_meetings), "meetings")
    print(len(active), "active bills")
    # for bill_number in heard:
    #     print(bill_number, heard[bill_number])
