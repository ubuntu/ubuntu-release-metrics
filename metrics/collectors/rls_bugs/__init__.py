from metrics.collectors.rls_bugs.rls_bugs_collector import ReleaseBugsMetrics

RUN_INTERVAL = "1h"


def run_metric(*args, **kwargs):
    ReleaseBugsMetrics(*args, **kwargs).run()
