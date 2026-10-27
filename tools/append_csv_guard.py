#!/usr/bin/env python3
"""
tools/append_csv_guard.py  —  L-ING-3 (S411, binding)

Every landed / non-landed / EC append CSV must carry postal_code as
6-character zero-padded TEXT. pandas reads postals as int and silently
drops the leading zero (S411: 078878 -> 78878, caught only at Gate B).

Use in an append builder:
    from append_csv_guard import write_append_csv
    write_append_csv(df, "landed_weekly_20261030_append.csv")

Or check a finished file before handing it over:
    python3 append_csv_guard.py landed_weekly_20261030_append.csv [more.csv ...]

C&I transactions.postal_code is INTEGER and is out of scope.
"""
import csv
import sys


def _pad(v):
    s = "" if v is None else str(v).strip()
    if s.endswith(".0"):            # float-coerced by pandas
        s = s[:-2]
    if s == "" or s.lower() == "nan":
        return s
    if not s.isdigit():
        raise ValueError(f"non-numeric postal_code: {v!r}")
    return s.zfill(6)


def write_append_csv(df, path):
    """Zero-pad postal_code, assert 6 chars on every row, write as text."""
    df = df.copy()
    df["postal_code"] = df["postal_code"].map(_pad)
    bad = df[df["postal_code"].str.len() != 6]
    if len(bad):
        raise AssertionError(
            f"L-ING-3: {len(bad)} row(s) without a 6-char postal_code:\n"
            + bad[["id", "address", "postal_code"]].to_string(index=False))
    df.to_csv(path, index=False)
    check_file(path)                 # re-read the bytes we wrote
    return path


def check_file(path):
    """Read the CSV as raw text and fail on any postal_code != 6 chars."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows or "postal_code" not in rows[0]:
        raise AssertionError(f"{path}: no postal_code column")
    bad = [(r.get("id"), r.get("address"), r["postal_code"])
           for r in rows if len(r["postal_code"]) != 6]
    if bad:
        lines = "\n".join(f"  id {i}  {a}  postal '{p}'" for i, a, p in bad)
        raise AssertionError(f"L-ING-3 FAIL {path}: {len(bad)} bad row(s)\n{lines}")
    print(f"L-ING-3 PASS {path}: {len(rows)} rows, all postal_code 6 chars")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rc = 0
    for p in sys.argv[1:]:
        try:
            check_file(p)
        except AssertionError as e:
            print(e)
            rc = 1
    sys.exit(rc)
