"""
report_all.py — Generate aggregate quality report from all clean JSONs in a folder.

Unlike batch_report.py (which only reports on the current run),
this script reads ALL existing clean JSONs and produces a full report.

Usage:
    python report_all.py                        # default: data/clean/
    python report_all.py data/clean/            # explicit path
    python report_all.py data/clean/ --no-csv   # terminal only, no CSV saved
"""

import json
import argparse
from pathlib import Path

from batch_report import score_excipient, print_summary, save_csv


def load_clean_jsons(clean_dir: Path) -> list[dict]:
    """Read all clean JSONs and score each one."""
    files = sorted(clean_dir.glob("*.json"))
    # exclude quality_report CSVs accidentally saved as json, and temp files
    files = [f for f in files if not f.name.startswith("quality_report")]

    if not files:
        print(f"⚠️  No clean JSONs found in {clean_dir}")
        return []

    rows = []
    errors = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            extracted = data.get("extracted", {})
            error = data.get("meta", {}).get("error", "")
            row = score_excipient(extracted)
            row["excipient"] = f.stem
            row["annotator"] = data.get("meta", {}).get("annotator", "")
            row["error"] = error
            # reorder: excipient first
            rows.append({"excipient": row.pop("excipient"), **row})
        except Exception as e:
            errors.append((f.name, str(e)))

    if errors:
        print(f"\n⚠️  Could not parse {len(errors)} file(s):")
        for name, err in errors:
            print(f"   {name}: {err}")

    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate quality report from all clean JSONs"
    )
    parser.add_argument(
        "clean_dir",
        nargs="?",
        default="data/clean",
        help="Directory containing clean JSONs (default: data/clean/)",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Print summary only, do not save CSV",
    )
    args = parser.parse_args()

    clean_dir = Path(args.clean_dir)
    if not clean_dir.exists():
        print(f"❌ Directory not found: {clean_dir}")
        raise SystemExit(1)

    rows = load_clean_jsons(clean_dir)
    if not rows:
        raise SystemExit(1)

    print(f"\n📂 Loaded {len(rows)} excipients from {clean_dir}")
    print_summary(rows)

    if not args.no_csv:
        csv_path = save_csv(rows, clean_dir)
        print(f"\n💾 CSV report saved → {csv_path}")


if __name__ == "__main__":
    main()