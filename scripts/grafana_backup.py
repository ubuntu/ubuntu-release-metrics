#!/usr/bin/env python3
"""Backup all dashboards from the Grafana HTTP API."""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode


def main():
    base_url = os.environ.get("GRAFANA_URL", "https://ubuntu-release.kpi.ubuntu.com")
    out_dir = Path(os.environ.get("BACKUP_DIR", "grafana_dashboards"))
    api_token = os.environ.get("GRAFANA_TOKEN")
    if not api_token:
        print("Please provide an API key in GRAFANA_TOKEN")
        return 1

    opener = urllib.request.build_opener()
    opener.addheaders = [("Authorization", f"Bearer {api_token}")]

    out_dir.mkdir(parents=True, exist_ok=True)

    # Fetch all dashboards (UID + slug)
    url = f"{base_url}/api/search?{urlencode({'type': 'dash-db'})}"
    req = urllib.request.Request(url)
    try:
        resp = opener.open(req)
    except urllib.error.HTTPError as e:
        print(f"Error fetching dashboards: {e.code} {e.reason}")
        return 1
    dashboards = json.loads(resp.read())
    if not dashboards:
        print("No dashboards found.")
        return 1

    for entry in dashboards:
        uid = entry.get("uid") or entry["uri"].split("/")[-1]
        print(f"Fetching {entry['title']} ({uid}) ...")
        req = urllib.request.Request(f"{base_url}/api/dashboards/uid/{uid}")
        try:
            resp = opener.open(req)
        except urllib.error.HTTPError as e:
            print(f"  Error fetching {uid}: {e.code} {e.reason}")
            continue
        payload = json.loads(resp.read())

        db = payload["dashboard"]
        slug = db.get("title", uid).replace(" ", "_").replace("/", "_")
        filename = out_dir / f"{slug}_{uid}.json"
        with open(filename, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"  -> {filename}")


if __name__ == "__main__":
    sys.exit(main())
