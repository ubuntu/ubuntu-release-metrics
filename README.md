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

## Existing collectors

* **Autopkgtest** (`metrics.collectors.autopkgtest`) — every 5m

  Queue sizes and running test counts from autopkgtest servers (production and staging), indexed by context, release, architecture, and instance.
  - `autopkgtest_queue_size`
  - `autopkgtest_running`

* **Britney** (`metrics.collectors.britney`) — every 5m

  Britney migration tool metrics: last run age, run duration, and update_excuses statistics.
  - `britney_last_run_age` — hours since last run
  - `britney_last_run_duration` — run duration in minutes
  - `update_excuses_stats` — valid candidates, not considered, total, median age, backlog
  - `update_excuses_by_team_stats` — count and average age of packages stuck >3 days, per team

* **Command Not Found** (`metrics.collectors.cnf`) — every 5m

  Command Not Found index age for each release, with an out-of-date flag when older than 1 day.
  - `command_not_found_age`

* **Contributors** (`metrics.collectors.contributors`) — every 1h

  Launchpad team member and participant counts for key Ubuntu teams (e.g. motu, ubuntu-core-dev, ubuntu-release, ubuntu-sru).
  - `launchpad_team_members`

* **Images** (`metrics.collectors.images`) — every 5m

  Daily Ubuntu image age and size, indexed by flavor, release, architecture, and image type.
  - `daily_image_details`

* **RLS Bugs** (`metrics.collectors.rls_bugs`) — every 1h

  Release bug tracking statistics split by incoming vs. tracking tags, indexed by team and release codename.
  - `distro_rls_bug_tasks`

* **Sponsoring** (`metrics.collectors.sponsoring`) — every 5m

  Sponsoring queue statistics: count, oldest age, and average age (in days), indexed by report type.
  - `sponsoring_queue_stats`

* **Ubuntu Archive** (`metrics.collectors.ubuntu_archive`) — every 1h

  Archive metrics for the development series, sourced from ubuntu-archive-team reports and Launchpad.
  - `nbs_stats` — Not Built from Source packages: removable and total counts
  - `uninst_stats` — uninstallable package counts per architecture
  - `outdate_stats` — outdated package counts per architecture
  - `priority_mismatch_stats` — priority mismatch package counts per architecture
  - `component_mismatch_stats` — component mismatch counts per pocket (`release`, `proposed`), action (`promotion`, `demotion`), and type (`source`, `binary`)
  - `ubuntu_archive_reviews` — review count for the ubuntu-archive team
  - `ubuntu_archive_bugs` — bug counts subscribed to and assigned to the ubuntu-archive team

* **Upload Queues** (`metrics.collectors.upload_queues`) — every 5m

  Package upload queue sizes by status and pocket, new queue splits by type, and queue ages.
  - `ubuntu_queue_size`
  - `ubuntu_new_queue_size`
  - `queue_ages` — oldest entry and 10-day backlog count

* **Versions** (`metrics.collectors.versions`) — every 1h

  Version statistics from desktop reports, including various categories and their counts for the devel series.
  - `versions_script_stats`

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
charmcraft upload ubuntu-release-metrics-collector_ubuntu@24.04-amd64.charm
charmcraft release ubuntu-release-metrics-collector --revision=$REVISION --channel=latest/edge
```

For production deployments, store the terraform config elsewhere, as it will contain secrets.

### Charmhub token

The CHARMCRAFT_TOKEN is what allows the CI to push the charm to charmhub. If it expires, you can refresh it with the following:

```
charmcraft login --export=secrets.auth --charm=ubuntu-release-metrics-collector  --permission=package-manage --permission=package-view --ttl=$((3600*24*365))
cat secrets.auth
```
