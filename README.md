# Introduction

The Ubuntu project has an [instance of
Grafana](https://ubuntu-release.kpi.ubuntu.com/) which is a place for Ubuntu
teams to track their metrics.

This repository hosts the scripts which collect data and push it to the
Influxdb database that the Grafana reads from.

# Architecture

There are three branches in this repository:

  * ` metrics`. The default branch which contains the scripts themselves. These will be run periodically.
  * `charm`. This branch contains the Juju charm to deploy an instance which
  checks out `metrics` and arranges for them to be run regularly.
  * `mojo`. This is [a delivery system for Juju
  charms](https://mojo.canonical.com/). Most people won't need to touch this,
  but the Mojo spec is run on a "controller" host to arrange to collect
  secrets - the InfluxDB credentials - and deploy the charm.

# Writing a collector script

Collector scripts are Python scripts. The simplest way to write a script is
to `import metrics.basemetric` and write a class which inherits from `Metric`
in there. Provide a `collect` function which returns data points suitable for
passing to
[InfluxDBClient.write_points()](https://influxdb-python.readthedocs.io/en/latest/api-documentation.html#influxdb.InfluxDBClient.write_points),
instansiate an object of your class and call `run()` on it. `Metric` will
take care of submitting to Influx for you. For development, you can pass
`--dry-run` to see what would be submitted. Make use of `self.log` to log
progress. With `--verbose`, debug messages will be logged.