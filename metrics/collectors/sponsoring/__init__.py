from metrics.collectors.sponsoring.sponsoring_collector import SponsoringMetrics


def run_metric(*args, **kwargs):
    SponsoringMetrics(*args, **kwargs).run()
