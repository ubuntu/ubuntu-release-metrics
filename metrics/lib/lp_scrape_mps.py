# Copyright 2026 Canonical Ltd

"""Count Launchpad merge proposals assigned to a team via web scraping.

This works around https://bugs.launchpad.net/launchpad/+bug/1979817: the
Launchpad API only covers Bazaar branches, not Git repositories, so MPs
against Git repos must be discovered by scraping the web UI instead.
"""

import re

import bs4
import requests

_MATCH_MP_HREF = re.compile(r"^/.*/\+merge/\d+$")

# Matches section headings that list MPs the team is asked to review:
#   "Requested reviews by <team>"  or  "Reviews <team> can do"
_MATCH_CAN_DO = re.compile(r"^(Requested reviews)|(Reviews) .* can do$")

LAUNCHPAD_CODE_BASE = "https://code.launchpad.net"


def count_team_reviews(team_name):
    """Return the number of open MPs where *team_name* is a requested reviewer.

    Fetches ``https://code.launchpad.net/~<team_name>/+activereviews`` and counts
    the merge-proposal links that appear under "Requested reviews" or
    "Reviews … can do" section headings.
    """
    url = f"{LAUNCHPAD_CODE_BASE}/~{team_name}/+activereviews"
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    soup = bs4.BeautifulSoup(response.text, features="lxml")

    count = 0
    in_can_do_section = False

    for tag in soup(
        lambda t: (t.name == "td" and "section-heading" in t.get("class", []))
        or (t.name == "a" and _MATCH_MP_HREF.search(t.get("href", "")))
    ):
        if tag.name == "td":
            in_can_do_section = bool(_MATCH_CAN_DO.search(tag.string or ""))
        elif in_can_do_section:
            count += 1

    return count
