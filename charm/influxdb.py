import logging
import os
import secrets
import string
from pathlib import Path
from subprocess import CalledProcessError, check_call
from textwrap import dedent

logger = logging.getLogger(__name__)

HOME = Path("~ubuntu").expanduser()


class InfluxDB:
    def __init__(self):
        # For use by caller
        self.admin_password = self._get_password("admin")
        self.collector_password = self._get_password("collector")
        self.grafana_password = self._get_password("grafana")

        self.influxdb_hostname = "localhost"
        self.influxdb_port = 8086
        self.influxdb_username = "collector"
        self.influxdb_password = self.collector_password
        self.influxdb_database = "metrics"

    def install(self):
        self._install_deps()

    def configure(self, config: dict):
        logger.info(f"config:\n{config}")

        self._setup_database()
        self._enable_http()

    def _get_password(self, username):
        password_path = Path(f"/root/.influx_{username}_password")
        if password_path.exists():
            logger.info(f"Reading password from {password_path}")
            return password_path.read_text().strip()
        password = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(20)
        )
        logger.info(f"Saving new password to {password_path}")
        password_path.write_text(password)
        return password

    def _setup_database(self):
        grafana_password_path = HOME / "influxdb_grafana_password"

        if grafana_password_path.exists():
            logger.info("InfluxDB database already configured")
            return

        def _run_influx(command):
            check_call(
                [
                    "influx",
                    "-username",
                    "admin",
                    "-password",
                    self.admin_password,
                    "-execute",
                    command,
                ]
            )

        logger.info("Creating InfluxDB 'admin' user")
        # Create admin user
        check_call(
            [
                "influx",
                "-execute",
                f"CREATE USER admin WITH PASSWORD '{self.admin_password}' WITH ALL PRIVILEGES",
            ]
        )

        # Create metrics DB
        logger.info("Creating InfluxDB 'metrics' database")
        _run_influx("CREATE DATABASE metrics")

        # Create collector user
        logger.info("Creating InfluxDB 'collector' user")
        _run_influx(f"CREATE USER collector WITH PASSWORD '{self.collector_password}'")
        _run_influx("GRANT WRITE ON metrics TO collector")

        # Create grafana user
        logger.info("Creating InfluxDB 'grafana' user")
        _run_influx(f"CREATE USER grafana WITH PASSWORD '{self.grafana_password}'")
        _run_influx("GRANT READ ON metrics TO grafana")

        grafana_password_path.write_text(self.grafana_password)

    def _enable_http(self):
        if os.path.exists("/etc/ssl/influxdb-selfsigned.key"):
            logger.info("InfluxDB already configured, skipping")
            return
        logger.info("Generating self-signed certificate for InfluxDB")
        check_call(
            [
                "openssl",
                "req",
                "-x509",
                "-nodes",
                "-newkey",
                "rsa:2048",
                "-keyout",
                "/etc/ssl/influxdb-selfsigned.key",
                "-out",
                "/etc/ssl/influxdb-selfsigned.crt",
                "-days",
                "3650",  # ~10 years
                "-subj",
                "/C=GB/ST=London/L=London/O=Canonical/CN=influxdb.ubuntu-kpi.internal",
            ]
        )
        check_call(
            [
                "chown",
                "influxdb:influxdb",
                "/etc/ssl/influxdb-selfsigned.key",
                "/etc/ssl/influxdb-selfsigned.crt",
            ]
        )
        config_path = Path("/etc/influxdb/influxdb.conf")
        current_config = config_path.read_text()
        new_config = current_config.replace(
            "\n[http]\n",
            dedent(
                """
            [http]
              enabled = true
              bind-address = ":8086"
              auth-enabled = true
              log-enabled = true
              write-tracing = false
              https-enabled = true
              https-certificate = "/etc/ssl/influxdb-selfsigned.crt"
              https-private-key = "/etc/ssl/influxdb-selfsigned.key"
              """
            ),
        )
        logger.info(f"Writing new InfluxDB config to {config_path}")
        config_path.write_text(new_config)
        check_call(["systemctl", "restart", "influxdb"])

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
                    "influxdb",
                    "influxdb-client",
                ]
            )
        except CalledProcessError as e:
            logger.debug(
                "installing and updating packages failed with return code %d",
                e.returncode,
            )
            raise e
