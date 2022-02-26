from committee_data import *

from bs4 import BeautifulSoup
import pathlib
import arrow
import utils

committee_path = pathlib.Path("bill/")

TESTIFY_REMOTE = 'I would like to testify remotely'
TESTIFY_NOTED = 'I would like my position noted for the legislative record'
TESTIFY_WRITTEN = 'I would like to submit written testimony'

FORCE_FETCH = False

def add_lines(lines, active, heard, inactive):
    if active:
        lines.append("Active bills:")
        lines.extend(active)
        lines.append("")
    if heard:
        lines.append("Heard bills:")
        lines.extend(heard)
        lines.append("")
    if inactive:
        lines.append("")
        lines.append("<details>")
        lines.append("    <summary>Click to view inactive bills</summary>")
        lines.append("")
        lines.extend(inactive)
        lines.append("</details>")
        lines.append("")


for start_year in range(2021, 2023, 2):
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

        bill_path = list(biennium_path.glob(f"*/{bill_number}/README.md"))
        if bill_path and bill_path[0].exists():
            bill_path = bill_path[0]

        for dt, meeting, item, meeting_dict in meetings:
            if now < dt:
                if not activity:
                    activity = item.HearingTypeDescription.text + " " + dt.format("ddd, MMM D h:mm a")
                # print(activity)
                # print(item)
                # print(meeting)
                # doc link: https://app.leg.wa.gov/committeeschedules/Home/Documents/29441
                mId = meeting.AgendaId.text
                # print("[live]()") # tId=2
                # print("[written]()") # tId=4
                # print("[+/-]()") # tId=3

                url = csi_root_url + f"/Home/GetAgendaItems/?chamber=House&meetingFamilyId={mId}"
                agendaItems = requests.get(url, force_fetch=FORCE_FETCH)
                items = BeautifulSoup(agendaItems.text, "lxml")
                for item in items.find_all(class_="agendaItem"):
                    if bill_number not in item.text:
                        continue
                    chamber, mId, aId, caId = [x.strip(" ')") for x in item["onclick"].split(",")[1:]]
                    url = csi_root_url + f"/{chamber}/TestimonyTypes/?chamber={chamber}&meetingFamilyId={mId}&agendaItemFamilyId={aId}&agendaItemId={caId}"
                    testimonyOptions = requests.get(url)
                    testimonyOptions = BeautifulSoup(testimonyOptions.text, "lxml")
                    testimony_links = {}
                    for option in testimonyOptions.find_all("a"):
                        testimony_links[option.text] = option["href"]

                    if bill_path:
                        new_lines = []
                        committee = meeting.LongName.text
                        testify_date = dt.format("ddd, MMM D") + " at " + dt.format("h:mm a")
                        new_lines.append(f"The {committee} committee will be holding a public hearing on {testify_date}. There are three ways to testify. You can do more than one.")
                        new_lines.append(f"* 👍 / 👎 [Sign in support or oppose a bill.](https://app.leg.wa.gov{testimony_links[TESTIFY_NOTED]})")
                        new_lines.append(f"* ✍️ [Provide written feedback on a bill.](https://app.leg.wa.gov{testimony_links[TESTIFY_WRITTEN]})")
                        new_lines.append(f"* 📺 [Sign up to give live testimony over Zoom.](https://app.leg.wa.gov{testimony_links[TESTIFY_REMOTE]})")
                        new_lines.append("")
                        new_lines.append(f"Testimony is public record. You can see who is signed up to testify [on the website](https://app.leg.wa.gov/csi/Home/GetOtherTestifiers/?agendaItemId={caId}).")
                        new_lines.append("")
                        utils.add_or_update_section(bill_path, "## Testify", new_lines)
                        testify = True
            else:
                if not is_public_meeting_item(item):
                    continue
                mId = meeting.AgendaId.text
                # Only load these from the cache. After the meeting occurs, the
                # page no longer holds the IDs we care about.
                agenda_items = load_agenda_items(mId, False)
                for item in agenda_items:
                    if bill_number not in item.text:
                        continue

                    totals = load_testifier_counts(item.caId, FORCE_FETCH)

                    if bill_number in heard:
                        for k in totals:
                            if k in heard[bill_number]:
                                heard[bill_number][k] += totals[k]
                            else:
                                heard[bill_number][k] = totals[k]
                    else:
                        heard[bill_number] = totals

        if activity:
            active[bill_number] = activity

        if bill_path and not testify:
            utils.remove_section(bill_path, "## Testify")

        #
        # https://app.leg.wa.gov
    print(len(all_meetings), "meetings")
    print(len(active), "active bills")

    bill_index = pathlib.Path(f"bill/{biennium}/README.md")
    new_lines = []
    active_lines = []
    inactive_lines = []
    heard_lines = []
    heading = None
    for line in bill_index.read_text().split("\n"):
        if line.startswith("#"):
            heading = line
            # add active/inactive sections
            add_lines(new_lines, active_lines, heard_lines, inactive_lines)
            active_lines = []
            heard_lines = []
            inactive_lines = []
            new_lines.append(line)
            pass
        elif line.startswith("*"):
            if heading == "# 2021-22":
                new_lines.append(line)
                continue
            # parse out bill number and bin
            bill_number = line.split()[2][:4]
            if "|" in line:
                line = line.split("|")[0][:-1]
            thumbs = ""
            if bill_number in heard:
                pro = heard[bill_number].get("Pro", 0)
                con = heard[bill_number].get("Con", 0)
                other = heard[bill_number].get("Other", 0)
                thumbs = f" **{pro}👍** **{con}👎** **{other}❓**"
            if bill_number in active:
                active_lines.append(line + " | *" + active[bill_number] + "*" + thumbs)
            elif bill_number in heard:
                heard_lines.append(line + f" |" + thumbs)
            else:
                inactive_lines.append(line)
            pass
        elif line.strip().startswith("<") or line.startswith("Active bills") or line.startswith("Heard bills"):
            # Skip any <details> or <summary> that we've already added.
            pass
        elif line:
            new_lines.append(line)

    add_lines(new_lines, active_lines, heard_lines, inactive_lines)
    bill_index.write_text("\n".join(new_lines))

    all_meetings.sort(key=lambda x: x[0])

    hearing_types = ["Public Hearing", "Executive Session", "Agenda", "Work Session"]

    pages = {}

    last_date = {}
    last_time = {}

    for start, meeting in all_meetings:
        #print(start, meeting)
        event_description = []
        title = ""
        committee_name = meeting["committee"]
        bills = []
        for hearing_type in hearing_types:
            if hearing_type not in meeting["agenda"]:
                continue
            event_description.append(hearing_type)
            title = hearing_type
            for bill_id, description in meeting["agenda"][hearing_type]:
                if not bill_id:
                    event_description.append(f"* {description}")
                else:
                    originator, number = bill_id.split()
                    originator = originator[-2:]
                    bill_slug = f"{originator.lower()}/{number}"
                    line = f"* [{bill_id}](/bill/{biennium}/{bill_slug}/) - {description}"
                    bills.append((hearing_type, f"bill/{biennium}/{bill_slug}/README.md"))

                    bill_number = bill_id.split()[1]
                    thumbs = ""
                    if bill_number in heard:
                        pro = heard[bill_number].get("Pro", 0)
                        con = heard[bill_number].get("Con", 0)
                        other = heard[bill_number].get("Other", 0)
                        thumbs = f" **{pro}👍** **{con}👎** **{other}❓**"
                    line += thumbs
                    event_description.append(line)
            event_description.append("")
        event_description.append(meeting["notes"])
        agency = meeting["agency"]
        acronym = meeting["acronym"]
        if agency in ("Joint", "Other"):
            continue

        if start < now:
            continue
        committee_file = f"{agency.lower()}/{biennium}/{acronym}/README.md"
        agency_file = f"{agency.lower()}/{biennium}/README.md"
        if committee_file not in pages:
            pages[committee_file] = ["## Upcoming Meetings"]
        if agency_file not in pages:
            pages[agency_file] = ["## Upcoming Meetings"]

        meeting_date = start.format("ddd, MMM D")
        meeting_time = start.format("h:mm a")
        pages[committee_file].append(f"### {meeting_date} at {meeting_time}")
        pages[committee_file].extend(event_description)
        pages[committee_file].append("")

        if agency not in last_date or last_date[agency] != meeting_date:
            pages[agency_file].append(f"### {meeting_date}")
            dash_date = start.format("MM-DD-YYYY")
            pages[agency_file].append(f"Double check [the official calendar](https://app.leg.wa.gov/committeeschedules/#/{agency}/0/{dash_date}/{dash_date}/Agenda///Bill/)")

        if agency not in last_time or last_time[agency] != meeting_time:
            pages[agency_file].append(f"#### {meeting_time}")

        pages[agency_file].append(f"**{committee_name}**")
        pages[agency_file].extend(event_description)
        pages[agency_file].append("")

        last_date[agency] = meeting_date
        last_time[agency] = meeting_time

        for hearing_type, bill in bills:
            if bill == "bill/2021-22/hb/1043/README.md":
                print(start, now)
            if bill not in pages:
                pages[bill] = ["## Upcoming Meetings"]
            pages[bill].append(f"* {meeting_date} at {meeting_time} - [{agency} {committee_name}](/{agency.lower()}/{biennium}/{acronym}/) {hearing_type}")

    for page in pages:
        path = pathlib.Path(page)
        if not path.exists():
            continue
        new_contents = pages[page]
        utils.add_or_update_section(path, new_contents[0], new_contents[1:])
