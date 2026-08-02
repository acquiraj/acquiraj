"""Normalize the raw Ontario child care XLSX into a SQLite database.

Usage:
    python scripts/load_db.py
    python scripts/load_db.py --input path/to/file.xlsx --db path/to/out.db
"""
import argparse
import sqlite3
from pathlib import Path
from typing import List, Optional

import pandas as pd

DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "data" / "licensed_child_care_facilities.xlsx"
DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "childcare.db"

# Substrings (lowercased) matched against the source headers to locate each
# target field. If load_db.py warns a field is unmapped, check the printed
# headers it lists and add the real column name (or a substring of it) to
# the matching list below.
FIELD_CANDIDATES = {
    "licence_number": ["licence number", "license number", "licence_no", "licence#"],
    "centre_name": ["child care centre", "agency name", "centre name", "facility name", "operator name"],
    "licensee_name": ["licensee name", "licensee"],
    "program_type": ["program type", "auspice", "service type"],
    "address": ["address", "street address", "location address"],
    "city": ["city", "town", "municipality", "cmsm", "dssab"],
    "postal_code": ["postal code", "postal_code", "zip"],
    "ministry_region": ["ministry region", "region"],
    "licence_status": ["licence status", "status"],
    "language_of_service": ["language of service", "language"],
    "original_issue_date": ["original issue date", "issue date"],
    "phone": ["phone", "telephone"],
}

# Age groups sometimes appear as one combined column and sometimes as
# separate per-group flag columns -- both are handled below.
AGE_GROUP_LABELS = ["infant", "toddler", "preschool", "kindergarten", "school age", "primary/junior"]


def find_column(df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
    lower_cols = {c: c.lower() for c in df.columns}
    for kw in keywords:
        for col, low in lower_cols.items():
            if kw in low:
                return col
    return None


def build_age_groups(df: pd.DataFrame) -> pd.Series:
    combined_col = find_column(df, ["age group", "age_group", "age category"])
    if combined_col:
        return df[combined_col].fillna("").astype(str)

    flag_cols = [(find_column(df, [label]), label) for label in AGE_GROUP_LABELS]
    flag_cols = [(col, label) for col, label in flag_cols if col]

    if not flag_cols:
        return pd.Series([""] * len(df))

    def row_to_labels(row):
        labels = []
        for col, label in flag_cols:
            val = str(row[col]).strip().lower()
            if val in {"1", "true", "yes", "y"}:
                labels.append(label.title())
        return ", ".join(labels)

    return df.apply(row_to_labels, axis=1)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    mapped = {}
    unmapped = []
    for field, keywords in FIELD_CANDIDATES.items():
        col = find_column(df, keywords)
        if col:
            mapped[field] = df[col].fillna("").astype(str).str.strip()
        else:
            mapped[field] = pd.Series([""] * len(df))
            unmapped.append(field)

    mapped["age_groups"] = build_age_groups(df)
    if mapped["age_groups"].eq("").all():
        unmapped.append("age_groups")

    out = pd.DataFrame(mapped)
    out["postal_code"] = out["postal_code"].str.upper().str.replace(" ", "", regex=False)

    if unmapped:
        print("WARNING: could not auto-detect a source column for: " + ", ".join(unmapped))
        print("Available source columns:")
        for c in df.columns:
            print(f"  - {c}")
        print("Edit FIELD_CANDIDATES / AGE_GROUP_LABELS in load_db.py to fix the mapping.")

    return out


SCHEMA = """
CREATE TABLE child_care_centres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    licence_number TEXT,
    centre_name TEXT,
    licensee_name TEXT,
    program_type TEXT,
    age_groups TEXT,
    address TEXT,
    city TEXT,
    postal_code TEXT,
    ministry_region TEXT,
    licence_status TEXT,
    language_of_service TEXT,
    original_issue_date TEXT,
    phone TEXT
);
CREATE INDEX idx_city ON child_care_centres (city);
CREATE INDEX idx_postal_code ON child_care_centres (postal_code);
CREATE INDEX idx_program_type ON child_care_centres (program_type);
CREATE INDEX idx_age_groups ON child_care_centres (age_groups);
"""


def load(input_path: Path, db_path: Path) -> None:
    df = pd.read_excel(input_path, engine="openpyxl")

    print(f"Read {len(df)} rows from {input_path}")
    normalized = normalize(df)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("DROP TABLE IF EXISTS child_care_centres;")
        conn.executescript(SCHEMA)
        normalized.to_sql("child_care_centres", conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()

    print(f"Loaded {len(normalized)} rows into {db_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input file not found at {args.input}. Run scripts/fetch_data.py first.")

    load(args.input, args.db)


if __name__ == "__main__":
    main()
