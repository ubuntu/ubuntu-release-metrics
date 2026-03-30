from metrics.collectors.ubuntu_archive.ubuntu_archive_collector import (
    UbuntuArchiveMetrics,
)

RUN_INTERVAL = "1h"


def run_metric(*args, **kwargs):
    UbuntuArchiveMetrics(*args, **kwargs).run()
