# Copyright 2020 Canonical Ltd

import json
import urllib.request
from collections import defaultdict

from distro_info import UbuntuDistroInfo as UDI
from metrics.lib.basemetric import Metric
from metrics.lib.ubunturelease import UbuntuRelease

INCOMING_URL_PATTERN = (
    "https://reqorts.qa.ubuntu.com/reports/rls-mgr/rls-{}-incoming.json"
)
TRACKING_URL_PATTERN = (
    "https://reqorts.qa.ubuntu.com/reports/rls-mgr/rls-{}-tracking.json"
)


class ReleaseBugsMetrics(Metric):
    def urls(self, pattern):
        # Releases < artful are rls-N-blah.json, releases >= artful are
        # rls-NN-blah.json
        artful = UbuntuRelease("artful")
        for release in [UbuntuRelease(r) for r in UDI().supported()]:
            if release < artful:
                n = 1
            else:
                n = 2
            yield (release.codename, pattern.format(release.codename[0] * n))

    def collect(self):
        # incoming/tracking -> team -> release -> n
        counts = {
            "incoming": defaultdict(lambda: defaultdict(int)),
            "tracking": defaultdict(lambda: defaultdict(int)),
        }
        data = []

        def fetch(urls, result_dict):
            for (codename, url) in urls:
                self.log.debug(f"Fetching {url}")
                with urllib.request.urlopen(url) as resp:
                    resp_json = json.load(resp)
                    for bug in resp_json["tasks"]:
                        teams_for_this_bug = set()
                        for task in resp_json["tasks"][bug]:
                            teams = task["team"]
                            if not teams:
                                continue
                            for team in teams:
                                if team in teams_for_this_bug:
                                    continue
                                teams_for_this_bug.add(team)
                                result_dict[team][codename] += 1

        fetch(self.urls(INCOMING_URL_PATTERN), counts["incoming"])
        fetch(self.urls(TRACKING_URL_PATTERN), counts["tracking"])

        self.log.debug("Finished fetching data")

        for tag in counts:
            for team in counts[tag]:
                for codename, count in counts[tag][team].items():
                    data.append(
                        {
                            "measurement": "distro_rls_bug_tasks",
                            "fields": {"count": count},
                            "tags": {
                                "tag": tag,
                                "release": codename,
                                "team_name": team,
                            },
                        }
                    )

        return data
