import requests_cache
from bs4 import BeautifulSoup, NavigableString
import re
import pathlib
import sys
import subprocess
import arrow

PUSH = False

api_root_url = "http://wslwebservices.leg.wa.gov"

requests = requests_cache.CachedSession("committee_cache")

committee_path = pathlib.Path("bill/")

meetings_by_bill = {}

def add_lines(lines, active, inactive):
    if active:
        lines.append("Active bills:")
        lines.extend(active)
    if inactive:
        lines.append("<details>")
        lines.append("    <summary>Click to view inactive bills</summary>")
        lines.append("")
        lines.extend(inactive)
        lines.append("</details>")


for start_year in range(2021, 2023, 2):
    biennium = f"{start_year:4d}-{(start_year+1) % 100:02d}"
    print(biennium)

    url = api_root_url + f"/CommitteeMeetingService.asmx/GetCommitteeMeetings?beginDate={start_year}-01-01&endDate={start_year+1}-12-31"
    print(url)
    meetings = requests.get(url)
    meetings = BeautifulSoup(meetings.text, "xml")
    count = 0
    for info in meetings.find_all("CommitteeMeeting"):
        count += 1
        agendaId = info.AgendaId.text
        print(info.AgendaId.text, info.Date.text, info.RevisedDate.text)
        url = api_root_url + f"/CommitteeMeetingService.asmx/GetCommitteeMeetingItems?agendaId={agendaId}"
        print(url)
        items = requests.get(url)
        items = BeautifulSoup(items.text, "xml")
        for item in items.find_all("CommitteeMeetingItem"):
            billId = item.BillId.text
            if billId:
                bill_number = billId.split(" ")[1]
                if bill_number not in meetings_by_bill:
                    meetings_by_bill[bill_number] = []
                meetings_by_bill[bill_number].append((arrow.get(info.Date.text), info, item))
            else:
                print(item)

    print("-----")
    now = arrow.now()
    active = {}
    for bill_number in meetings_by_bill:
        meetings = meetings_by_bill[bill_number]
        meetings.sort(key=lambda x: x[0])
        latest_date = meetings[-1][0]
        if latest_date < now:
            continue

        activity = ""

        print(bill_number)
        for dt, meeting, item in meetings:
            if now < dt:
                if not activity:
                    activity = item.HearingTypeDescription.text + " " + dt.format("ddd, MMM D h:mm a")
                print(activity)
                print(item)
                print(meeting)
                # doc link: https://app.leg.wa.gov/committeeschedules/Home/Documents/29441
                mId = meeting.AgendaId.text
                chamber = meeting.Agency.text
                aId = item.AgendaId.text
                caId = meeting.Committee.Id.text
                print(mId, chamber, aId, caId)
                print("[live]()") # tId=2
                print("[written]()") # tId=4
                print("[+/-]()") # tId=3

        print()
        active[bill_number] = activity
    print(count, "meetings")
    print(len(active), "active bills")

    bill_index = pathlib.Path(f"bill/{biennium}/README.md")
    new_lines = []
    active_lines = []
    inactive_lines = []
    for line in bill_index.read_text().split("\n"):
        if not line:
            # add active/inactive sections
            add_lines(new_lines, active_lines, inactive_lines)
            active_lines = []
            inactive_lines = []
            new_lines.append(line)
            pass
        elif line.startswith("*"):
            # parse out bill number and bin
            bill_number = line.split()[2][:4]
            if "|" in line:
                line = line.split("|")[0][:-1]
            if bill_number in active:
                active_lines.append(line + " | *" + active[bill_number] + "*")
            else:
                inactive_lines.append(line)
            pass
        elif line.strip().startswith("<") or line.startswith("Active bills"):
            # Skip any <details> or <summary> that we've already added.
            pass
        elif line:
            new_lines.append(line)

    add_lines(new_lines, active_lines, inactive_lines)
    bill_index.write_text("\n".join(new_lines))