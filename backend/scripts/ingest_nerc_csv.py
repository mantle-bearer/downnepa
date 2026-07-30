from __future__ import annotations

import argparse
import csv
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a verified NERC feeder-performance CSV into DownNepa."
    )
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--source-url", required=True)
    args = parser.parse_args()

    raw = args.csv_file.read_bytes()
    rows = []
    with args.csv_file.open(newline="", encoding="utf-8-sig") as handle:
        for item in csv.DictReader(handle):
            rows.append(
                {
                    "disco": item["disco"].strip(),
                    "reporting_period_start": item["reporting_period_start"].strip(),
                    "reporting_period_end": item["reporting_period_end"].strip(),
                    "feeder_name": item["feeder_name"].strip(),
                    "location": item["location"].strip(),
                    "major_areas_served": item["major_areas_served"].strip(),
                    "average_supply_hours_per_day": float(item["average_supply_hours_per_day"]),
                    "estimated_outage_hours_per_day": float(item["estimated_outage_hours_per_day"]),
                    "current_band": item.get("current_band", "").strip() or None,
                    "regulatory_outcome": item.get("regulatory_outcome", "").strip() or None,
                    "source_url": item.get("source_url", "").strip() or args.source_url,
                }
            )

    token = request(
        f"{args.api}/api/auth/login",
        {"email": args.admin_email, "password": args.admin_password},
    )["access_token"]
    result = request(
        f"{args.api}/api/admin/pipeline/import",
        {
            "source": f"NERC CSV: {args.csv_file.name}",
            "source_url": args.source_url,
            "source_hash": hashlib.sha256(raw).hexdigest(),
            "rows": rows,
        },
        token,
    )
    print(json.dumps(result, indent=2))


def request(url: str, payload: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    call = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(call) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"Import failed ({error.code}): {error.read().decode()}") from error


if __name__ == "__main__":
    main()
