# Introduction

The Ubuntu project has an [instance of
Grafana](https://ubuntu-release.kpi.ubuntu.com/) which is a place for Ubuntu
teams to track their metrics.

This repository hosts the scripts which collect data and push it to the
Influxdb database that the Grafana reads from.

# Architecture

There are three branches in this repository:

  * ` metrics`. The default branch which contains the scripts themselves. These
    will be run periodically.
  * `charm`. This branch contains the Juju charm to deploy an instance which
  checks out `metrics` and arranges for them to be run regularly.
  * `mojo`. This is [a delivery system for Juju
  charms](https://mojo.canonical.com/). Most people won't need to touch this,
  but the Mojo spec is run on a "controller" host to arrange to collect
  secrets - the InfluxDB credentials - and deploy the charm.

# Writing a collector

Collectors are python modules in the `metrics.collectors` namespace which
expose a `run_metric()` function.

The simplest way to write a collector is to `import metrics.lib.basemetric`
and write a class which inherits from `Metric` in there. Provide a `collect`
function which returns data points suitable for passing to
[InfluxDBClient.write_points()](https://influxdb-python.readthedocs.io/en/latest/api-documentation.html#influxdb.InfluxDBClient.write_points).
`Metric` will take care of submitting to Influx for you when you invoke
`run()`, which your `run_metric()` top level function should do. For
development, when invoked as a script (by providing a `__main__.py` file),
you can pass `--dry-run` to see what would be submitted. Make use of
`self.log` to log progress. With `--verbose`, debug messages will be logged.

Raise a `metrics.lib.errors.CollectorError` on error, and the message will be
reported along with the failure.

If you make your collector run when executed too (`python3 -m
metrics.collectors.your_collector`), you can provide a symlink in `bin/` so
that it's easier for people to run for testing purposes.

But when starting a new metric, just copy the structure of an existing script!

# Controlling how often metrics are collected

The charm will handle arranging for each metric to be run periodically, but
you can control how frequently this happens. Provide a top level variable in
your `__init__.py` called `RUN_INTERVAL` with a value [suitable for passing
to `OnUnitInactiveSec` in a systemd timer
unit](https://www.freedesktop.org/software/systemd/man/systemd.timer.html).
The default value if you don't specify this is `5m`.