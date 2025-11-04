# Copyright 2021 Canonical Ltd
# pylint: disable=C0103,E0401
"""
Collects metrics for command not found indexes
"""

import datetime
import tempfile
import urllib

from launchpadlib.launchpad import Launchpad

from metrics.lib.basemetric import Metric

URL = "http://archive.ubuntu.com/ubuntu/dists/release/main/cnf/"


class CommandNotFoundMetric(Metric):
    """
    Collects metrics for command not found indexes
    """

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
        self.date_now = datetime.datetime.now()

    def get_cnf_ages_in_days(self):
        """
        metrics collecting function
        """
        data = []
        for s in self.active_series:
            url = URL.replace("release", s)
            count = None
            try:
                with urllib.request.urlopen(url) as fp:
                    bytes_resp = fp.read()
                op_str = bytes_resp.decode("utf-8")
                for line in op_str.splitlines():
                    if "Commands" in line:
                        # flake8: noqa: E203
                        date_str = line[
                            line.find('<td align="right">')
                            + len('<td align="right">') :
                        ]
                        date_str = date_str[
                            : date_str.find('</td><td align="right">')
                        ].rstrip()
                        datetime_object = datetime.datetime.strptime(
                            date_str, "%Y-%m-%d %H:%M"
                        )
                        age = self.date_now - datetime_object
                        count = age.total_seconds() / 86400
            except urllib.error.HTTPError:
                count = None
                continue
            data.append(
                {
                    "measurement": "command_not_found_age",
                    "fields": {
                        "cnf_age": count,
                        "out_of_date": (count > 1),
                    },
                    "tags": {"release": s},
                }
            )
        return data

    def collect(self):
        """Collect the cnf details"""
        return self.get_cnf_ages_in_days()
