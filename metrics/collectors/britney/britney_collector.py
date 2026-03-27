# Copyright 2025 Canonical Ltd

from datetime import datetime, timezone
from urllib.parse import urljoin

import csv
import requests
import time
import yaml

from distro_info import UbuntuDistroInfo
from yaml import CLoader as Loader
from metrics.lib.basemetric import Metric

BRITNEY_URL = "https://ubuntu-archive-team.ubuntu.com/proposed-migration/"
UPDATE_EXCUSES_CSV_URL = BRITNEY_URL + "update_excuses.csv"
UPDATE_EXCUSES_BY_TEAM_URL = BRITNEY_URL + "update_excuses_by_team.yaml"


class BritneyMetrics(Metric):
    def __init__(self, dry_run=False, verbose=False):
        super().__init__(dry_run, verbose)
        supported_series = UbuntuDistroInfo().supported()
        esm_series = UbuntuDistroInfo().supported_esm()
        self.active_series = set(supported_series + esm_series)
        self.dev_series = UbuntuDistroInfo().devel()
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

    def get_update_excuses_stats(self):
        data = []
        self.log.debug("Getting update_excuses stats for " + self.dev_series)
        self.log.debug("Downloading CSV...")

        try:
            response = requests.get(UPDATE_EXCUSES_CSV_URL, timeout=60)
            response.raise_for_status()

            self.log.debug("Parsing CSV...")
            lines = response.text.strip().splitlines()
            reader = csv.DictReader(lines)

            # Since we are stateless, we look back 12 hours to ensure
            # we never miss a record, even if this cron job skipped a few runs.
            now_ms = int(time.time() * 1000)
            lookback_ms = 12 * 60 * 60 * 1000
            cutoff = now_ms - lookback_ms

            for row in reader:
                try:
                    ts = int(row["time"])
                    if ts > cutoff:
                        data.append(
                            {
                                "measurement": "update_excuses_stats",
                                "tags": {"release": self.dev_series},
                                "time": datetime.fromtimestamp(
                                    ts / 1000.0, tz=timezone.utc
                                ),
                                "fields": {
                                    "valid_candidates": int(row["valid candidates"]),
                                    "not_considered": int(row["not considered"]),
                                    "total": int(row["total"]),
                                    "median_age": int(row["median age"]),
                                    "backlog": int(row["backlog"]),
                                },
                            }
                        )
                except (KeyError, ValueError) as exc:
                    # Skip malformed rows but continue processing the rest of the CSV
                    self.log.warning(
                        "Skipping malformed row in update_excuses CSV: %s", exc
                    )
                    continue
        except (requests.exceptions.RequestException, csv.Error) as exc:
            self.log.warning("Failed to download or parse update_excuses CSV: %s", exc)
            return []
        return data

    def get_update_excuses_by_team_stats(self):
        data = []
        self.log.debug("Getting update_excuses_by_team stats for " + self.dev_series)
        self.log.debug("Fetching YAML data...")
        try:
            response = requests.get(UPDATE_EXCUSES_BY_TEAM_URL, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.log.warning(f"Failed to fetch data: {e}")
            return []

        self.log.debug("Parsing YAML data...")
        try:
            parsed_yaml = yaml.load(response.text, Loader=Loader)
        except yaml.YAMLError as e:
            self.log.warning(f"Failed to parse YAML: {e}")
            return []

        if parsed_yaml is None:
            parsed_yaml = {}
        for team, packages in parsed_yaml.items():
            npackages = 0
            ages = []

            if packages:
                for item in packages:
                    age_val = float(item["age"])
                    if age_val > 3.0:
                        npackages += 1
                        ages.append(age_val)

            age_average = sum(ages) / len(ages) if ages else 0.0

            data.append(
                {
                    "measurement": "update_excuses_by_team_stats",
                    "fields": {"count": npackages, "age": age_average},
                    "tags": {"release": self.dev_series, "team": team},
                }
            )
        return data

    def collect(self):
        run_ages = self.get_britney_last_run_age()
        run_durations = self.get_britney_last_run_duration()
        update_excuses_stats = self.get_update_excuses_stats()
        update_excuses_by_team_stats = self.get_update_excuses_by_team_stats()
        return (
            run_ages
            + run_durations
            + update_excuses_stats
            + update_excuses_by_team_stats
        )
