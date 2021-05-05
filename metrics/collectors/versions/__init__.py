from metrics.collectors.versions.versions_collector import VersionsMetrics

RUN_INTERVAL = "1h"


def run_metric():
    VersionsMetrics().run()
