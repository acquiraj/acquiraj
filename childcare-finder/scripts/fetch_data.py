"""Download the Ontario licensed child care facilities dataset via CKAN.

Usage:
    python scripts/fetch_data.py
    python scripts/fetch_data.py --list-resources
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import requests

CKAN_BASE = "https://data.ontario.ca"
DATASET_ID = "licensed-child-care-facilities-in-ontario"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "licensed_child_care_facilities.xlsx"


def get_package(dataset_id: str) -> dict:
    url = f"{CKAN_BASE}/api/3/action/package_show"
    resp = requests.get(url, params={"id": dataset_id}, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError(f"CKAN API returned an error: {payload}")
    return payload["result"]


def _parse_month_year(name: str):
    try:
        return datetime.strptime(name.strip(), "%B %Y")
    except ValueError:
        return None


def pick_data_resource(resources: list) -> dict:
    # The dataset publishes the actual facility data as XLSX (not CSV), plus a
    # separate "Data dictionary" XLSX and a couple of empty-url/WEB-format
    # placeholder resources -- filter down to real, downloadable data files.
    candidates = [
        r for r in resources
        if (r.get("format") or "").upper() == "XLSX"
        and r.get("url")
        and "dictionary" not in (r.get("name") or "").lower()
    ]
    if not candidates:
        raise RuntimeError("No downloadable XLSX data resource found on this dataset.")

    # Resources are typically named by month (e.g. "June 2026") and updated
    # monthly -- prefer the most recent by parsed date, falling back to
    # whichever one is listed last if names don't parse as "Month Year".
    dated = [(r, _parse_month_year(r.get("name") or "")) for r in candidates]
    if any(d for _, d in dated):
        dated = [(r, d) for r, d in dated if d is not None]
        dated.sort(key=lambda pair: pair[1])
        return dated[-1][0]
    return candidates[-1]


def download(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", default=DATASET_ID)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--list-resources", action="store_true",
        help="Print available resources on the dataset and exit, without downloading.",
    )
    args = parser.parse_args()

    try:
        package = get_package(args.dataset_id)
    except Exception as exc:
        print(f"Failed to reach Ontario's open data API: {exc}", file=sys.stderr)
        sys.exit(1)

    resources = package.get("resources", [])

    if args.list_resources:
        for r in resources:
            print(f"- name={r.get('name')!r} format={r.get('format')} url={r.get('url')}")
        return

    try:
        resource = pick_data_resource(resources)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        print("Available resources:", file=sys.stderr)
        for r in resources:
            print(f"- name={r.get('name')!r} format={r.get('format')} url={r.get('url')}", file=sys.stderr)
        sys.exit(1)

    print(f"Downloading '{resource.get('name')}' -> {args.out}")
    try:
        download(resource["url"], args.out)
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    main()
