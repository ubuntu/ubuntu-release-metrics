import logging
import os
import shutil
from pathlib import Path
from subprocess import CalledProcessError, check_call

logger = logging.getLogger(__name__)

HOME = Path("~ubuntu").expanduser()
REPO_LOCATION = HOME / "ubuntu-release-metrics"


class ReleaseMetrics:
    def __init__(self):
        self._systemd_dir = Path("/etc/systemd/system/")
        self._influx_path = Path("/home/ubuntu/influx.conf")
        self.run_metric_collector_service_template = f"""[Unit]
Description=Run $METRIC metric

[Service]
DynamicUser=yes
Environment=DRY_RUN=$DRY_RUN
Environment=http_proxy=$HTTP_PROXY
Environment=https_proxy=$HTTPS_PROXY
Environment=no_proxy=$NO_PROXY
EnvironmentFile={str(self._influx_path)}
ExecStart=/usr/bin/python3 -c 'from metrics.collectors.$METRIC import run_metric; run_metric(dry_run=$DRY_RUN, verbose=True)'
NoNewPrivileges=yes
PrivateMounts=yes
PrivateUsers=yes
ProtectClock=yes
ProtectControlGroups=yes
ProtectHostname=yes
ProtectKernelLogs=yes
ProtectKernelModules=yes
ProtectKernelTunables=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
RestrictRealtime=yes
RestrictSUIDSGID=yes
RuntimeMaxSec=10m
Type=simple
WorkingDirectory=/home/ubuntu/ubuntu-release-metrics/"""  # flake8: noqa: F401
        self.run_metric_collector_timer_template = """[Unit]
Description=Run run-metric-collector@$METRIC.service on a timer
After=timers.target

[Timer]
OnBootSec=30s
OnUnitInactiveSec=5m
FixedRandomDelay=yes
RandomizedDelaySec=1m
Unit=run-metric-collector@$METRIC.service

[Install]
WantedBy=timers.target"""

    def install(self, config: dict):
        self._install_deps()
        self._copy_repo()
        self.configure(config)

    def configure(self, config: dict):
        self._write_influx_creds(config)
        self._setup_units(config)

    def _install_deps(self):
        try:
            logger.info("running apt update")
            check_call(["apt-get", "update", "-y"])
            logger.info("running apt upgrade")
            check_call(["apt-get", "upgrade", "-y"])
            logger.info("installing dependencies")
            check_call(
                [
                    "apt-get",
                    "install",
                    "-y",
                    "git",
                    "python3-influxdb",
                    "python3-launchpadlib",
                ]
            )
        except CalledProcessError as e:
            logger.debug(
                "installing and updating packages failed with return code %d",
                e.returncode,
            )
            return

    def _copy_repo(self):
        logger.info("copying source code...")
        shutil.copytree(".", REPO_LOCATION)
        check_call(["chown", "-R", "ubuntu:ubuntu", str(REPO_LOCATION)])

    def _write_influx_creds(self, config: dict):
        # write influx creds to /home/ubuntu/influx.conf
        logger.info(f"writing influx creds to {self._influx_path}")
        config_vars = [
            "influxdb_hostname",
            "influxdb_port",
            "influxdb_username",
            "influxdb_password",
            "influxdb_database",
        ]
        influx_vars = []
        for var in config_vars:
            try:
                influx_value = config.get("var", None)
                if influx_value is None:
                    raise Exception(f"{var} cannot be empty or None")
                influx_vars.append(f"{var.upper()}={influx_value}")
            except Exception as e:
                logger.error(
                    f"writing influx creds to {self._influx_path} failed with {e}"
                )
        self._influx_path.write_text("\n".join(influx_vars))

    def _setup_units(self, config: dict):
        logger.info("setting up ubuntu-release-metrics systemd units")
        # first, check for anything old under /etc/systemd/system and remove it
        old_systemd_files = [
            f for f in Path("/etc/systemd/system/").glob("run-metric-collector@*")
        ]
        for fl in old_systemd_files:
            os.remove(fl)
        # this is the set of juju config variables involved in the systemd units
        config_vars = [
            "dry_run",
            "http_proxy",
            "https_proxy",
            "no_proxy",
        ]
        # list of metrics - each directory under metrics/collectors
        metrics = [
            f
            for f in Path(REPO_LOCATION / "metrics" / "collectors").glob("**/*")
            if f.is_dir()
        ]
        for metric in metrics:
            logger.info(f"setting up {metric} systemd unit and timer")
            try:
                # for each metric, re-write the service and timer files
                metric_service_file = self.run_metric_collector_service_template
                for cfg_var in config_vars:
                    cfg_value = config.get(cfg_var, None)
                    if cfg_value is None:
                        raise Exception(f"{cfg_var} cannot be None in juju config")
                    metric_service_file = metric_service_file.replace(
                        f"${cfg_var.upper()}",
                        str(cfg_value),
                    )
                metric_timer_file = self.run_metric_collector_timer_template.replace(
                    "$METRIC",
                    metric,
                )
                service_file = (
                    self._systemd_dir / f"run-metric-collector@{metric}.service"
                )
                timer_file = self._systemd_dir / f"run-metric-collector@{metric}.timer"
                service_file.write_text(metric_service_file)
                timer_file.write_text(metric_timer_file)
            except Exception as e:
                logger.error(
                    f"failed to install {metric} systemd unit + timer, traceback:\n{e}"
                )
                return
        # There is no need to restart services, since they're
        # periodically triggered and very short-lived.
        # So we just reload the daemon.
        check_call(["systemctl", "daemon-reload"])
