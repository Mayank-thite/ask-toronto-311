"""Download the 2024 and 2025 Toronto 311 files and load them into PostgreSQL.

    python -m ask311.load            # download (if needed) + load
"""
import csv
import io
import pathlib
import re
import zipfile

import psycopg
import requests

from .config import ADMIN_DSN
from .topics import topic_for

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
SOURCES = {
    2024: "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/2e54bc0e-4399-4076-b717-351df5918ae7/resource/f46b640d-d465-4f8b-9db5-5000a08295cd/download/sr2024.zip",
    2025: "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/2e54bc0e-4399-4076-b717-351df5918ae7/resource/f3db05ab-2588-4159-89f7-56c74d1d8201/download/sr2025.zip",
}
# Division names that contain a comma. The city's CSV doesn't quote them,
# so these rows arrive with 10 fields instead of 9.
COMMA_DIVISIONS = {"Parks, Forestry & Recreation", "Environment, Climate & Forestry"}
WARD_RX = re.compile(r"^(.*) \((\d{2})\)$")


def download(year: int) -> pathlib.Path:
    RAW.mkdir(parents=True, exist_ok=True)
    csv_path = RAW / f"SR{year}.csv"
    if not csv_path.exists():
        print(f"downloading {year}...")
        blob = requests.get(SOURCES[year], timeout=120).content
        zipfile.ZipFile(io.BytesIO(blob)).extractall(RAW)
    return csv_path


def fix_row(row: list[str]) -> list[str]:
    """Repair rows split by an unquoted comma in Division or Section."""
    if len(row) == 9:
        return row
    if len(row) == 10:
        if f"{row[7]},{row[8]}" in COMMA_DIVISIONS:
            return row[:7] + [f"{row[7]},{row[8]}", row[9]]
        return row[:8] + [f"{row[8]},{row[9]}"]          # comma inside Section
    raise ValueError(f"unexpected row with {len(row)} fields: {row}")


def read_rows(path: pathlib.Path):
    # Files are Windows-1252, not UTF-8 (accented street names break a UTF-8 read).
    with open(path, encoding="cp1252", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for raw in reader:
            yield fix_row(raw)


def main():
    rows, wards, types = [], {}, set()
    for year in SOURCES:
        for created, status, fsa, st1, st2, ward, rtype, division, section in read_rows(download(year)):
            m = WARD_RX.match(ward)
            ward_id = None
            if m:
                ward_id = int(m.group(2))
                wards[ward_id] = m.group(1)
            rtype = rtype.strip()
            types.add(rtype)
            if fsa == "Intersection":        # location was an intersection, not a postal code
                fsa = None
            rows.append((created[:19], status, fsa or None, st1 or None, st2 or None,
                         ward_id, rtype, division.strip(), section.strip()))
    print(f"parsed {len(rows):,} requests, {len(wards)} wards, {len(types)} request types")

    with psycopg.connect(ADMIN_DSN) as con:
        con.execute((ROOT / "sql" / "schema.sql").read_text())
        with con.cursor() as cur:
            cur.executemany("INSERT INTO wards VALUES (%s, %s)", sorted(wards.items()))
            cur.executemany("INSERT INTO request_types VALUES (%s, %s)",
                            [(t, topic_for(t)) for t in sorted(types)])
            with cur.copy("COPY service_requests (created_at, status, postal_fsa, intersection_street_1, "
                          "intersection_street_2, ward_id, request_type, division, section) FROM STDIN") as cp:
                for r in rows:
                    cp.write_row(r)
        con.execute("ANALYZE")
    print("loaded.")


if __name__ == "__main__":
    main()
