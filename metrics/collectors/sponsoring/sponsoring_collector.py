# Copyright 2021 Canonical Ltd

import datetime
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
        datenow = datetime.datetime.now()

        with urllib.request.urlopen(SPONSORING_QUEUE_DIR) as url:
            for index in url.read().decode("utf-8", errors="ignore").split("\n"):
                if ".json" in index:
                    r = re.compile(r'<a href="([\w.-]+)">')
                    reports.append(r.search(index).group(1))

        for report in reports:
            age_of_items = []
            reporturl = "%s%s" % (SPONSORING_QUEUE_DIR, report)
            with urllib.request.urlopen(reporturl) as url:
                reportcontent = json.load(url)

                for entry in reportcontent:
                    date_queue = datetime.datetime.strptime(
                        entry["date_queued"], "%m/%d/%y"
                    )
                    item_age = (datenow - date_queue).days
                    age_of_items.append(item_age)

                oldest = max(age_of_items)
                average_age = int(sum(age_of_items) / len(age_of_items))

                data.append(
                    {
                        "measurement": "sponsoring_queue_stats",
                        "fields": {
                            "count": len(reportcontent),
                            "oldest": oldest,
                            "average_age": average_age,
                        },
                        "tags": {"report": report.replace(".json", "")},
                    }
                )

        return data
