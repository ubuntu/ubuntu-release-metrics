# Copyright 2026 Canonical Ltd

import tempfile

from launchpadlib.launchpad import Launchpad
from metrics.lib.basemetric import Metric

TEAMS = [
    "motu",
    "ubuntumembers",
    "ubuntu-archive",
    "ubuntu-core-dev",
    "ubuntu-dev",
    "ubuntu-developer-members",
    "ubuntu-release",
    "ubuntu-sru",
    "ubuntu-sru-developers",
    "ubuntu-uploaders",
]


class ContributorsMetrics(Metric):
    def __init__(self, dry_run=False, verbose=False):
        super().__init__(dry_run, verbose)

        self.lp = Launchpad.login_anonymously(
            "metrics",
            "production",
            launchpadlib_dir=tempfile.mkdtemp(),
            version="devel",
        )
        self.ubuntu = self.lp.distributions["ubuntu"]
        self.active_series = {s.name: s for s in self.ubuntu.series if s.active}

    def collect(self):
        data_points = []

        for team_name in TEAMS:
            try:
                self.log.debug(f"Fetching member count for Launchpad team: {team_name}")
                team = self.lp.people[team_name]
                member_count = len(team.members)
                participants_count = len(team.participants)
                self.log.debug(
                    f"Team {team_name} has {member_count} members and {participants_count} participants."
                )

                data_points.append(
                    {
                        "measurement": "launchpad_team_members",
                        "tags": {"team": team_name, "count_type": "members"},
                        "fields": {"count": member_count},
                    }
                )
                data_points.append(
                    {
                        "measurement": "launchpad_team_members",
                        "tags": {"team": team_name, "count_type": "participants"},
                        "fields": {"count": participants_count},
                    }
                )
            except Exception as e:
                self.log.warning(
                    f"Failed to fetch data for Launchpad team '{team_name}': {e}"
                )
                continue

        return data_points
