# Copyright 2021 Canonical Ltd

import json
import re
import urllib.request

from metrics.lib.basemetric import Metric

SPONSORING_QUEUE_DIR = "http://reqorts.qa.ubuntu.com/reports/sponsoring/jsons/"


class SponsoringMetrics(Metric):
    def collect(self):
        """ Collect the sponsoring queue details"""
        data = []
        reports = []

        with urllib.request.urlopen(SPONSORING_QUEUE_DIR) as url:
            for index in url.read().decode("utf-8", errors="ignore").split("\n"):
                if ".json" in index:
                    r = re.compile(r'<a href="([\w.-]+)">')
                    reports.append(r.search(index).group(1))

        for report in reports:
            reporturl = "%s%s" % (SPONSORING_QUEUE_DIR, report)
            with urllib.request.urlopen(reporturl) as url:
                reportcontent = json.load(url)

                data.append(
                    {
                        "measurement": "sponsoring_queue_stats",
                        "fields": {"count": len(reportcontent)},
                        "tags": {"report": report.replace(".json", "")},
                    }
                )

        return data
