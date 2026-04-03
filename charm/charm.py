#!/usr/bin/env python3
# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Charm the release metrics."""

import ops
from releasemetrics import ReleaseMetrics
from influxdb import InfluxDB
from grafana import Grafana


class UbuntuReleaseMetricsCharm(ops.CharmBase):
    """Charm the release metrics"""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self._influxdb = InfluxDB()
        self._grafana = Grafana()
        self._release_metrics = ReleaseMetrics()

        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    def _on_start(self, event: ops.StartEvent):
        """Handle start event."""
        self.unit.set_workload_version("0.0.1")
        self.unit.status = ops.ActiveStatus()

    def _on_install(self, event: ops.InstallEvent):
        """Handle install event."""
        self.unit.status = ops.MaintenanceStatus("installing ubuntu-release-metrics")
        try:
            self._influxdb.install()
        except Exception as e:
            self.unit.status = ops.BlockedStatus(f"failed installing influxdb: {e}")
            raise e
        try:
            self._grafana.install()
        except Exception as e:
            self.unit.status = ops.BlockedStatus(f"failed installing grafana: {e}")
            raise e
        try:
            self._release_metrics.install()
        except Exception as e:
            self.unit.status = ops.BlockedStatus(f"failed installing collector: {e}")
            raise e

        self.unit.status = ops.ActiveStatus("Ready")

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        self.unit.status = ops.MaintenanceStatus("rolling out configuration")

        influxdb_config = {}

        try:
            self._influxdb.configure(self.config)
            influxdb_config["influxdb_hostname"] = self._influxdb.influxdb_hostname
            influxdb_config["influxdb_port"] = self._influxdb.influxdb_port
            influxdb_config["influxdb_username"] = self._influxdb.influxdb_username
            influxdb_config["influxdb_password"] = self._influxdb.influxdb_password
            influxdb_config["influxdb_database"] = self._influxdb.influxdb_database
        except Exception as e:
            self.unit.status = ops.BlockedStatus(f"failed configuring influxdb: {e}")
            raise e

        try:
            self._grafana.configure(self.config)
        except Exception as e:
            self.unit.status = ops.BlockedStatus(f"failed configuring grafana: {e}")
            raise e

        try:
            self._release_metrics.configure({**self.config, **influxdb_config})
        except Exception as e:
            self.unit.status = ops.BlockedStatus(f"failed configuring collector: {e}")
            raise e

        self.unit.set_ports(self._influxdb.influxdb_port, self._grafana.grafana_port)
        self.unit.status = ops.ActiveStatus("ready")


if __name__ == "__main__":  # pragma: nocover
    ops.main(UbuntuReleaseMetricsCharm)
