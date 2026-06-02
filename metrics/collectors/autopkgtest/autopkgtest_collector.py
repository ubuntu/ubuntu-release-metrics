# Copyright 2020 Canonical Ltd

import json
import urllib.request
from collections import defaultdict

from metrics.lib.basemetric import Metric

QUEUE_URL = {
    "production": "https://autopkgtest.ubuntu.com/queues.json",
    "staging": "https://autopkgtest.staging.ubuntu.com/queues.json",
}

RUNNING_URL = {
    "production": "https://autopkgtest.ubuntu.com/static/running.json",
    "staging": "https://autopkgtest.staging.ubuntu.com/static/running.json",
}


class AutopkgtestMetrics(Metric):
    def fetch(self, url):
        try:
            with urllib.request.urlopen(url) as resp:
                return json.load(resp)
        except urllib.error.URLError:
            return []

    def collect_queue_sizes(self):
        data = []
        for instance in ("production", "staging"):
            queues = self.fetch(QUEUE_URL[instance])
            if not queues:
                continue
            for queue in queues:
                for release in queues[queue]:
                    for arch, items in queues[queue][release].items():
                        data.append(
                            {
                                "measurement": "autopkgtest_queue_size",
                                "fields": {"count": len(items)},
                                "tags": {
                                    "context": queue,
                                    "release": release,
                                    "arch": arch,
                                    "instance": instance,
                                },
                            }
                        )
        return data

    def collect_running(self):
        data = []
        for instance in ("production", "staging"):
            running = self.fetch(RUNNING_URL[instance])
            counts = defaultdict(lambda: defaultdict(int))

            for pkg in running:
                for params in running[pkg]:
                    for release in running[pkg][params]:
                        for arch in running[pkg][params][release]:
                            counts[release][arch] += 1

            for release in counts:
                for arch, count in counts[release].items():
                    data.append(
                        {
                            "measurement": "autopkgtest_running",
                            "fields": {"count": count},
                            "tags": {
                                "release": release,
                                "arch": arch,
                                "instance": instance,
                            },
                        }
                    )

            return data

    def collect(self):
        d1 = self.collect_queue_sizes()
        d2 = self.collect_running()

        return d1 + d2
