# Copyright 2021 Canonical Ltd

import datetime
import urllib.request

from metrics.lib.basemetric import Metric

VERSIONS_STATS_URL = (
    "https://people.canonical.com/~platform/desktop/stats/%s/"
    % datetime.datetime.now().strftime("%Y-%m-%d")
)


class VersionsMetrics(Metric):
    def collect(self):
        """ Collect the sponsoring queue details"""
        data = []

        known_reports_lst = []
        with urllib.request.urlopen(VERSIONS_STATS_URL + "reports") as reports:
            for report in reports.read().decode("utf-8", errors="ignore").split("\n"):
                if report:
                    known_reports_lst.append(report)

        for report in known_reports_lst:
            with urllib.request.urlopen(VERSIONS_STATS_URL + report) as stats:
                for category in (
                    stats.read().decode("utf-8", errors="ignore").split("\n")
                ):
                    if not category:
                        continue
                    category, value = category.split("=")
                    data.append(
                        {
                            "measurement": "versions_script_stats",
                            "fields": {"count": value},
                            "tags": {"report": report, "category": category},
                        }
                    )

        return data
