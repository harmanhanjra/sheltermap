#!/usr/bin/env python3
"""ShelterMap — open dataset generator for housing/shelter access info.

Loads bundled (or user-supplied) shelter datasets, validates them, and emits
an open dataset (JSON or CSV) with search, attribute filtering, and capacity
stats. Fully offline, stdlib-only.

Usage:
    python sheltermap.py --list-cities
    python sheltermap.py --city berlin
    python sheltermap.py --city berlin --search wheelchair
    python sheltermap.py --city delhi --filter type=emergency --format csv
    python sheltermap.py --city berlin --stats
    python sheltermap.py --data mycity.json --out mycity.csv --format csv
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import pathlib
import sys

DATA_DIR = pathlib.Path(__file__).parent / "data"

REQUIRED_FIELDS = {"name", "type", "capacity", "access", "contact"}
VALID_TYPES = {"emergency", "registry", "transitional", "subsidized"}


# ---------------------------------------------------------------- loading

def load_city(city: str) -> list[dict]:
    """Load a bundled city dataset by name (case-insensitive)."""
    path = DATA_DIR / f"{city.lower()}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"no dataset for city '{city}'. Available: {', '.join(list_cities()) or 'none'}"
        )
    return load_file(path)


def load_file(path) -> list[dict]:
    """Load and validate a dataset file (JSON or CSV)."""
    path = pathlib.Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(io.StringIO(text)))
        for row in rows:
            row["capacity"] = int(row["capacity"] or 0)
        records = rows
    else:
        doc = json.loads(text)
        records = doc["records"] if isinstance(doc, dict) else doc
    problems = validate(records)
    if problems:
        raise ValueError("invalid records in %s:\n  %s" % (path, "\n  ".join(problems)))
    return records


def validate(records: list[dict]) -> list[str]:
    problems = []
    for i, rec in enumerate(records):
        missing = REQUIRED_FIELDS - set(rec)
        if missing:
            problems.append(f"record {i} ({rec.get('name', '?')}): missing {sorted(missing)}")
            continue
        if rec["type"] not in VALID_TYPES:
            problems.append(
                f"record {i} ({rec['name']}): unknown type '{rec['type']}' "
                f"(valid: {sorted(VALID_TYPES)})"
            )
        if not isinstance(rec["capacity"], int) or rec["capacity"] < 0:
            problems.append(f"record {i} ({rec['name']}): capacity must be a non-negative int")
        for field in ("access", "contact"):
            if not str(rec[field]).strip():
                problems.append(f"record {i} ({rec['name']}): '{field}' is empty")
    return problems


# ---------------------------------------------------------------- querying

def search(records: list[dict], text: str) -> list[dict]:
    """Case-insensitive substring match across all fields."""
    text = text.lower()
    return [
        r for r in records
        if any(text in str(v).lower() for v in r.values())
    ]


def filter_by(records: list[dict], filters: list[str]) -> list[dict]:
    """Filter records by 'field=value' strings, ANDed together."""
    parsed = []
    for f in filters:
        if "=" not in f:
            raise ValueError(f"bad filter '{f}', expected field=value")
        field, value = f.split("=", 1)
        parsed.append((field.strip().lower(), value.strip().lower()))
    out = []
    for rec in records:
        ok = True
        for field, value in parsed:
            rec_val = str(rec.get(field, "")).lower()
            if value not in [v.strip() for v in rec_val.split(",")]:
                ok = False
                break
        if ok:
            out.append(rec)
    return out


def stats(records: list[dict]) -> dict:
    by_type: dict[str, int] = {}
    accessible = 0
    for r in records:
        by_type[r["type"]] = by_type.get(r["type"], 0) + r["capacity"]
        tags = [t.strip().lower() for t in str(r.get("access", "")).split(",")]
        if "wheelchair" in tags:
            accessible += 1
    return {
        "records": len(records),
        "total_capacity": sum(r["capacity"] for r in records),
        "capacity_by_type": dict(sorted(by_type.items())),
        "wheelchair_accessible": accessible,
    }


# ---------------------------------------------------------------- output

def to_dataset(city: str, records: list[dict]) -> dict:
    return {
        "format": "sheltermap-open-dataset/v1",
        "city": city,
        "record_count": len(records),
        "records": records,
    }


def render(records: list[dict], fmt: str) -> str:
    if fmt == "csv":
        if not records:
            return ""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
        return buf.getvalue()
    return json.dumps(records, indent=2, ensure_ascii=False)


def list_cities() -> list[str]:
    if not DATA_DIR.exists():
        return []
    return sorted(p.stem for p in DATA_DIR.glob("*.json"))


# ---------------------------------------------------------------- cli

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="sheltermap",
        description="Open dataset generator for housing/shelter access info.",
    )
    parser.add_argument("--city", help="bundled city dataset to load (e.g. berlin)")
    parser.add_argument("--data", help="path to your own JSON/CSV dataset")
    parser.add_argument("--search", help="substring to search across all fields")
    parser.add_argument("--filter", action="append", dest="filters",
                        metavar="FIELD=VALUE", help="filter, e.g. type=emergency (repeatable)")
    parser.add_argument("--stats", action="store_true", help="print capacity stats")
    parser.add_argument("--format", choices=["json", "csv"], default="json", dest="fmt")
    parser.add_argument("--out", help="write result to file instead of stdout")
    parser.add_argument("--list-cities", action="store_true", help="list bundled cities")
    args = parser.parse_args(argv)

    if args.list_cities:
        for city in list_cities():
            print(city)
        return 0

    if not args.city and not args.data:
        parser.error("either --city or --data is required (try --list-cities)")

    try:
        records = load_file(args.data) if args.data else load_city(args.city)
        if args.search:
            records = search(records, args.search)
        if args.filters:
            records = filter_by(records, args.filters)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    city = args.city or pathlib.Path(args.data).stem
    if args.stats:
        print(json.dumps(stats(records), indent=2))
        return 0

    if args.fmt == "csv":
        output = render(records, "csv")
    else:
        output = json.dumps(to_dataset(city, records), indent=2, ensure_ascii=False)
    if args.out:
        pathlib.Path(args.out).write_text(output, encoding="utf-8")
        print(f"wrote {len(records)} records to {args.out}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
