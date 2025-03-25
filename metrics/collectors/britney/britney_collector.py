# Copyright 2025 Canonical Ltd

from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from distro_info import UbuntuDistroInfo
from metrics.lib.basemetric import Metric

BRITNEY_URL = "https://ubuntu-archive-team.ubuntu.com/proposed-migration/"


class BritneyMetrics(Metric):
    def __init__(self, dry_run=False, verbose=False):
        super().__init__(dry_run, verbose)
        supported_series = UbuntuDistroInfo().supported()
        esm_series = UbuntuDistroInfo().supported_esm()
        self.active_series = set(supported_series + esm_series)
        self.latest_dates = {}

    def get_log_duration(self, log_url):
        """returns run duration from log in minutes,
        or false if log is from an incomplete run"""
        LOG_TIME_FORMAT = "%a, %d %b %Y %H:%M:%S %z"
        log_text = requests.get(log_url).text
        log_lines = log_text.splitlines()
        if not log_lines[-1].startswith("Finished at:"):
            return False
        start_time = datetime.strptime(log_lines[0], LOG_TIME_FORMAT)
        finish_time = datetime.strptime(
            log_lines[-1].replace("Finished at: ", ""), LOG_TIME_FORMAT
        )
        return (finish_time - start_time).seconds // 60

    def get_latest_log(self, logs_url):
        "yield the link to the latest valid log for date"
        date_logs = requests.get(logs_url).text
        date_logs = date_logs.split("<td>")
        date_logs.reverse()
        for line in date_logs[1:]:
            if "notest" in line or ".log" not in line:
                continue
            date_index = line.find("href=") + 8
            latest_date = line[date_index : date_index + 12]  # noqa: E203
            self.log.debug("Trying log " + latest_date)
            yield logs_url + latest_date

    def get_britney_last_run_age(self):
        data = []
        for s in self.active_series:
            self.log.debug("Getting run time for " + s)
            url = urljoin(BRITNEY_URL, f"{s}/update_excuses.html")
            generated_datetime = None
            update_excuses = requests.get(url).text
            for line in update_excuses.splitlines():
                if "Generated:" in line:
                    tokens = line.split(" ")
                    generated_datetime = " ".join(tokens[1:3])
                    break
            if not generated_datetime:
                continue
            now = datetime.now(timezone.utc)
            generated_datetime = datetime.strptime(
                generated_datetime, "%Y.%m.%d %H:%M:%S"
            ).replace(tzinfo=timezone.utc)
            self.latest_dates[s] = generated_datetime.strftime("%Y-%m-%d")
            run_age = (now - generated_datetime).seconds // 3600
            data.append(
                {
                    "measurement": "britney_last_run_age",
                    "fields": {"run_age": run_age},
                    "tags": {"release": s},
                }
            )
        return data

    def get_britney_last_run_duration(self):
        data = []
        for s in self.active_series:
            self.log.debug("Getting run duration for " + s)
            url = urljoin(BRITNEY_URL, f"log/{s}/{self.latest_dates[s]}/")

            for latest_log_url in self.get_latest_log(url):
                log_duration = self.get_log_duration(latest_log_url)
                if log_duration:
                    data.append(
                        {
                            "measurement": "britney_last_run_duration",
                            "fields": {"run_duration": log_duration},
                            "tags": {"release": s},
                        }
                    )
                    break

        return data

    def collect(self):
        run_ages = self.get_britney_last_run_age()
        run_durations = self.get_britney_last_run_duration()
        return run_ages + run_durations
