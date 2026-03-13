#!/usr/bin/env python3
import json, sys, csv, re
from pathlib import Path

raw_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw")
contents_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None
sections = [str(i) for i in range(1, 23)]
output = Path("raw_status.tsv")

def normalize(s):
    return re.sub(r'[\s\-\(\)/\'\.，,]', '', s).lower()

# 讀 curated
curated_file = Path("data/manual/raw_status_curated.tsv")
curated = {}
if curated_file.exists():
    with curated_file.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row.get("manual_checked_book_name"):
                curated[row["file_name"]] = row["manual_checked_book_name"]

# 讀 contents
book = {}  # normalize(name) -> (name, page)
if contents_file and contents_file.exists():
    with contents_file.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            name = row["Item"].strip()
            book[normalize(name)] = (name, row["Page"].strip(), row["Category"].strip())

# 讀 raw JSONs
raw_records = {}  # normalize(name) -> record
rows = []
for f in sorted(raw_dir.glob("*.json")):
    data = json.loads(f.read_text())
    name = data.get("name", "N/A")
    found_nums = {k.split("_")[0] for k in data.get("sections", {}).keys()}
    missing = [s for s in sections if s not in found_nums]
    key = normalize(name)
    record = {
        "file_name": f.stem,
        "excipient_name": name,
        "file_path": str(f),
        "fields_found": 22 - len(missing),
        "fields_missing": len(missing),
        "missing_sections": ", ".join(missing) if missing else "-",
        "book_name": "",
        "page": "",
        "category": "",
        "in_contents": "no" if contents_file else "n/a",
        "manual_checked_book_name": curated.get(f.stem, ""),
        "manual_checked_page": "",
        "manual_checked_category": "",
    }
    if contents_file:
        if key in book:
            record["book_name"] = book[key][0]
            record["page"] = book[key][1]
            record["category"] = book[key][2]
            record["in_contents"] = "yes"
    raw_records[key] = record
    # curated info
    manual_name = curated.get(f.stem, "")
    if manual_name:
        manual_key = normalize(manual_name)
        if manual_key in book:
            record["manual_checked_page"] = book[manual_key][1]
            record["manual_checked_category"] = book[manual_key][2]
    rows.append(record)

# contents 有但 raw 沒有的
if contents_file:
    # add additional columns
    for key, (name, page, category) in book.items():
        if key not in raw_records:
            rows.append({
                "file_name": "MISSING",
                "excipient_name": "",
                "file_path": "",
                "fields_found": 0,
                "fields_missing": 22,
                "missing_sections": "all",
                "book_name": name,
                "page": page,
                "category": next((v[2] for v in book.values() if v[0] == name), ""),
                "in_contents": "missing_from_raw",
            })

with output.open("w", newline="") as f:
    cols = ["file_name", "excipient_name", "file_path", "fields_found", "fields_missing", "missing_sections", "book_name", "page", "category", "in_contents", "manual_checked_book_name", "manual_checked_page", "manual_checked_category"]
    writer = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)

print(f"saved → {output}  ({len(rows)} rows)")
if contents_file:
    missing_count = sum(1 for r in rows if r["in_contents"] == "missing_from_raw")
    print(f"  in contents but missing from raw: {missing_count}")