from metrics.collectors.upload_queues.upload_queue_collector import UbuntuQueueMetrics


def run_metric(*args, **kwargs):
    UbuntuQueueMetrics(*args, **kwargs).run()
