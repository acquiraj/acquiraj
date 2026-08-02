"""Download the Ontario licensed child care facilities dataset via CKAN.

Usage:
    python scripts/fetch_data.py
    python scripts/fetch_data.py --list-resources
"""
import argparse
import sys
from pathlib import Path

import requests

CKAN_BASE = "https://data.ontario.ca"
DATASET_ID = "licensed-child-care-facilities-in-ontario"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "licensed_child_care_facilities.csv"


def get_package(dataset_id: str) -> dict:
    url = f"{CKAN_BASE}/api/3/action/package_show"
    resp = requests.get(url, params={"id": dataset_id}, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError(f"CKAN API returned an error: {payload}")
    return payload["result"]


def pick_csv_resource(resources: list) -> dict:
    csv_resources = [r for r in resources if (r.get("format") or "").upper() == "CSV"]
    if not csv_resources:
        raise RuntimeError("No CSV resource found on this dataset.")
    preferred = [
        r for r in csv_resources
        if "archive" not in (r.get("name") or "").lower()
        and "historic" not in (r.get("name") or "").lower()
    ]
    return (preferred or csv_resources)[0]


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
        resource = pick_csv_resource(resources)
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
