import logging
from pathlib import Path
from textwrap import dedent
from subprocess import CalledProcessError, check_call

logger = logging.getLogger(__name__)

HOME = Path("~ubuntu").expanduser()


class Grafana:
    def __init__(self):
        # For use by caller
        self.grafana_port = 3000

    def install(self):
        self._install_deps()

    def configure(self, config: dict):
        logger.info(f"config:\n{config}")
        grafana_conf = Path("/var/snap/grafana/current/conf/grafana.ini")
        grafana_conf.parent.mkdir(exist_ok=True, parents=True)
        grafana_conf.write_text(
            dedent(
                """
                [auth.anonymous]
                enabled = true
                """
            )
        )
        check_call(["systemctl", "restart", "snap.grafana.grafana.service"])

    def _install_deps(self):
        try:
            logger.info("installing dependencies")
            check_call(["snap", "install", "grafana"])
        except CalledProcessError as e:
            logger.debug(
                "installing packages failed with return code %d",
                e.returncode,
            )
            raise e
