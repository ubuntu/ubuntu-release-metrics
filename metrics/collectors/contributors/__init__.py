from metrics.collectors.contributors.contributors_collector import ContributorsMetrics

RUN_INTERVAL = "1h"


def run_metric(*args, **kwargs):
    ContributorsMetrics(*args, **kwargs).run()
