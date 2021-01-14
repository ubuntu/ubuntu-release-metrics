#!/usr/bin/python3

# Copyright 2020 Canonical Ltd
from metrics.lib.basemetric import run_metric_main

run_metric_main("metrics.collectors.autopkgtest", "AutopkgtestMetrics")
