# Copyright 2021 Canonical Ltd

import datetime
import re
import subprocess
import tempfile

from launchpadlib.launchpad import Launchpad

from metrics.lib.basemetric import Metric

RSYNC_SERVER_REQUEST = "rsync://cdimage.ubuntu.com/cdimage/"
IMAGE_FORMATS = [".iso", ".img.xz", ".tar.gz", ".wsl"]

UBUNTUSTUDIO_DVD_RELEASES = ["jammy", "noble"]


class ImagesMetrics(Metric):
    def __init__(self, dry_run=False, verbose=False):
        super().__init__(dry_run, verbose)

        self.lp = Launchpad.login_anonymously(
            "metrics",
            "production",
            launchpadlib_dir=tempfile.mkdtemp(),
            version="devel",
        )
        self.ubuntu = self.lp.distributions["ubuntu"]
        self.active_series = {s.name: s for s in self.ubuntu.series if s.active}
        self.date_now = datetime.datetime.now()

    def rsync_list_images(self) -> list[str]:
        self.log.debug("Rsync listing %s", RSYNC_SERVER_REQUEST)
        rsync = subprocess.run(
            [
                "rsync",
                "-4",
                "--dry-run",
                "--relative",
                "--copy-links",
                "--out-format=%l %M %f",
                "--archive",
                RSYNC_SERVER_REQUEST,
                "/tmp",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = []
        for line in rsync.stdout.splitlines():
            if any(line.endswith(ext) for ext in IMAGE_FORMATS):
                lines.append(line)
        return lines

    def collect(self):
        """Collect the daily images details"""
        data = []

        rsync_cmd_output = self.rsync_list_images()

        for rsyncline in rsync_cmd_output:
            self.log.debug("parsing rsync line '%s'", rsyncline)
            if "current" in rsyncline or "pending" in rsyncline:
                # the format is specific in the rsync call '%l %M %f'
                size, mtime, path = rsyncline.strip("'").split()
                size = int(size)
                date_current_image = datetime.datetime.strptime(
                    mtime, "%Y/%m/%d-%H:%M:%S"
                )
                image_age = (self.date_now - date_current_image).days

                # there are variations of the naming scheme so guess a bit
                path_table = path.split("/")

                # first element is the flavor/product
                flavor = path_table[0]

                # the path ends with the image filename
                image_name = path_table[-1]

                image_type = None
                for part_of_path in path_table:
                    # If statement like this to cover daily-live, daily-legacy
                    # daily-minimal, daily-preinstalled and dvd
                    starts_with_daily = part_of_path.startswith("daily-")
                    if starts_with_daily or part_of_path == "dvd":
                        image_type = part_of_path.replace("daily-", "")
                        break

                # let's filter out hidden files that sometimes show up
                if image_name.startswith("."):
                    continue

                # let's filter out old ubuntu-core-16 images
                if image_name.startswith("ubuntu-core-16"):
                    continue

                if "current" in rsyncline:
                    current_or_pending = "current"
                else:
                    current_or_pending = "pending"

                regexp = re.compile(r"^(\w+)-.*-([\w\+]+)\..+")
                series, arch = regexp.search(image_name).groups()

                # 2024-06-17 ubuntu studio recently moved from having a "dvd" directory
                # to having a "daily-live" directory for oracular - until jammy and noble are
                # EOL we'll need this hack unless the directories for jammy and noble get
                # retroactively changed.
                # This hack stops us pushing data to the KPI for images under this directory:
                # https://cdimage.ubuntu.com/ubuntustudio/dvd/
                if (
                    flavor == "ubuntustudio"
                    and series not in UBUNTUSTUDIO_DVD_RELEASES
                    and "dvd" in rsyncline
                ):
                    continue

                data.append(
                    {
                        "measurement": "daily_image_details",
                        "fields": {"age": image_age, "size": size},
                        "tags": {
                            "flavor": flavor,
                            "release": series,
                            "current_or_pending": current_or_pending,
                            "architecture": arch,
                            "image_type": image_type,
                        },
                    }
                )
        return data
