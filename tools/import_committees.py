import requests_cache
from bs4 import BeautifulSoup, NavigableString
import re
import pathlib
import sys
import subprocess

PUSH = False

api_root_url = "http://wslwebservices.leg.wa.gov"

requests = requests_cache.CachedSession("committee_cache")

committee_path = pathlib.Path("bill/")

meetings_by_bill = {}

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
                meetings_by_bill[bill_number].append((info, item))
            else:
                print(item)

    print("-----")

    for bill_number in meetings_by_bill:
        print(bill_number)
        for meeting, item in meetings_by_bill[bill_number]:
            print(meeting.Date.text, item.HearingTypeDescription.text)
        print()
    print(info)
    print(count, "meetings")

