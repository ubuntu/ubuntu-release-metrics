#!/usr/bin/env python3
# Copyright 2020 Canonical Ltd
# See LICENSE file for licensing details.

import logging
import os
import subprocess
from textwrap import dedent

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = "/srv/influx.conf"
DRY_RUN_FILE = "/srv/dry-run.conf"
ENVIRONMENT_FILE = "/etc/environment.d/proxy.conf"
METRICS_REPO = "https://github.com/ubuntu/ubuntu-release-metrics.git"
PACKAGES_TO_INSTALL = ["git", "python3-influxdb", "python3-launchpadlib"]


class UbuntuReleaseMetricsCollectorCharm(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self.http_proxy = self.model.config.get("http-proxy")
        self.https_proxy = self.model.config.get("https-proxy")
        self.no_proxy = self.model.config.get("no-proxy")

        self.subprocess_env = os.environ.copy()
        self.subprocess_env["http_proxy"] = self.http_proxy
        self.subprocess_env["https_proxy"] = self.https_proxy
        self.subprocess_env["no_proxy"] = self.no_proxy

        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self._stored.set_default(installed_packages=set(), repo_cloned=False)

    def _install_packages(self, packages):
        packages = packages - self._stored.installed_packages
        if not packages:
            logger.info("No packages to install.")
            return
        logger.info(f"Installing apt package(s) {', '.join(packages)}")
        subprocess.check_call(
            [
                "apt-get",
                "--assume-yes",
                "--option=Dpkg::Options::=--force-confold",
                "install",
            ]
            + list(packages),
            env=self.subprocess_env,
        )
        self._stored.installed_packages |= packages

    def _clone_metrics_repo(self):
        if self._stored.repo_cloned:
            return

        logger.info(f"Cloning {METRICS_REPO}")
        subprocess.check_call(
            [
                "git",
                "clone",
                METRICS_REPO,
                os.path.expanduser("/srv/ubuntu-release-metrics/"),
            ],
            env=self.subprocess_env,
        )
        self._stored.repo_cloned = True

    def _ensure_set_up(self):
        self._install_packages(set(PACKAGES_TO_INSTALL))
        self._clone_metrics_repo()
        unit_dir = "/etc/systemd/system"
        for unit in (
            "daemon-reload.service",
            "daemon-reload.timer",
            "pull-metrics.service",
            "pull-metrics.timer",
            "run-metric-collector@.service",
            "start-all-timers.service",
            "start-all-timers.timer",
        ):
            dest = os.path.join(unit_dir, unit)
            if not os.path.exists(dest):
                logger.info(f"Installing {dest}")
                os.symlink(os.path.join(self.charm_dir, "data", unit), dest)

        os.makedirs(
            "/etc/systemd/system-generators/", mode=0o755, exist_ok=True
        )
        if not os.path.exists(
            "/etc/systemd/system-generators/metrics-unit-generator"
        ):
            os.symlink(
                os.path.join(
                    self.charm_dir, "scripts", "metrics-unit-generator"
                ),
                "/etc/systemd/system-generators/metrics-unit-generator",
            )

        if self.http_proxy or self.https_proxy or self.no_proxy:
            logger.info(f"Writing proxy settings to {ENVIRONMENT_FILE}")
            os.makedirs(os.path.dirname(ENVIRONMENT_FILE), exist_ok=True)
            with open(ENVIRONMENT_FILE, "w") as env:
                if self.http_proxy:
                    env.write(f"http_proxy={self.http_proxy}\n")
                if self.https_proxy:
                    env.write(f"https_proxy={self.https_proxy}\n")
                if self.no_proxy:
                    env.write(f"no_proxy={self.no_proxy}\n")
        else:
            try:
                os.unlink(ENVIRONMENT_FILE)
            except FileNotFoundError:
                pass

    def _on_install(self, _):
        self._ensure_set_up()

    def _on_start(self, _):
        self._ensure_set_up()
        for timer in (
            "daemon-reload.timer",
            "pull-metrics.timer",
            "start-all-timers.timer",
        ):
            subprocess.check_call(
                ["systemctl", "enable", "--quiet", "--now", timer]
            )

    def _on_upgrade_charm(self, _):
        self._ensure_set_up()

    def _on_config_changed(self, _):
        logger.info(f"Writing InfluxDB credentials to {CREDENTIALS_FILE}")

        influxdb_hostname = self.model.config["influxdb-hostname"]
        influxdb_port = self.model.config["influxdb-port"]
        influxdb_username = self.model.config["influxdb-username"]
        influxdb_password = self.model.config["influxdb-password"]
        influxdb_database = self.model.config["influxdb-database"]

        with open(
            os.open(
                CREDENTIALS_FILE,
                os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
                mode=0o600,
            ),
            "w",
        ) as cf:
            cf.write(
                dedent(
                    f"""\
            INFLUXDB_HOSTNAME={influxdb_hostname}
            INFLUXDB_PORT={influxdb_port}
            INFLUXDB_USERNAME={influxdb_username}
            INFLUXDB_PASSWORD={influxdb_password}
            INFLUXDB_DATABASE={influxdb_database}
            """
                )
            )

        dry_run = self.model.config["dry-run"]

        with open(
            os.open(
                DRY_RUN_FILE,
                os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
                mode=0o600,
            ),
            "w",
        ) as drf:
            drf.write(f"DRY_RUN={str(dry_run)}\n")


if __name__ == "__main__":
    main(UbuntuReleaseMetricsCollectorCharm)
