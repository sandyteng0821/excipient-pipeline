# tools/analyze_ontology_coverage.py
import json
from pathlib import Path
from collections import Counter

def analyze_coverage(raw_dir: str, ontology_path: str):
    ontology = json.loads(Path(ontology_path).read_text())
    all_synonyms = {
        term.lower()
        for synonyms in ontology["roles"].values()
        for term in synonyms
    }

    counter = Counter()
    unmatched = Counter()

    for path in Path(raw_dir).glob("*.json"):
        data = json.loads(path.read_text())
        section6 = data.get("sections", {}).get("6_Functional Category", "")
        terms = [t.strip().lower().rstrip(".;,") for t in section6.split(";")]
        for term in terms:
            if not term:
                continue
            counter[term] += 1
            if not any(s in term or term in s for s in all_synonyms):
                unmatched[term] += 1

    print("=== Top unmatched terms (not covered by ontology) ===")
    for term, count in unmatched.most_common(30):
        print(f"{count:3d}  {term}")

if __name__ == "__main__":
    analyze_coverage("data/raw", "config/ontology.json")