"""
batch_report.py — Batch runner + quality statistics

Usage:
    # Layer 1 only (fast, no API calls):
    python batch_report.py data/raw/

    # Layer 1 + 2 (LLM enrichment, rate-limited):
    python batch_report.py data/raw/ --enrich

    # Output to specific directory:
    python batch_report.py data/raw/ --enrich --out data/clean/
"""

import json
import time
import argparse
import csv
from pathlib import Path
from datetime import datetime

# Fields to track in quality report
TRACKED_FIELDS = [
    "excipient_name",
    "synonyms",
    "description",
    "roles",
    "dosage_forms",
    "incompatibilities",
    "compatibilities",
    "stability_notes",
    "ph_sensitivity",
    "temperature_sensitivity",
    "toxicity_notes",
    "regulatory_status",
    "processing_notes",
    "storage_conditions",
    "cross_references",
]

# Groq free tier: ~6,000 tokens/min for llama-3.3-70b
# Each excipient prompt ~1500-2000 tokens → safe to do 2-3 per minute
RATE_LIMIT_SLEEP = 22  # seconds between enriched requests (~2.7/min, conservative)


def is_empty(value) -> bool:
    """Check if a field value is considered empty."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def score_excipient(extracted: dict) -> dict:
    """
    Calculate per-field fill status and overall health score for one excipient.
    Returns dict with field statuses and summary stats.
    """
    field_status = {}
    filled = 0

    for field in TRACKED_FIELDS:
        value = extracted.get(field)
        empty = is_empty(value)
        field_status[field] = "❌" if empty else "✅"
        if not empty:
            filled += 1

    health_pct = round(filled / len(TRACKED_FIELDS) * 100)

    return {
        "field_status": field_status,
        "filled":       filled,
        "total":        len(TRACKED_FIELDS),
        "health_pct":   health_pct,
    }


def run_batch(
    input_dir: Path,
    output_dir: Path,
    enrich: bool,
) -> list[dict]:
    """
    Process all *.json files in input_dir.
    Returns list of per-excipient report rows.
    """
    from pipeline import run  # import here to avoid circular deps

    files = sorted(input_dir.glob("*.json"))
    if not files:
        print(f"⚠️  No JSON files found in {input_dir}")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    report_rows = []

    print(f"\n🚀 Batch processing {len(files)} excipients")
    print(f"   Enrichment: {'✅ Layer 1+2' if enrich else '⬜ Layer 1 only'}")
    print(f"   Output dir: {output_dir}")
    if enrich:
        print(f"   Rate limit delay: {RATE_LIMIT_SLEEP}s between requests")
    print("─" * 60)

    for i, f in enumerate(files, 1):
        excipient_name = f.stem
        status_prefix = f"  [{i:>3}/{len(files)}] {excipient_name:<30}"

        try:
            out_file = output_dir / f.name
            if out_file.exists():
                print(f"{status_prefix} ⏭️  SKIP")
                continue
            raw = json.loads(f.read_text(encoding="utf-8"))
            result = run(raw, enrich=enrich)

            # Save clean output
            out_file.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            # Score quality
            score = score_excipient(result["extracted"])
            health = score["health_pct"]
            health_icon = "🟢" if health >= 80 else "🟡" if health >= 50 else "🔴"

            print(f"{status_prefix} {health_icon} {health:>3}%")

            # Collect report row
            row = {
                "excipient":  excipient_name,
                "health_pct": health,
                "filled":     score["filled"],
                "total":      score["total"],
                "annotator":  result["meta"].get("annotator", ""),
                "error":      "",
            }
            for field in TRACKED_FIELDS:
                row[f"field_{field}"] = score["field_status"][field]

            report_rows.append(row)

            # Rate limiting for enriched runs
            if enrich and i < len(files):
                time.sleep(RATE_LIMIT_SLEEP)

        except Exception as e:
            print(f"{status_prefix} 💥 ERROR: {e}")
            report_rows.append({
                "excipient":  excipient_name,
                "health_pct": 0,
                "filled":     0,
                "total":      len(TRACKED_FIELDS),
                "annotator":  "",
                "error":      str(e),
                **{f"field_{f}": "💥" for f in TRACKED_FIELDS},
            })

    return report_rows


def print_summary(rows: list[dict]) -> None:
    """Print terminal summary table."""
    if not rows:
        return

    total = len(rows)
    errors = sum(1 for r in rows if r["error"])
    avg_health = round(sum(r["health_pct"] for r in rows) / total)

    green  = sum(1 for r in rows if r["health_pct"] >= 80)
    yellow = sum(1 for r in rows if 50 <= r["health_pct"] < 80)
    red    = sum(1 for r in rows if r["health_pct"] < 50 and not r["error"])

    print("\n\n📊 Batch Summary")
    print("=" * 60)
    print(f"  Total excipients : {total}")
    print(f"  Avg health score : {avg_health}%")
    print(f"  🟢 ≥80%          : {green}")
    print(f"  🟡 50-79%        : {yellow}")
    print(f"  🔴 <50%          : {red}")
    print(f"  💥 Errors        : {errors}")

    # Per-field fill rate across all excipients
    print("\n📋 Field Fill Rate (across all excipients)")
    print("─" * 45)
    for field in TRACKED_FIELDS:
        col = f"field_{field}"
        filled = sum(1 for r in rows if r.get(col) == "✅")
        pct = round(filled / total * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        status = "🟢" if pct >= 80 else "🟡" if pct >= 50 else "🔴"
        print(f"  {status} {field:<28} {bar} {pct:>3}%")

    # Bottom 10 excipients (worst health)
    worst = sorted(
        [r for r in rows if not r["error"]],
        key=lambda r: r["health_pct"]
    )[:10]
    if worst:
        print("\n⚠️  Lowest Quality Excipients (top 10)")
        print("─" * 45)
        for r in worst:
            print(f"  🔴 {r['excipient']:<35} {r['health_pct']:>3}%")


def save_csv(rows: list[dict], output_dir: Path) -> Path:
    """Save full report to CSV."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"quality_report_{ts}.csv"

    if not rows:
        return csv_path

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input",   help="Directory containing raw JSON files")
    parser.add_argument("--enrich", action="store_true", help="Run Layer 2 LLM enrichment")
    parser.add_argument("--out",    default=None,         help="Output directory (default: input/../clean)")
    args = parser.parse_args()

    input_dir  = Path(args.input)
    output_dir = Path(args.out) if args.out else input_dir.parent / "clean"

    rows = run_batch(input_dir, output_dir, enrich=args.enrich)

    print_summary(rows)

    csv_path = save_csv(rows, output_dir)
    print(f"\n💾 CSV report saved → {csv_path}")


if __name__ == "__main__":
    main()
