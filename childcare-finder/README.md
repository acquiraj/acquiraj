# Ontario Licensed Child Care Finder

A small search app over Ontario's open data on licensed child care facilities.
Users can search by **city/town**, **address**, **postal code**, **program
type**, and **age group** — any one of these is enough to search, none are
required together.

Data source: [Licensed Child Care Facilities in Ontario](https://data.ontario.ca/dataset/licensed-child-care-facilities-in-ontario)
(data.ontario.ca), updated monthly by the Ministry of Education, licensed
under the [Open Government Licence – Ontario](https://www.ontario.ca/page/open-government-licence-ontario).
This project reads that dataset instead of scraping the live
`earlyyears.edu.gov.on.ca` search portal, which has no stable API and is
fragile/likely against terms of use to scrape directly.

## Setup

```bash
cd childcare-finder
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## 1. Fetch the data

Downloads the current XLSX from Ontario's CKAN open data API (the dataset is
published as an Excel file, updated monthly). Requires internet access (this
step can't run in network-restricted sandboxes).

```bash
python scripts/fetch_data.py
```

If the download fails, run `python scripts/fetch_data.py --list-resources`
to see what resources the dataset actually exposes and adjust
`scripts/fetch_data.py` if the dataset id or resource format has changed.

## 2. Load it into SQLite

```bash
python scripts/load_db.py
```

This normalizes the raw spreadsheet columns into a `child_care_centres`
table in `data/childcare.db`. Government column names shift over time, so
the loader auto-detects columns by keyword matching (see `FIELD_CANDIDATES`
and `AGE_GROUP_LABELS` in `scripts/load_db.py`). **Check the console
output** — it prints a warning listing any field it couldn't confidently
map, plus the actual source headers, so you can fix the keyword list if
needed.

## 3. Run the search app

```bash
python app/app.py
```

Then open http://127.0.0.1:5000 — fill in any one filter (or several) and
search.

## Notes

- Postal codes are matched with spaces/case stripped, so `n9a 1a1`, `N9A1A1`,
  and `N9A` (partial) all match.
- Program type is an exact-match dropdown populated from whatever distinct
  values exist in the loaded data.
- Age group is checkboxes (multi-select, OR'd together) populated from the
  data itself, since the source dataset sometimes represents age groups as
  one combined column and sometimes as separate flag columns per group —
  `load_db.py` handles both.
- Results are capped at 200 rows per search to keep the page usable; narrow
  your filters if you hit that cap.
