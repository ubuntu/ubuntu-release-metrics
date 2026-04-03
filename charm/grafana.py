import logging
from pathlib import Path
from subprocess import CalledProcessError, check_call

logger = logging.getLogger(__name__)

HOME = Path("~ubuntu").expanduser()


class Grafana:
    def install(self):
        self._install_deps()

    def configure(self, config: dict):
        self.grafana_port = 3000
        logger.info(f"config:\n{config}")
        logger.info("no-op")

    def _install_deps(self):
        try:
            logger.info("installing dependencies")
            check_call(["snap", "install", "grafana"])
        except CalledProcessError as e:
            logger.debug(
                "installing packages failed with return code %d",
                e.returncode,
            )
            return
