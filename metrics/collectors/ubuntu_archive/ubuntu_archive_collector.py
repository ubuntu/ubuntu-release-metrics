# Copyright 2026 Canonical Ltd

import tempfile

import requests
import time

from datetime import datetime, timezone
from launchpadlib.launchpad import Launchpad
from metrics.lib.basemetric import Metric

NBS_CSV_URL = "https://ubuntu-archive-team.ubuntu.com/nbs.csv"


class UbuntuArchiveMetrics(Metric):
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
        self.dev_series = self.ubuntu.current_series.name

    def get_nbs_stats(self):
        data = []
        self.log.debug("Getting NBS stats for " + self.dev_series)
        self.log.debug("Downloading tail of NBS CSV...")

        try:
            # 2KB is a safe buffer for text to ensure 12h of records
            headers = {"Range": "bytes=-2048"}
            response = requests.get(NBS_CSV_URL, headers=headers, timeout=60)

            # we expect 200 or 206 for a Range request; anything else is a problem
            response.raise_for_status()

            self.log.debug("Parsing NBS CSV fragment...")
            lines = response.text.strip().splitlines()

            status_code = response.status_code
            if status_code == 206:
                # The first line of a partial Range response is almost always
                # a partial fragment. We discard it to avoid ValueErrors.
                if len(lines) > 1:
                    lines = lines[1:]
            elif status_code == 200:
                # Server ignored the Range header and returned the full file.
                # Keep all lines, including the first one.
                self.log.debug("Received full NBS CSV (status 200); keeping all lines.")
            else:
                # Unexpected 2xx status for a Range request.
                self.log.warning(
                    "Unexpected status code %s when requesting NBS CSV", status_code
                )
                return []

            now_ms = int(time.time() * 1000)
            cutoff = now_ms - (12 * 60 * 60 * 1000)  # 12h safety period

            for line in lines:
                parts = line.split(",")
                if len(parts) != 3:
                    continue

                try:
                    ts = int(parts[0])
                    if ts > cutoff:
                        # Convert ms to datetime for InfluxDB precision
                        data.append(
                            {
                                "measurement": "nbs_stats",
                                "tags": {"release": self.dev_series},
                                "time": datetime.fromtimestamp(
                                    ts / 1000.0, tz=timezone.utc
                                ),
                                "fields": {
                                    "removable": int(parts[1]),
                                    "total": int(parts[2]),
                                },
                            }
                        )
                except ValueError as exc:
                    self.log.debug("Skipping line due to parse error: %s", exc)
                    continue
        except requests.exceptions.RequestException as exc:
            self.log.warning("Failed to download or parse NBS CSV: %s", exc)
            return []

        return data

    def collect(self):
        nbs = self.get_nbs_stats()
        return nbs
