from metrics.collectors.britney.britney_collector import BritneyMetrics


def run_metric(*args, **kwargs):
    BritneyMetrics(*args, **kwargs).run()
