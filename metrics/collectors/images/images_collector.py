# Copyright 2021 Canonical Ltd

from metrics.lib.basemetric import Metric
from launchpadlib.launchpad import Launchpad

import requests, datetime, tempfile

DESKTOP_CURRENT_DAILY = "http://cdimage.ubuntu.com/daily-live/current/%s-desktop-%s.iso"
DESKTOP_LTS_DAILY = "http://cdimage.ubuntu.com/%s/daily-live/current/%s-desktop-%s.iso"

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
        self.current_serie = self.ubuntu.current_series
        self.date_now = datetime.datetime.now()

    def get_iso_details(self, url):
        response = requests.head(url)
        last_modified = response.headers.get('Last-Modified')
        # If the info is missing it's probably because the image is not available
        if not last_modified:
           return (False, 0, 0)
        # HTTP headers are returning in RFC 1123 format
        date_current_image = datetime.datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z')
        image_age = (self.date_now - date_current_image).days

        image_size = response.headers.get('content-length', 0)
        return (True, image_age, image_size)

    def collect_desktop_images(self):
        """ Collect the desktop images details"""
        data = []

        # There are current daily built for those series
        for serie in self.active_series:
            # we build desktop on those architectures
            for arch in ("amd64", "arm64"):
                if serie == self.current_serie.name:
                    url = DESKTOP_CURRENT_DAILY % (serie, arch)
                else:
                    url = DESKTOP_LTS_DAILY % (serie, serie, arch)
                exists, image_age, image_size = self.get_iso_details(url)

                if not exists:
                    self.log.debug("There is no desktop %s/%s image" % (serie, arch))
                    continue

                data.append(
                    {
                        "measurement": "iso_images_details",
                        "fields": {
                            "age": image_age,
                            "size": image_size,
                        },
                        "tags": {
                            "release": serie,
                            "arch": arch,
                            "flavour": "desktop",
                        },
                    }
                )
        return data

    def collect(self):
        desktop = self.collect_desktop_images()

        return desktop
