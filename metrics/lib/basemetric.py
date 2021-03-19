# Copyright 2020 Canonical Ltd

import argparse
import logging
import os
import sys

from influxdb import InfluxDBClient
from metrics.lib.errors import CollectorError


def run_metric_main(module, cls):
    from importlib import import_module

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Do not act but print what would be submitted",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Be more verbose")

    args = parser.parse_args()

    cls = getattr(import_module(module), cls)
    try:
        cls(dry_run=args.dry_run, verbose=args.verbose).run()
    except CollectorError:
        sys.exit(1)


class Metric:
    def __init__(self, dry_run=False, verbose=False):
        self.dry_run = dry_run
        self.verbose = verbose

        self.log = logging.getLogger(__name__)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        ch.setFormatter(formatter)
        self.log.addHandler(ch)

        self.log.setLevel(logging.INFO)

        if self.verbose:
            self.log.setLevel(logging.DEBUG)

        if not self.dry_run:
            try:
                hostname = os.environ["INFLUXDB_HOSTNAME"]
                port = os.environ["INFLUXDB_PORT"]
                username = os.environ["INFLUXDB_USERNAME"]
                password = os.environ["INFLUXDB_PASSWORD"]
                database = os.environ["INFLUXDB_DATABASE"]
            except KeyError as e:
                self.log.error(f"Make sure {e} is set in the environment.")
                raise CollectorError(f"Variable {e} not set") from e

            self.log.debug(f"Connecting to influxdb at {hostname}:{port}...")

            self.influx_client = InfluxDBClient(
                hostname, port, username, password, database
            )
        else:
            self.log.info("Running in dry-run mode.")

    def collect(self):
        raise NotImplementedError

    def run(self):
        data = self.collect()

        if self.dry_run:
            import pprint

            self.log.info(f"[dry-run] Would submit: {pprint.pformat(data)}")
        else:
            self.influx_client.write_points(data)
