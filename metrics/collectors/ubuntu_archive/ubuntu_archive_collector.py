# Copyright 2026 Canonical Ltd

import re
import tempfile

import requests
import time

from datetime import datetime, timezone
from launchpadlib.launchpad import Launchpad
from metrics.lib.basemetric import Metric

NBS_CSV_URL = "https://ubuntu-archive-team.ubuntu.com/nbs.csv"
PROPOSED_MIGRATION_URL = "https://ubuntu-archive-team.ubuntu.com/proposed-migration/"
PRIORITY_MISMATCHES_URL = (
    "https://ubuntu-archive-team.ubuntu.com/priority-mismatches.txt"
)


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
        self.architectures = [
            arch.architecture_tag for arch in self.ubuntu.current_series.architectures
        ]

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

    def _get_byarch_report_stats(self, url, measurement):
        data = []
        self.log.debug("Downloading %s report from %s", measurement, url)

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            self.log.warning("Failed to download %s report: %s", measurement, exc)
            return []

        text = response.text

        # Parse the "* summary" section
        summary_match = re.search(
            r"\* summary\n(.*?)(?=\n# Generated:)", text, re.DOTALL
        )
        if not summary_match:
            self.log.warning("Could not find summary section in %s report", measurement)
            return []

        # Parse the generated timestamp
        generated_match = re.search(r"# Generated:\s+(.+)", text)
        if not generated_match:
            self.log.warning(
                "Could not find generated timestamp in %s report", measurement
            )
            return []

        try:
            generated_time = datetime.strptime(
                generated_match.group(1).strip(), "%a, %d %b %Y %H:%M:%S %z"
            )
        except ValueError as exc:
            self.log.warning("Failed to parse generated timestamp: %s", exc)
            return []

        counts_by_arch = {arch: 0 for arch in self.architectures}
        for line in summary_match.group(1).splitlines():
            m = re.match(r"^\s*(\d+)\s+(\S+)\s*$", line)
            if m:
                count, arch = int(m.group(1)), m.group(2)
                counts_by_arch[arch] = count

        for arch, count in counts_by_arch.items():
            data.append(
                {
                    "measurement": measurement,
                    "tags": {"release": self.dev_series, "arch": arch},
                    "time": generated_time,
                    "fields": {"count": count},
                }
            )
        return data

    def get_uninst_stats(self):
        url = PROPOSED_MIGRATION_URL + f"{self.dev_series}_uninst.txt"
        return self._get_byarch_report_stats(url, "uninst_stats")

    def get_outdate_stats(self):
        url = PROPOSED_MIGRATION_URL + f"{self.dev_series}_outdate.txt"
        return self._get_byarch_report_stats(url, "outdate_stats")

    def get_priority_mismatch_stats(self):
        data = []
        self.log.debug("Downloading priority mismatches report")

        try:
            response = requests.get(PRIORITY_MISMATCHES_URL, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            self.log.warning("Failed to download priority mismatches report: %s", exc)
            return []

        text = response.text

        # Parse the generated timestamp
        generated_match = re.search(r"Generated:\s+(.+)", text)
        if not generated_match:
            self.log.warning(
                "Could not find generated timestamp in priority mismatches report"
            )
            return []

        try:
            ts_str = generated_match.group(1).strip().replace(" GMT ", " ")
            generated_time = datetime.strptime(ts_str, "%a %b %d %H:%M:%S %Y").replace(
                tzinfo=timezone.utc
            )
        except ValueError as exc:
            self.log.warning("Failed to parse generated timestamp: %s", exc)
            return []

        counts_by_arch = {arch: 0 for arch in self.architectures}
        lines = text.splitlines()
        arch = None

        for i, line in enumerate(lines):
            if not line or line.startswith("Generated:"):
                continue
            # Architecture section header: name line followed by '====' underline
            if i + 1 < len(lines) and lines[i + 1].startswith("===="):
                arch = line
                continue
            # Separator lines
            if line.startswith("====") or line.startswith("----"):
                continue
            # Subsection header lines always contain spaces; package names never do
            if " " in line:
                continue
            # Last word of a multi-line subsection header is followed by '----'
            if i + 1 < len(lines) and lines[i + 1].startswith("----"):
                continue
            # Remaining lines are package names
            if arch and arch in counts_by_arch:
                counts_by_arch[arch] += 1

        for arch, count in counts_by_arch.items():
            data.append(
                {
                    "measurement": "priority_mismatch_stats",
                    "tags": {"release": self.dev_series, "arch": arch},
                    "time": generated_time,
                    "fields": {"count": count},
                }
            )
        return data

    def get_bug_stats(self):
        data = []
        self.log.debug("Getting bug stats for ubuntu-archive team")
        try:
            archive_team = self.lp.people["ubuntu-archive"]
        except Exception as exc:
            self.log.warning("Failed to fetch Launchpad team 'ubuntu-archive': %s", exc)
            return data

        try:
            subscribed_bugs = archive_team.searchTasks(bug_subscriber=archive_team)
            data.append(
                {
                    "measurement": "ubuntu_archive_bugs",
                    "tags": {"type": "subscribed"},
                    "fields": {"count": len(subscribed_bugs)},
                }
            )
        except Exception as exc:
            self.log.warning(
                "Failed to fetch subscribed bug stats from Launchpad: %s", exc
            )

        try:
            assigned_bugs = archive_team.searchTasks(assignee=archive_team)
            data.append(
                {
                    "measurement": "ubuntu_archive_bugs",
                    "tags": {"type": "assigned"},
                    "fields": {"count": len(assigned_bugs)},
                }
            )
        except Exception as exc:
            self.log.warning(
                "Failed to fetch assigned bug stats from Launchpad: %s", exc
            )

        return data

    def collect(self):
        nbs = self.get_nbs_stats()
        uninst = self.get_uninst_stats()
        outdate = self.get_outdate_stats()
        priority_mismatches = self.get_priority_mismatch_stats()
        bugs = self.get_bug_stats()
        return nbs + uninst + outdate + priority_mismatches + bugs
