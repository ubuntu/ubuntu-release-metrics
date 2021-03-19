# Copyright 2021 Canonical Ltd

import importlib
import os
import pkgutil
import unittest

from metrics.lib.basemetric import Metric
from metrics.lib.errors import CollectorError


class TestCollector(unittest.TestCase):
    def test_dry_run(self):
        """Test each test runner in dry run mode. They will all most likely
        access the internet, so we may want to consider replacing this with
        mocks in future."""
        for (module_loader, name, ispkg) in pkgutil.iter_modules(
            [os.path.join("metrics", "collectors")], prefix="metrics.collectors."
        ):
            importlib.import_module(name, __package__)

        all_collectors = Metric.__subclasses__()

        for collector in all_collectors:
            with self.subTest(collector_name=collector.__name__):
                try:
                    collector(dry_run=True).run()
                except CollectorError as e:
                    self.fail(f"Metric errored: {e}")
