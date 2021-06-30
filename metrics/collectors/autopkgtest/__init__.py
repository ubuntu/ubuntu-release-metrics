from metrics.collectors.autopkgtest.autopkgtest_collector import AutopkgtestMetrics


def run_metric(*args, **kwargs):
    AutopkgtestMetrics(*args, **kwargs).run()
