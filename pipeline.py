"""
pipeline.py — Main entry point

Usage:
    # Single file, Layer 1 only:
    python pipeline.py input.json

    # Single file, Layer 1 + 2:
    python pipeline.py input.json --enrich

    # Batch:
    python pipeline.py data/raw/ --enrich --batch
"""

import json
import argparse
from datetime import date
from pathlib import Path

from layer1.normalizer import normalize
from layer1.extractor  import extract


def run(raw_json: dict, enrich: bool = False) -> dict:
    """Full pipeline: normalize → extract → (optionally) enrich."""

    # Step 1: normalize OCR noise
    normalized = normalize(raw_json)

    # Step 2: rule-based extraction
    extracted, provenance = extract(normalized)

    result = {
        "meta": {
            "excipient_name":  extracted["excipient_name"],
            "source":          "Handbook of Pharmaceutical Excipients",
            "extraction_date": str(date.today()),
            "schema_version":  "1.0",
            "annotator":       "layer1_rule",
        },
        "raw":        raw_json,
        "extracted":  extracted,
        "provenance": provenance,
    }

    # Step 3: LLM enrichment (optional)
    if enrich:
        from layer2.llm_enricher import enrich as llm_enrich
        result = llm_enrich(result)

    return result


def evaluate(result: dict, gold_path: Path) -> None:
    """Print per-field evaluation against a gold record."""
    gold = json.loads(gold_path.read_text())["extracted"]
    ext  = result["extracted"]

    print("\n── Evaluation vs Gold ──────────────────────────")
    for field, g_val in gold.items():
        e_val = ext.get(field)
        if isinstance(g_val, list):
            g_set = {v.lower() for v in g_val}
            e_set = {v.lower() for v in (e_val or [])}
            p = round(len(g_set & e_set) / len(e_set), 2) if e_set else 0.0
            r = round(len(g_set & e_set) / len(g_set), 2) if g_set else 1.0
            ok = "✅" if g_set == e_set else "❌"
            missing = sorted(g_set - e_set)
            extra   = sorted(e_set - g_set)
            print(f"  {ok} {field:<28} P={p} R={r}"
                  + (f"  missing={missing}" if missing else "")
                  + (f"  extra={extra}"     if extra   else ""))
        else:
            g_words = set((g_val or "").lower().split())
            e_words = set((e_val or "").lower().split())
            overlap = round(len(g_words & e_words) / len(g_words), 2) if g_words else 1.0
            ok = "✅" if overlap > 0.6 else "❌"
            print(f"  {ok} {field:<28} overlap={overlap}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input",  help="Raw JSON file or directory (with --batch)")
    parser.add_argument("--enrich", action="store_true", help="Run Layer 2 LLM enrichment")
    parser.add_argument("--batch",  action="store_true", help="Process all *.json in directory")
    parser.add_argument("--gold",   help="Gold record JSON for evaluation")
    args = parser.parse_args()

    input_path = Path(args.input)

    if args.batch:
        files = sorted(input_path.glob("*.json"))
        print(f"Batch: {len(files)} files")
        for f in files:
            out = input_path.parent / "clean" / f.name
            out.parent.mkdir(exist_ok=True)
            result = run(json.loads(f.read_text()), enrich=args.enrich)
            out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            print(f"  ✅ {f.name} → {out}")
    else:
        raw = json.loads(input_path.read_text())
        result = run(raw, enrich=args.enrich)
        out = input_path.with_stem(input_path.stem + "_clean")
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"✅ Written to {out}")

        if args.gold:
            evaluate(result, Path(args.gold))
