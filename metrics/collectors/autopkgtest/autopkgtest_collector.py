# Copyright 2020 Canonical Ltd

import json
import urllib.request
import sys

from collections import defaultdict
from distro_info import UbuntuDistroInfo as UDI
from metrics.lib.basemetric import Metric
from metrics.lib.ubunturelease import UbuntuRelease

QUEUE_SIZE_URL = "https://autopkgtest.ubuntu.com/queue_size.json"
RUNNING_URL = "https://autopkgtest.ubuntu.com/static/running.json"


class AutopkgtestMetrics(Metric):
    def fetch(self, url):
        with urllib.request.urlopen(url) as resp:
            return json.load(resp)

    def collect_queue_sizes(self):
        data = []
        queue_sizes = self.fetch(QUEUE_SIZE_URL)
        for context in queue_sizes:
            for release in queue_sizes[context]:
                for arch, count in queue_sizes[context][release].items():
                    data.append(
                        {
                            "measurement": "autopkgtest_queue_size",
                            "fields": {"count": count},
                            "tags": {
                                "context": context,
                                "release": release,
                                "arch": arch,
                            },
                        }
                    )
        return data

    def collect_running(self):
        data = []
        running = self.fetch(RUNNING_URL)
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
                        "tags": {"release": release, "arch": arch},
                    }
                )

        return data

    def collect(self):
        d1 = self.collect_queue_sizes()
        d2 = self.collect_running()

        return d1 + d2
