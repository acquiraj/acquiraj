"""Search UI for the Ontario licensed child care centres database."""
import sqlite3
from pathlib import Path

from flask import Flask, render_template, request

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "childcare.db"
MAX_RESULTS = 200

app = Flask(__name__)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_distinct(column: str, limit: int = 1000):
    conn = get_conn()
    try:
        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM child_care_centres "
            f"WHERE {column} != '' ORDER BY {column} LIMIT ?",
            (limit,),
        ).fetchall()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_age_group_options():
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT DISTINCT age_groups FROM child_care_centres WHERE age_groups != ''"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    labels = set()
    for (value,) in rows:
        for part in value.split(","):
            part = part.strip()
            if part:
                labels.add(part)
    return sorted(labels)


@app.route("/", methods=["GET"])
def index():
    filters = {
        "city": request.args.get("city", "").strip(),
        "address": request.args.get("address", "").strip(),
        "postal_code": request.args.get("postal_code", "").strip(),
        "program_type": request.args.get("program_type", "").strip(),
        "age_group": request.args.getlist("age_group"),
    }
    searched = any([
        filters["city"], filters["address"], filters["postal_code"],
        filters["program_type"], filters["age_group"],
    ])

    results = []
    truncated = False
    error = None

    if searched:
        clauses = []
        params = []

        if filters["city"]:
            clauses.append("city LIKE ?")
            params.append(f"%{filters['city']}%")
        if filters["address"]:
            clauses.append("address LIKE ?")
            params.append(f"%{filters['address']}%")
        if filters["postal_code"]:
            clauses.append("postal_code LIKE ?")
            params.append(f"%{filters['postal_code'].upper().replace(' ', '')}%")
        if filters["program_type"]:
            clauses.append("program_type = ?")
            params.append(filters["program_type"])
        if filters["age_group"]:
            age_clauses = " OR ".join(["age_groups LIKE ?"] * len(filters["age_group"]))
            clauses.append(f"({age_clauses})")
            params.extend(f"%{ag}%" for ag in filters["age_group"])

        sql = "SELECT * FROM child_care_centres WHERE " + " AND ".join(clauses)
        sql += " ORDER BY city, centre_name LIMIT ?"
        params.append(MAX_RESULTS + 1)

        conn = get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            results = [dict(r) for r in rows[:MAX_RESULTS]]
            truncated = len(rows) > MAX_RESULTS
        except sqlite3.OperationalError as exc:
            error = (
                f"Database not ready ({exc}). "
                "Have you run scripts/fetch_data.py and scripts/load_db.py?"
            )
        finally:
            conn.close()

    return render_template(
        "index.html",
        filters=filters,
        results=results,
        searched=searched,
        truncated=truncated,
        error=error,
        cities=get_distinct("city"),
        program_types=get_distinct("program_type"),
        age_group_options=get_age_group_options(),
    )


if __name__ == "__main__":
    app.run(debug=True)
