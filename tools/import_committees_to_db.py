from committee_data import *

from bs4 import BeautifulSoup
import pathlib
import arrow
import utils
import datetime

db = utils.get_db()

FORCE_FETCH = False

for start_year in range(2023, 2025, 2):
    biennium = f"{start_year:4d}-{(start_year+1) % 100:02d}"
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

        activity = ""

        testify = False

        for dt, meeting, item, meeting_dict in meetings:
            mId = meeting.AgendaId.text
            chamber = meeting.Agency.text
            if not activity:
                activity = item.HearingTypeDescription.text + " " + dt.format("ddd, MMM D h:mm a")
            # print(activity)
            # print(item)
            # print(meeting)
            # doc link: https://app.leg.wa.gov/committeeschedules/Home/Documents/29441


            # print("[live]()") # tId=2
            # print("[written]()") # tId=4
            # print("[+/-]()") # tId=3

            items = load_agenda_items(mId, FORCE_FETCH)
            for item in items:
                if bill_number not in item.text:
                    continue
                print(item, bill_number)
                cur = db.cursor()
                url = csi_root_url + f"/Home/GetOtherTestifiers/?agendaItemId={item.caId}"
                testifiers = requests.get(url, fetch_again=FORCE_FETCH)
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
                        last_name, first_name = cols[1].split(", ")
                        organization = cols[2]
                        position = cols[3]
                        sign_in_time = datetime.datetime.strptime(cols[4], "%m/%d/%Y %H:%M:%S %p")
                        cur.execute("INSERT OR IGNORE INTO positions VALUES (?)", (position,))
                        cur.execute("SELECT rowid FROM positions WHERE position = ?;", (position,))
                        position_rowid = cur.fetchone()[0]

                        cur.execute("SELECT rowid FROM bills WHERE year = 2023 AND id = ?", (bill_number,))
                        bill_rowid = cur.fetchone()[0]

                        print(cols)
                        print(last_name, first_name, testifying, organization, position, sign_in_time)
                        cur.execute("INSERT INTO testifiers (bill_rowid, first_name, last_name, organization, position_rowid, testifying, sign_in_time) VALUES"
                                                           "(?, ?, ?, ?, ?, ?, ?)",
                                                           (bill_rowid, first_name, last_name, organization, position_rowid, testifying, sign_in_time))

                url = csi_root_url + f"/{chamber}/TestimonyTypes/?chamber={chamber}&meetingFamilyId={item.mId}&agendaItemFamilyId={item.aId}&agendaItemId={item.caId}"
                testimonyOptions = requests.get(url)
                testimonyOptions = BeautifulSoup(testimonyOptions.decode("utf-8"), "lxml")
                testimony_links = {}
                for option in testimonyOptions.find_all("a"):
                    testimony_links[option.text] = option["href"]
                db.commit()

        if activity:
            active[bill_number] = activity

        #
        # https://app.leg.wa.gov
    print(len(all_meetings), "meetings")
    print(len(active), "active bills")
    # for bill_number in heard:
    #     print(bill_number, heard[bill_number])
