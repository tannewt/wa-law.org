from bs4 import BeautifulSoup
from collections import namedtuple
import arrow
import url_history
import pathlib
import csv

requests = url_history.HistorySession("committee_cache.db")

api_root_url = "http://wslwebservices.leg.wa.gov"
csi_root_url = "https://app.leg.wa.gov/csi"


def request_biennium_meetings(start_year, force_fetch):
    url = api_root_url + \
        f"/CommitteeMeetingService.asmx/GetCommitteeMeetings?beginDate={start_year}-01-01&endDate={start_year+1}-12-31"
    print(f"Loading {url}")
    response = requests.get(url, fetch_again=force_fetch)
    return BeautifulSoup(response.decode("utf-8"), "xml")


def extract_meetings(meetings_xml):
    all_meetings = []
    end_time = 0
    for info in meetings_xml.find_all("CommitteeMeeting"):
        agendaId = info.AgendaId.text
        notes = info.Notes.text
        agency = info.Agency.text
        committee_name = info.Name.text
        acronym = info.Acronym.text
        meeting_date = arrow.get(info.Date.text)
        last_revised = arrow.get(info.RevisedDate.text)
        meeting_dict = {
            "agency": agency,
            "committee": committee_name,
            "acronym": acronym,
            "start": meeting_date,
            "revised": last_revised,
            "notes": notes,
            "agendaId": agendaId,
            "info": info
        }
        all_meetings.append((meeting_date, meeting_dict))
        if "scheduled to end" in notes:
            end_time += 1
    print(f"Found {len(all_meetings)} meetings, end_time: {end_time}")
    return all_meetings


def load_committee_meeting_items(agenda_id, force_fetch):
    url = api_root_url + f"/CommitteeMeetingService.asmx/GetCommitteeMeetingItems?agendaId={agenda_id}"
    response = requests.get(url, fetch_again=force_fetch)
    items_xml = BeautifulSoup(response.decode("utf-8"), "xml")
    return items_xml.find_all("CommitteeMeetingItem")


def populate_meeting_items(all_meetings, meetings_by_bill, now, force_fetch):
    for (meeting_date, meeting) in all_meetings:
        upcoming = now < meeting_date
        agenda_id = meeting["agendaId"]
        items = load_committee_meeting_items(agenda_id, upcoming and force_fetch)
        agenda = {}
        meeting["agenda"] = agenda
        for item in items:
            hearing_type = item.HearingTypeDescription.text
            if hearing_type not in agenda:
                agenda[hearing_type] = []
            billId = item.BillId.text
            agenda[hearing_type].append((billId, item.ItemDescription.text))
            if billId:
                bill_number = billId.split(" ")[1]
                if bill_number not in meetings_by_bill:
                    meetings_by_bill[bill_number] = []
                meetings_by_bill[bill_number].append((meeting_date, meeting["info"], item, meeting))


def is_public_meeting_item(item):
  return item.HearingType.text == "Public"


AgendaItem = namedtuple("AgendaItem", ["agendaId", "mId", "aId", "caId", "text"])

agenda_cache = {}
agenda_fn = pathlib.Path("data/agenda_items.csv")
with agenda_fn.open("r") as f:
    for row in csv.reader(f):
        if row[0] == "agendaId":
            continue
        agendaId = row[0]
        if agendaId not in agenda_cache:
            agenda_cache[agendaId] = []
        agenda_cache[agendaId].append(AgendaItem(*row))

def load_agenda_items(agendaId, force_fetch):
    if not force_fetch and agendaId in agenda_cache:
        return agenda_cache[agendaId]
    url = csi_root_url + f"/Home/GetAgendaItems/?chamber=House&meetingFamilyId={agendaId}"
    response = requests.get(url, fetch_again=force_fetch)
    xml_items = BeautifulSoup(response.decode("utf-8"), "lxml")
    agenda_items = []
    for item in xml_items.find_all(class_="agendaItem"):
        chamber, mId, aId, caId = [x.strip(" ')") for x in item["onclick"].split(",")[1:]]
        agenda_items.append(AgendaItem(agendaId, mId, aId, caId, item.text))
    if agendaId not in agenda_cache:
        agenda_cache[agendaId] = []
    for item in agenda_items:
        if item in agenda_cache[agendaId]:
            continue
        agenda_cache[agendaId].append(item)
    return agenda_cache[agendaId]

def save_cache_files():
    with agenda_fn.open("w") as f:
        writer = csv.writer(f)
        writer.writerow(["agendaId","mId","aId","caId","text"])
        for agendaId in sorted(agenda_cache.keys()):
            writer.writerows(agenda_cache[agendaId])


def load_all_meetings(start_year, force_fetch):
  meetings_xml = request_biennium_meetings(start_year, force_fetch)
  return extract_meetings(meetings_xml)


def load_biennium_meetings_by_bill(start_year, now, force_fetch):
    all_meetings = load_all_meetings(start_year, force_fetch)
    meetings_by_bill = {}
    populate_meeting_items(all_meetings, meetings_by_bill, now, force_fetch)
    return all_meetings, meetings_by_bill


def load_testifier_counts(caId, force_fetch):
    url = csi_root_url + f"/Home/GetOtherTestifiers/?agendaItemId={caId}"
    testifiers = requests.get(url, fetch_again=force_fetch)
    testifiers = BeautifulSoup(testifiers.decode("utf-8"), "lxml")
    results = []
    for row in testifiers.find_all("tr"):
        cols = [c.text for c in row.find_all("td")]
        if not cols:
            continue
        results.append(cols[1:])
    return results

# Lists upcoming hearings in order of least to most sign-ins
if __name__ == "__main__":
    start_year = 2021
    force_fetch = False
    all_meetings = load_all_meetings(start_year, force_fetch)

    agenda_items = set()
    for (date, meeting) in all_meetings:
      if date > arrow.now(): # only future agenda items load anyway
        items = load_agenda_items(meeting["agendaId"], True)
        agenda_items.update(items)

    print(f"Found {len(agenda_items)} agenda items")

    hearings = []
    for hearing in agenda_items:
      counts = load_testifier_counts(hearing.caId, False)
      hearings.append({"text": hearing.text, "counts": counts})

    hearings.sort(key=lambda h: h["counts"].get("Pro", 0) + h["counts"].get("Con", 0))

    for hearing in hearings:
      print(f"\"{hearing['text']}\" Sign-ins: {hearing['counts']}")

    save_cache_files()
