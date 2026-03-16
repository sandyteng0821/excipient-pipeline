"""
query_drug.py — Demo query tool: 給藥品名稱，查詢所有 excipient 的 handbook 資訊
...
Setup:
    Requires at least one of:
        data/clean/             (Layer 1 + Layer 2, from batch_report.py --enrich)
        data/clean-layer1-only/ (Layer 1 only,      from batch_report.py)
...
Usage:
    python query_drug.py                          # 列出所有已定義的藥品
    python query_drug.py amlodipine               # 查詢藥品的所有 excipient
    python query_drug.py amlodipine --field roles # 只顯示特定欄位
    python query_drug.py amlodipine --field incompatibilities --field dosage_forms
    python query_drug.py --filter dosage_forms injection  # 找有 injection 的 excipient

NOTE: Excipient mapping 目前是手動對應（name normalization 尚未實作）
      不在資料庫內的 excipient 會標示為 NOT FOUND
"""

import json
import argparse
from pathlib import Path
from rapidfuzz import process, fuzz

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))  # 讓 tools/ 下的檔案能 import 根目錄的 module

# ── 手動 mapping：藥品 => excipient file stems ────────────────────────────────
# key: 藥品名稱（小寫，用於 CLI 匹配）
# value: dict with label, url, excipients (file stem list)

DRUG_REGISTRY: dict[str, dict] = {
    "vyleesi": {
        "label": "VYLEESI (bremelanotide injection)",
        "url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=8c9607a2-5b57-4a59-b159-cf196deebdd9",
        "excipients": [
            "GLYCERIN",
            "WATER",
            "SODIUM HYDROXIDE",
            "HYDROCHLORIC ACID",
        ],
    },
    "amlodipine": {
        "label": "AMLODIPINE AND OLMESARTAN MEDOXOMIL (tablet, film coated)",
        "url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=99865c67-5475-4e60-98d5-a8fa850fe9ba",
        "excipients": [
            "CROSCARMELLOSE SODIUM",
            "MAGNESIUM STEARATE",
            #"CORN STARCH",
            "STARCH",  # corn starch → Starch (handbook uses generic name)
            "POLYETHYLENE GLYCOL 3350",
            "TITANIUM DIOXIDE",
            "TALC",
            "FERROSOFERRIC OXIDE",
            "MICROCRYSTALLINE CELLULOSE",
            "POLYVINYL ALCOHOL",
        ],
    },
}

# ── 顯示欄位設定 ──────────────────────────────────────────────────────────────
# 預設顯示的欄位（不指定 --field 時）
DEFAULT_FIELDS = [
    "roles",
    "dosage_forms",
    "incompatibilities",
    "ph_sensitivity",
    "processing_notes",
    "storage_conditions",
    "toxicity_notes",
]

# CLEAN_DIR = Path("data/clean")
CLEAN_DIR = Path(__file__).parent.parent / "data" / "clean"
CLEAN_DIR_L1 = Path(__file__).parent.parent / "data" / "clean-layer1-only"

def build_index() -> dict[str, str]:
    """Build {normalized_name: file_stem} index from all clean JSONs.
    Prefers data/clean/ (L1+L2), falls back to data/clean-layer1-only/ (L1 only).
    """
    index = {}
    # L1-only first (lower priority)
    for path in CLEAN_DIR_L1.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            extracted = data.get("extracted", {})
            stem = f"l1:{path.stem}"  # 標記來源
            name = extracted.get("excipient_name", "")
            if name:
                index[name.lower()] = stem
            for syn in extracted.get("synonyms", []):
                if syn:
                    index[syn.lower()] = stem
        except Exception:
            continue

    # L1+L2 second (higher priority, overwrites L1-only)
    for path in CLEAN_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            extracted = data.get("extracted", {})
            stem = f"l2:{path.stem}"
            name = extracted.get("excipient_name", "")
            if name:
                index[name.lower()] = stem
            for syn in extracted.get("synonyms", []):
                if syn:
                    index[syn.lower()] = stem
        except Exception:
            continue

    return index


