# Copyright 2021 Canonical Ltd

import datetime
import re
import subprocess
import tempfile

from launchpadlib.launchpad import Launchpad
from metrics.lib.basemetric import Metric

RSYNC_SERVER_REQUESTS = [
    "rsync://cdimage.ubuntu.com/cdimage/daily*/*/*.",
    "rsync://cdimage.ubuntu.com/cdimage/*/daily*/*/*.",
    "rsync://cdimage.ubuntu.com/cdimage/*/*/daily*/*/*.",
]
IMAGE_FORMATS = ["iso", "img.xz"]


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

    def rsync_list_images(self):
        rsync = ""
        for url in RSYNC_SERVER_REQUESTS:
            for img in IMAGE_FORMATS:
                try:
                    self.log.debug("Rsync listing %s%s", url, img)
                    rsync += subprocess.check_output(
                        [
                            "rsync",
                            "-4",
                            "--dry-run",
                            "-RL",
                            "--out-format='%l %M %f'",
                            "--archive",
                            "%s" % url + img,
                            "/tmp",
                        ],
                        text=True,
                    )
                except subprocess.CalledProcessError as e:
                    self.log.error("rsync call failed: %s", e.output)
        return rsync

    def collect(self):
        """ Collect the daily images details"""
        data = []

        rsync_cmd_output = self.rsync_list_images()

        for rsyncline in rsync_cmd_output.splitlines():
            if not any(ext in rsyncline for ext in IMAGE_FORMATS):
                continue
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
                # the path starts with a serie name then it's a desktop iso
                if path_table[0] in self.active_series:
                    flavor = "ubuntu"
                # or with 'daily-live'
                elif path_table[0] == "daily-live":
                    flavor = "ubuntu"
                # otherwise it starts with the flavor
                else:
                    flavor = path_table[0]

                # the path ends with the image filename
                image_name = path_table[-1]

                # let's filter out old ubuntu-core-16 images
                if image_name.startswith("ubuntu-core-16"):
                    continue

                if "current" in rsyncline:
                    current_or_pending = "current"
                else:
                    current_or_pending = "pending"

                regexp = re.compile(r"^(\w+)-.*-([\w\+]+)\..+")
                series, arch = regexp.search(image_name).groups()

                data.append(
                    {
                        "measurement": "daily_image_details",
                        "fields": {"age": image_age, "size": size},
                        "tags": {
                            "flavor": flavor,
                            "release": series,
                            "current_or_pending": current_or_pending,
                        },
                    }
                )
        return data
