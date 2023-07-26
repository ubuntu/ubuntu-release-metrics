from metrics.collectors.cnf.command_not_found import CommandNotFoundMetric


def run_metric(*args, **kwargs):
    CommandNotFoundMetric(*args, **kwargs).run()