def resolve_excipient(name: str, index: dict) -> str | None:
    """
    Map a drug label ingredient name to a clean JSON file stem.
    Currently uses fuzzy matching — swap this function for UNII-based lookup later.

    Args:
        name:  Ingredient name from drug label (e.g. "POLYETHYLENE GLYCOL 3350")
        index: Dict of {normalized_name: file_stem} built from clean JSONs
    Returns:
        file stem (e.g. "PolyethyleneGlycol") or None if no match found
    """
    # result = process.extractOne(name.lower(), index.keys(), score_cutoff=80) # fuzzy matching
    result = process.extractOne(name.lower(), index.keys(), scorer=fuzz.token_sort_ratio, score_cutoff=80)
    if result:
        return index[result[0]]
    return None

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_excipient(stem: str) -> dict | None:
    if stem.startswith("l2:"):
        path = CLEAN_DIR / f"{stem[3:]}.json"
    elif stem.startswith("l1:"):
        path = CLEAN_DIR_L1 / f"{stem[3:]}.json"
    else:
        path = CLEAN_DIR / f"{stem}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def format_value(value) -> str:
    if isinstance(value, list):
        return ", ".join(value) if value else "—"
    return str(value) if value else "—"


def print_excipient(stem: str, fields: list[str]) -> None:
    data = load_excipient(stem)

    if data is None:
        print(f"\n  ❌ {stem}  [NOT FOUND in data/clean/]")
        return

    extracted = data.get("extracted", {})
    name = extracted.get("excipient_name", stem)
    annotator = data.get("meta", {}).get("annotator", "layer1")
    layer = "L1+L2" if "layer2" in annotator else "L1 only"

    print(f"\n  {'─'*60}")
    print(f"  📦 {name}  [{layer}]")

    for field in fields:
        value = extracted.get(field)
        label = field.replace("_", " ").title()
        print(f"  {label:<24} {format_value(value)}")


def print_drug(drug_key: str, fields: list[str]) -> None:
    drug = DRUG_REGISTRY[drug_key]
    index = build_index()  # ← 加這行

    print(f"\n{'═'*64}")
    print(f"💊 {drug['label']}")
    print(f"   {drug['url']}")
    print(f"{'═'*64}")
    print(f"Excipients ({len(drug['excipients'])}):")

    for raw_name in drug["excipients"]:
        stem = resolve_excipient(raw_name, index)  # ← 這行
        if stem:
            print_excipient(stem, fields)
        else:
            print(f"\n  ❌ {raw_name}  [NOT FOUND — no fuzzy match]")

    print()


def filter_excipients(field: str, value: str) -> None:
    """Find all excipients where field contains value."""
    matches = []
    for path in sorted(CLEAN_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            extracted = data.get("extracted", {})
            field_val = extracted.get(field, [])
            if isinstance(field_val, list):
                if any(value.lower() in str(v).lower() for v in field_val):
                    matches.append(extracted.get("excipient_name", path.stem))
            elif isinstance(field_val, str):
                if value.lower() in field_val.lower():
                    matches.append(extracted.get("excipient_name", path.stem))
        except Exception:
            continue

    print(f"\n🔍 Excipients where `{field}` contains '{value}' ({len(matches)} found):")
    for name in matches:
        print(f"  • {name}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Query excipient data by drug name")
    parser.add_argument(
        "drug",
        nargs="?",
        help="Drug name (e.g. amlodipine, vyleesi). Omit to list all drugs."
    )
    parser.add_argument(
        "--field", "-f",
        action="append",
        dest="fields",
        help="Field(s) to display (default: roles, dosage_forms, incompatibilities, ...)"
    )
    parser.add_argument(
        "--filter",
        nargs=2,
        metavar=("FIELD", "VALUE"),
        help="Filter all excipients by field value (e.g. --filter dosage_forms injection)"
    )
    args = parser.parse_args()

    # --filter mode
    if args.filter:
        filter_excipients(args.filter[0], args.filter[1])
        return

    # list all drugs
    if not args.drug:
        print("\n📋 Available drugs:")
        for key, drug in DRUG_REGISTRY.items():
            print(f"  {key:<20} {drug['label']}")
        print("\nUsage: python query_drug.py <drug_name>")
        return

    # query drug
    drug_key = args.drug.lower()
    if drug_key not in DRUG_REGISTRY:
        print(f"❌ Drug '{args.drug}' not found. Available: {list(DRUG_REGISTRY.keys())}")
        raise SystemExit(1)

    fields = args.fields if args.fields else DEFAULT_FIELDS
    print_drug(drug_key, fields)


if __name__ == "__main__":
    main()