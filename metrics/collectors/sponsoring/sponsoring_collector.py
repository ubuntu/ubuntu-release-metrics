# Copyright 2021 Canonical Ltd

import json
import urllib.request

from metrics.lib.basemetric import Metric

SPONSORING_QUEUE_URL = "http://reqorts.qa.ubuntu.com/reports/sponsoring/sponsoring.json"


class SponsoringMetrics(Metric):
    def collect(self):
        """ Collect the sponsoring queue details"""
        data = []

        with urllib.request.urlopen(SPONSORING_QUEUE_URL) as url:
            report = json.load(url)

            data.append(
                {
                    "measurement": "sponsoring_queue_stats",
                    "fields": {"count": len(report)},
                    "tags": {"report": "ubuntu"},
                }
            )

        return data
