# Ubuntu community metrics

## Introduction

The Ubuntu project has an [instance of
Grafana](https://ubuntu-release.kpi.ubuntu.com/) which is a place for Ubuntu
teams to track their metrics.

This repository hosts the scripts which collect data and push it to the
Influxdb database that the Grafana reads from.

## Architecture

- `bin`: contains wrapper scripts to help run collectors in dry-run mode
- `charm`: contains all charm code
- `metrics`: contains the actual metric collector scripts
- `terraform`: includes a terraform module for the release metrics as well as a local deployment configuration to test the terraform module - please note that the local terraform config pulls the charm from charmhub, not from a locally built charm
- `tests`: unit tests for the metric collector scripts
- `utils`: contains a wrapper script called `exec-metric` used by the executables in `bin`

## Writing a collector

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

The `metrics` branch is auto pulled, so after merging your new collector will
be run automatically.

## Controlling how often metrics are collected

The charm will handle arranging for each metric to be run periodically, but
you can control how frequently this happens. Provide a top level variable in
your `__init__.py` called `RUN_INTERVAL` with a value [suitable for passing
to `OnUnitInactiveSec` in a systemd timer
unit](https://www.freedesktop.org/software/systemd/man/systemd.timer.html).
The default value if you don't specify this is `5m`.

## Deploying the charm

The charm is built, packed and deployed to Charmhub via Github actions on pushes
to the `main` branch. To build locally, run `snap install charmcraft` and
run `charmcraft pack`. You can test a locally built charm either by running
`juju deploy ./my-charm-file.charm`, or by uploading the charm to Charmhub, on
a suitable track (`latest/edge`), and then using the terraform local config to deploy it.

To do so, run:
```
charmcraft clean
charmcraft pack
charmcraft upload ubuntu-release-metrics_ubuntu@24.04-amd64.charm --name ubuntu-release-metrics-collector
charmcraft release ubuntu-release-metrics-collector --revision=$REVISION --channel=latest/edge
```

For production deployments, store the terraform config elsewhere, as it will contain secrets.
