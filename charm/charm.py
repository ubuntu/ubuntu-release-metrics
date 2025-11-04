#!/usr/bin/env python3
# Copyright 2025 ssstr1pe
# See LICENSE file for licensing details.

"""Charm the release metrics."""

import ops
from releasemetrics import ReleaseMetrics


class ReleaseMetricsCharm(ops.CharmBase):
    """Charm the release metrics"""

    def __init__(self, *args):
        super().__init__(*args)
        self._release_metrics = ReleaseMetrics()

        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    def _on_start(self, event: ops.StartEvent):
        """Handle start event."""
        self.unit.status = ops.ActiveStatus()

    def _on_install(self, event: ops.InstallEvent):
        """Handle install event."""
        self.unit.status = ops.MaintenanceStatus(
            "installing ubuntu-release-metrics metric collectors"
        )
        try:
            self._release_metrics.install(self.config)
        except Exception as e:
            self.unit.status = ops.BlockedStatus(
                f"failed installing ubuntu-release-metrics: {e}"
            )
            return

        self.unit.status = ops.ActiveStatus("Ready")

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        self.unit.status = ops.MaintenanceStatus(
            "ubuntu-release-metrics charm configuration updated - updating unit"
        )
        self._release_metrics.configure(self.config)
        self.unit.status = ops.ActiveStatus("ready")
