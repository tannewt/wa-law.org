import asyncio
import url_history
from bs4 import BeautifulSoup, NavigableString
import re
import pathlib
import sys
import subprocess
import arrow
import urllib.parse


async def main():
    PUSH = False

    api_root_url = "http://wslwebservices.leg.wa.gov"
    csi_root_url = "https://app.leg.wa.gov/csi"
    root_url = "https://app.leg.wa.gov"

    requests = url_history.HistorySession("people_cache.db")

    email_by_name = {}
    committee_members = {
        "Senate": {},
        "House": {}
    }

    for start_year in range(2023, 2025, 2):
        biennium = f"{start_year:4d}-{(start_year+1) % 100:02d}"
        print(biennium)

        url = api_root_url + f"/SponsorService.asmx/GetSponsors?biennium={biennium}"
        print(url)
        sponsors = await requests.get(url)
        sponsors = BeautifulSoup(sponsors.decode("utf-8"), "xml")
        for member in sponsors.find_all("Member"):
            name = member.FirstName.text + " " + member.LastName.text
            email = member.Email.text
            print(member)
            print(member.Email.text, name , member.District.text)
            email_by_name[name] = email

        committees_by_agency = {}

        url = api_root_url + f"/CommitteeService.asmx/GetCommittees?biennium={biennium}"
        print(url)
        committees = (await requests.get(url)).decode("utf-8")
        committees = BeautifulSoup(committees, "xml")
        for committee in committees.find_all("Committee"):
            agency = committee.Agency.text
            name = committee.Name.text
            acronym = committee.Acronym.text
            print(agency, acronym, name)
            if agency not in committees_by_agency:
                committees_by_agency[agency] = []
            committees_by_agency[agency].append(f"* [{name}]({acronym}/)")
            name_safe = urllib.parse.quote_plus(name)
            committee_lines = [f"# {name}"]
            committee_lines.append("## Members")

            url = api_root_url + f"/CommitteeService.asmx/GetCommitteeMembers?biennium={biennium}&agency={agency}&committeeName={name_safe}"
            members = (await requests.get(url)).decode("utf-8")
            members = BeautifulSoup(members, "xml")
            for member in members.find_all("Member"):
                member_name = member.Name.text
                email = member.Email.text
                slug = email.split("@")[0].lower()
                committee_lines.append(f"* [{member_name}](/person/leg/{slug}.md)")
            committee_page = pathlib.Path(f"{agency.lower()}/{biennium}/{acronym}/README.md")
            committee_page.parent.mkdir(parents=True, exist_ok=True)
            committee_page.write_text("\n".join(committee_lines))

    # Current members
    url = root_url + f"/ContentParts/MemberDirectory/?a=House"
    print(url)
    reps = await requests.get(url)
    reps = BeautifulSoup(reps.decode("utf-8"), "lxml")
    rep_lines = ["# 2021-22 House of Representatives"]
    rep_lines.append("## Committees")
    rep_lines.extend(committees_by_agency["House"])
    rep_lines.append("")
    rep_lines.append("## Members")
    for rep in reps.find_all(class_="memberInformation"):
        photo = rep.img
        name = photo["alt"]
        email = email_by_name[name]
        slug = email.split("@")[0].lower()
        person_page = pathlib.Path(f"person/leg/{slug}.md")
        rep_lines.append(f"* [{name}](/person/leg/{slug}.md)")
        person_page.write_text(f"# {name}")
        for link in rep.find_all("a"):
            # print(link["href"], link.text)
            pass

    rep_page = pathlib.Path("house/2021-22/README.md")
    rep_page.parent.mkdir(parents=True, exist_ok=True)
    rep_page.write_text("\n".join(rep_lines))

    house_lines = ["# House of Representatives", "* [2021-22](2021-22/)"]
    house_page = pathlib.Path("house/README.md")
    house_page.write_text("\n".join(house_lines))

    url = root_url + f"/ContentParts/MemberDirectory/?a=Senate"
    print(url)
    senators = await requests.get(url)
    senators = BeautifulSoup(senators.decode("utf-8"), "lxml")
    senate_lines = ["# 2021-22 Senate"]
    senate_lines.append("## Committees")
    senate_lines.extend(committees_by_agency["Senate"])
    senate_lines.append("")
    senate_lines.append("## Members")
    for senator in senators.find_all(class_="memberInformation"):
        photo = senator.img
        name = photo["alt"]
        email = email_by_name[name]
        slug = email.split("@")[0].lower()
        person_page = pathlib.Path(f"person/leg/{slug}.md")
        senate_lines.append(f"* [{name}](/person/leg/{slug}.md)")
        person_page.write_text(f"# {name}")
        for link in rep.find_all("a"):
            # print(link["href"], link.text)
            pass
    senate_lines.append("")

    senate_page = pathlib.Path("senate/2021-22/README.md")
    senate_page.parent.mkdir(parents=True, exist_ok=True)
    senate_page.write_text("\n".join(senate_lines))

    senate_lines = ["# Senate", "* [2021-22](2021-22/)"]
    senate_page = pathlib.Path("senate/README.md")
    senate_page.write_text("\n".join(house_lines))

    await requests.close()

asyncio.run(main())
