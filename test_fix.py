"""
test_fix.py — 針對特定 excipient 測試 pipeline，可指定 output path

Usage:
    # 測試單一檔案
    python test_fix.py data/raw/LacticAcid.json

    # 測試單一檔案 + Layer 2 enrichment
    python test_fix.py data/raw/LacticAcid.json --enrich

    # 指定 output 路徑
    python test_fix.py data/raw/LacticAcid.json --enrich --out data/test_output/

    # 一次測試多個檔案
    python test_fix.py data/raw/LacticAcid.json data/raw/Methylparaben.json data/raw/MineralOil.json --enrich
"""

import json
import argparse
from pathlib import Path

from pipeline import run


DEFAULT_TEST_FILES = [
    "data/raw/LacticAcid.json",
    "data/raw/Methylparaben.json",
    "data/raw/MineralOil.json",
]


def test_one(raw_path: Path, out_dir: Path, enrich: bool) -> bool:
    """
    Run pipeline on a single file, write result to out_dir.
    Returns True if successful, False if an exception occurred.
    """
    print(f"\n{'─'*50}")
    print(f"▶  {raw_path.name}")

    try:
        raw = json.loads(raw_path.read_text())
        result = run(raw, enrich=enrich)

        # Write output
        out_path = out_dir / raw_path.name
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

        # Spot-check: dosage_forms type
        dosage_forms = result.get("extracted", {}).get("dosage_forms", [])
        bad_items = [x for x in dosage_forms if not isinstance(x, str)]

        if bad_items:
            print(f"   ⚠️  dosage_forms 仍有非 string 項目：")
            for item in bad_items:
                print(f"      {type(item).__name__}: {item}")
            return False

        print(f"   ✅ dosage_forms OK ({len(dosage_forms)} items)")
        for item in dosage_forms:
            print(f"      • {item}")
        print(f"   📄 output → {out_path}")
        return True

    except Exception as e:
        print(f"   💥 ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test pipeline.run() with custom output path")
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Raw JSON files to test. Defaults to the 3 known-failing excipients."
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Run Layer 2 LLM enrichment"
    )
    parser.add_argument(
        "--out",
        default="data/test_output",
        help="Output directory for results (default: data/test_output/)"
    )
    args = parser.parse_args()

    # Resolve input files
    input_files = [Path(p) for p in args.inputs] if args.inputs else [Path(p) for p in DEFAULT_TEST_FILES]

    # Validate inputs exist
    missing = [p for p in input_files if not p.exists()]
    if missing:
        for p in missing:
            print(f"❌ File not found: {p}")
        raise SystemExit(1)

    # Prepare output dir
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Run tests
    results = {p: test_one(p, out_dir, enrich=args.enrich) for p in input_files}

    # Summary
    passed = sum(results.values())
    total  = len(results)
    print(f"\n{'='*50}")
    print(f"結果：{passed}/{total} passed")
    for p, ok in results.items():
        icon = "✅" if ok else "💥"
        print(f"  {icon} {p.name}")


if __name__ == "__main__":
    main()