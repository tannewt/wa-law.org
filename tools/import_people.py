import requests_cache
from bs4 import BeautifulSoup, NavigableString
import re
import pathlib
import sys
import subprocess
import arrow
import urllib.parse

PUSH = False

api_root_url = "http://wslwebservices.leg.wa.gov"
csi_root_url = "https://app.leg.wa.gov/csi"
root_url = "https://app.leg.wa.gov"

requests = requests_cache.CachedSession("people_cache")

email_by_name = {}
committee_members = {
    "Senate": {},
    "House": {}
}

for start_year in range(2021, 2023, 2):
    biennium = f"{start_year:4d}-{(start_year+1) % 100:02d}"
    print(biennium)

    url = api_root_url + f"/SponsorService.asmx/GetSponsors?biennium={biennium}"
    print(url)
    sponsors = requests.get(url)
    sponsors = BeautifulSoup(sponsors.text, "xml")
    for member in sponsors.find_all("Member"):
        name = member.FirstName.text + " " + member.LastName.text
        email = member.Email.text
        print(member)
        print(member.Email.text, name , member.District.text)
        email_by_name[name] = email

    url = api_root_url + f"/CommitteeService.asmx/GetCommittees?biennium={biennium}"
    print(url)
    committees = requests.get(url)
    committees = BeautifulSoup(committees.text, "xml")
    for committee in committees.find_all("Committee"):
        agency = committee.Agency.text
        name = committee.Name.text
        acronym = committee.Acronym.text
        print(agency, acronym, name)
        name_safe = urllib.parse.quote_plus(name)
        url = api_root_url + f"/CommitteeService.asmx/GetCommitteeMembers?biennium={biennium}&agency={agency}&committeeName={name_safe}"
        members = requests.get(url)
        members = BeautifulSoup(members.text, "xml")
        # for member in members.find_all("Member"):
        #     print(" ", member.Email.text)

# Current members
url = root_url + f"/ContentParts/MemberDirectory/?a=House"
print(url)
reps = requests.get(url)
reps = BeautifulSoup(reps.text, "lxml")
rep_lines = ["# 2021-22 House of Representatives"]
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
rep_page.write_text("\n".join(rep_lines))

house_lines = ["# House of Representatives", "* [2021-22](2021-22/)"]
house_page = pathlib.Path("house/README.md")
house_page.write_text("\n".join(house_lines))

url = root_url + f"/ContentParts/MemberDirectory/?a=Senate"
print(url)
senators = requests.get(url)
senators = BeautifulSoup(senators.text, "lxml")
senate_lines = ["# 2021-22 Senate"]
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

senate_page = pathlib.Path("senate/2021-22/README.md")
senate_page.write_text("\n".join(senate_lines))

senate_lines = ["# Senate", "* [2021-22](2021-22/)"]
senate_page = pathlib.Path("senate/README.md")
senate_page.write_text("\n".join(house_lines))
