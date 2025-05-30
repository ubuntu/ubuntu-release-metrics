# Copyright 2020 Canonical Ltd

import tempfile

from launchpadlib.launchpad import Launchpad
from metrics.lib.basemetric import Metric


class UbuntuQueueMetrics(Metric):
    def __init__(self, dry_run=False, verbose=False):
        super().__init__(dry_run, verbose)

        self.launchpadlib_dir = tempfile.mkdtemp()
        self.temp_resources.append(self.launchpadlib_dir)

        self.lp = Launchpad.login_anonymously(
            "metrics",
            "production",
            launchpadlib_dir=self.launchpadlib_dir,
            version="devel",
        )
        self.ubuntu = self.lp.distributions["ubuntu"]
        self.active_series = {s.name: s for s in self.ubuntu.series if s.active}

    def _is_devel(self, series):
        return self.active_series[series] == self.ubuntu.current_series

    def collect_queue_sizes(self):
        """Get the number of UNAPPROVED/NEW uploads for proposed for each series."""
        measurements = []
        for series in self.active_series:
            for status in ("Unapproved", "New"):
                queue_size = len(
                    self.active_series[series].getPackageUploads(
                        status=status, pocket="Proposed"
                    )
                )
                measurements.append(
                    {
                        "measurement": "ubuntu_queue_size",
                        "fields": {"count": queue_size},
                        "tags": {
                            "devel": self._is_devel(series),
                            "status": status,
                            "release": series,
                        },
                    }
                )
        return measurements

    def queue_ages(self):
        """Determine age of UNAPPROVED/NEW uploads for proposed for each series."""
        from datetime import datetime

        measurement = []
        for series in self.active_series:
            for status in ("Unapproved", "New"):
                uploads = self.active_series[series].getPackageUploads(
                    status=status, pocket="Proposed"
                )
                oldest_age_in_days = 0
                backlog_count = 0
                today = datetime.today()
                for upload in uploads:
                    # the granularity only needs to be in days so tzinfo doesn't need
                    # to be accurate
                    age_in_days = (
                        today - upload.date_created.replace(tzinfo=None)
                    ).days
                    if age_in_days > oldest_age_in_days:
                        oldest_age_in_days = age_in_days
                    # items in the queue for > 10 days have gone through at least a
                    # weeks worth of reviewers and should be considered late
                    if age_in_days > 10:
                        backlog_count += 1

                measurement.append(
                    {
                        "measurement": "queue_ages",
                        "fields": {
                            "oldest_age_in_days": oldest_age_in_days,
                            "ten_day_backlog_count": backlog_count,
                        },
                        "tags": {
                            "devel": self._is_devel(series),
                            "release": series,
                            "status": status,
                        },
                    }
                )

        return measurement

    def collect(self):
        d1 = self.collect_queue_sizes()
        d2 = self.queue_ages()

        return d1 + d2
