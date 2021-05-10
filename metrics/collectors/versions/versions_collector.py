# Copyright 2021 Canonical Ltd

import datetime
import urllib.parse
import urllib.request

from metrics.lib.basemetric import Metric

VERSIONS_STATS_URL = "https://people.canonical.com/~platform/desktop/versions/stats/%s/"
VERSIONS_STATS_TODAY = VERSIONS_STATS_URL % datetime.datetime.now().strftime("%Y-%m-%d")


class VersionsMetrics(Metric):
    def collect(self):
        """ Collect the sponsoring queue details"""
        data = []

        known_reports_lst = []
        with urllib.request.urlopen(
            urllib.parse.urljoin(VERSIONS_STATS_TODAY, "reports")
        ) as reports:
            for report in reports:
                report = report.decode("utf-8", errors="ignore").strip()
                if report:
                    known_reports_lst.append(report)

        for report in known_reports_lst:
            with urllib.request.urlopen(
                urllib.parse.urljoin(VERSIONS_STATS_TODAY, report)
            ) as stats:
                for category in stats:
                    category = category.decode("utf-8", errors="ignore").strip()
                    if not category:
                        continue
                    category, value = category.split("=")
                    data.append(
                        {
                            "measurement": "versions_script_stats",
                            "fields": {"count": value},
                            "tags": {
                                "report": report,
                                "category": category,
                                "series": "devel",
                            },
                        }
                    )

        return data