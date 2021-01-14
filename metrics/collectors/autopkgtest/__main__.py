#!/usr/bin/python3

# Copyright 2020 Canonical Ltd
import sys

from metrics.collectors.autopkgtest import run_metric
from metrics.lib.errors import CollectorError

try:
    run_metric()
except CollectorError:
    sys.exit(1)
