from metrics.collectors.images.images_collector import ImagesMetrics


def run_metric(*args, **kwargs):
    ImagesMetrics(*args, **kwargs).run()
