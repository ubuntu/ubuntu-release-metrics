# Copyright 2021 Canonical Ltd

import datetime
import json
import urllib.request

from metrics.lib.basemetric import Metric

SPONSORING_QUEUE_URL = "http://reqorts.qa.ubuntu.com/reports/sponsoring/sponsoring.json"


class SponsoringMetrics(Metric):
    def collect(self):
        """ Collect the sponsoring queue details"""
        data = []
        set_age_items = {}
        datenow = datetime.datetime.now()

        with urllib.request.urlopen(SPONSORING_QUEUE_URL) as url:
            report = json.load(url)
            set_age_items["sponsoring"] = []
            for entry in report:
                date_queue = datetime.datetime.strptime(
                    entry["date_queued"], "%m/%d/%y"
                )
                item_age = (datenow - date_queue).days

                for set in entry["sets"]:
                    if set not in set_age_items:
                        set_age_items[set] = []
                    set_age_items[set].append(item_age)
                set_age_items["sponsoring"].append(item_age)

        for report in set_age_items:
            items = set_age_items[report]
            oldest = max(items)
            average_age = int(sum(items) / len(items))

            data.append(
                {
                    "measurement": "sponsoring_queue_stats",
                    "fields": {
                        "count": len(items),
                        "oldest": oldest,
                        "average_age": average_age,
                    },
                    "tags": {"report": report},
                }
            )

        return data
