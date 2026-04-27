# Copyright 2026 Canonical Ltd

import re
import tempfile

import requests
import time

from datetime import datetime, timezone
from launchpadlib.launchpad import Launchpad
from metrics.lib.basemetric import Metric
from metrics.lib.lp_scrape_mps import count_team_reviews

NBS_CSV_URL = "https://ubuntu-archive-team.ubuntu.com/nbs.csv"
COMPONENT_MISMATCHES_CSV_URLS = {
    "release": "https://ubuntu-archive-team.ubuntu.com/component-mismatches.csv",
    "proposed": "https://ubuntu-archive-team.ubuntu.com/component-mismatches-proposed.csv",
}
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

    def _fetch_recent_csv_lines(self, url, buffer_size=2048):
        """Fetch the tail of a CSV via a Range request and return parsed lines.

        For a 206 partial response the first line is discarded as it is likely
        a fragment.  For a 200 full response all lines are kept.  Returns an
        empty list on network or unexpected-status errors.
        """
        try:
            headers = {"Range": f"bytes=-{buffer_size}"}
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            self.log.warning("Failed to download CSV from %s: %s", url, exc)
            return []

        lines = response.text.strip().splitlines()
        status_code = response.status_code

        if status_code == 206:
            # The first line of a partial response is almost always a fragment.
            if len(lines) > 1:
                lines = lines[1:]
        elif status_code == 200:
            # Server ignored the Range header; keep all lines.
            self.log.debug("Received full CSV from %s (status 200)", url)
        else:
            self.log.warning(
                "Unexpected status code %s when requesting CSV from %s",
                status_code,
                url,
            )
            return []

        return lines

    def get_nbs_stats(self):
        data = []
        self.log.debug("Getting NBS stats for %s", self.dev_series)

        lines = self._fetch_recent_csv_lines(NBS_CSV_URL)
        if not lines:
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

        return data

    def get_component_mismatch_stats(self):
        data = []
        now_ms = int(time.time() * 1000)
        cutoff = now_ms - (12 * 60 * 60 * 1000)  # 12h safety period

        # Columns: time, source promotions, binary promotions,
        #          source demotions, binary demotions
        column_tags = [
            {"action": "promotion", "type": "source"},
            {"action": "promotion", "type": "binary"},
            {"action": "demotion", "type": "source"},
            {"action": "demotion", "type": "binary"},
        ]

        for pocket, url in COMPONENT_MISMATCHES_CSV_URLS.items():
            self.log.debug(
                "Getting component mismatch stats for %s (pocket: %s)",
                self.dev_series,
                pocket,
            )
            lines = self._fetch_recent_csv_lines(url)

            for line in lines:
                parts = line.split(",")
                if len(parts) != 5:
                    continue
                try:
                    ts = int(parts[0])
                    if ts <= cutoff:
                        continue
                    timestamp = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                    for i, tags in enumerate(column_tags):
                        data.append(
                            {
                                "measurement": "component_mismatch_stats",
                                "tags": {
                                    "release": self.dev_series,
                                    "pocket": pocket,
                                    **tags,
                                },
                                "time": timestamp,
                                "fields": {"count": int(parts[i + 1])},
                            }
                        )
                except ValueError as exc:
                    self.log.debug("Skipping line due to parse error: %s", exc)
                    continue

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

    def get_review_stats(self):
        data = []
        self.log.debug("Getting review stats for ubuntu-archive team")
        try:
            count = count_team_reviews("ubuntu-archive")
            data.append(
                {
                    "measurement": "ubuntu_archive_reviews",
                    "fields": {"count": count},
                }
            )
        except Exception as exc:
            self.log.warning("Failed to fetch review stats for ubuntu-archive: %s", exc)
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
        component_mismatches = self.get_component_mismatch_stats()
        reviews = self.get_review_stats()
        bugs = self.get_bug_stats()
        return (
            nbs
            + uninst
            + outdate
            + priority_mismatches
            + component_mismatches
            + reviews
            + bugs
        )
