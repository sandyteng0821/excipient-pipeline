"""
pubchem_utils.py — Fetch physicochemical properties from PubChem.

Setup:
    pip install requests

Supports lookup by:
    - Compound name  (e.g. "aspirin", "microcrystalline cellulose")
    - CAS number     (e.g. "50-78-2")
    - SMILES         (e.g. "CC(=O)Oc1ccccc1C(=O)O")

Usage:
    python pubchem_utils.py                              # run demo batch
    python pubchem_utils.py aspirin                      # single compound
    python pubchem_utils.py 50-78-2 --input-type cas     # by CAS number
    python pubchem_utils.py --show-raw aspirin           # show raw API response

    from pubchem_utils import get_properties, batch_fetch

    props = get_properties("aspirin")
    results = batch_fetch(["aspirin", "magnesium stearate"])
    results = batch_fetch(["50-78-2", "557-04-0"], input_type="cas")

NOTE: pKa is not available via PubChem REST — use ChEMBL or DrugBank if needed.
      Polymers / mixtures (e.g. HPMC, MCC) may return no CID or incomplete data.
"""

import json
import time
import argparse
import requests
from pathlib import Path
from typing import TypedDict, Literal

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Types ─────────────────────────────────────────────────────────────────────

InputType = Literal["name", "cas", "smiles"]

class CompoundProperties(TypedDict):
    query: str                  # original input
    input_type: InputType
    cid: int                    # PubChem CID
    molecular_formula: str
    molecular_weight: float     # g/mol
    smiles: str                 # IsomericSMILES
    inchi_key: str
    xlogp: float | None         # lipophilicity — affects membrane permeability
    tpsa: float | None          # topological polar surface area — absorption predictor
    hbd: int | None             # H-bond donors
    hba: int | None             # H-bond acceptors
    rotatable_bonds: int | None
    complexity: float | None
    charge: int | None
    pubchem_url: str

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Formulation-relevant physicochemical properties
PROPERTY_FIELDS = [
    "MolecularFormula",
    "MolecularWeight",
    "IsomericSMILES",
    "InChIKey",
    "XLogP",                # lipophilicity
    "TPSA",                 # polar surface area
    "HBondDonorCount",
    "HBondAcceptorCount",
    "RotatableBondCount",
    "Complexity",
    "Charge",
]
PROPERTY_QUERY = ",".join(PROPERTY_FIELDS)

DEFAULT_COMPOUNDS = [
    # APIs
    "aspirin",
    "metformin",
    "ibuprofen",
    # Excipients
    "microcrystalline cellulose",
    "magnesium stearate",
    "mannitol",
    "povidone",
    "polysorbate 80",
]

# ── Core API ──────────────────────────────────────────────────────────────────

def _get_cid(query: str, input_type: InputType) -> int | None:
    """Resolve a name / CAS / SMILES to a PubChem CID."""
    namespace = {
        "name":   "name",
        "cas":    "name",       # CAS goes through /name/ endpoint
        "smiles": "smiles",
    }[input_type]

    url = f"{BASE_URL}/compound/{namespace}/{requests.utils.quote(query)}/cids/JSON"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        cids = resp.json().get("IdentifierList", {}).get("CID", [])
        return cids[0] if cids else None
    except Exception as e:
        print(f"  ❌ CID lookup failed for '{query}': {e}")
        return None


def _get_properties_by_cid(cid: int, query: str, input_type: InputType) -> CompoundProperties | None:
    """Fetch physicochemical properties for a known PubChem CID."""
    url = f"{BASE_URL}/compound/cid/{cid}/property/{PROPERTY_QUERY}/JSON"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        p = resp.json()["PropertyTable"]["Properties"][0]

        return CompoundProperties(
            query=query,
            input_type=input_type,
            cid=cid,
            molecular_formula=p.get("MolecularFormula", ""),
            molecular_weight=float(p.get("MolecularWeight", 0)),
            smiles=p.get("IsomericSMILES", "") or p.get("SMILES", ""),
            inchi_key=p.get("InChIKey", ""),
            xlogp=p.get("XLogP"),
            tpsa=p.get("TPSA"),
            hbd=p.get("HBondDonorCount"),
            hba=p.get("HBondAcceptorCount"),
            rotatable_bonds=p.get("RotatableBondCount"),
            complexity=p.get("Complexity"),
            charge=p.get("Charge"),
            pubchem_url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
        )
    except Exception as e:
        print(f"  ❌ Property fetch failed for CID {cid}: {e}")
        return None


def get_properties(
    query: str,
    input_type: InputType = "name",
) -> CompoundProperties | None:
    """
    Resolve name / CAS / SMILES and fetch physicochemical properties.

    Args:
        query:      compound name, CAS number, or SMILES string
        input_type: "name" | "cas" | "smiles"
    Returns:
        CompoundProperties dict, or None if not found / parse failed
    """
    cid = _get_cid(query, input_type)
    if not cid:
        print(f"  ❌ {query}  [NOT FOUND in PubChem]")
        return None
    return _get_properties_by_cid(cid, query, input_type)


def batch_fetch(
    queries: list[str],
    input_type: InputType = "name",
    delay: float = 0.5,
) -> list[CompoundProperties]:
    """
    Fetch properties for a list of compound names, CAS numbers, or SMILES.

    Args:
        queries:    list of compound identifiers
        input_type: "name" | "cas" | "smiles" — applies to all queries
        delay:      seconds between requests (PubChem rate limit: 5 req/s)
    Returns:
        list of successfully parsed CompoundProperties dicts
    """
    results = []
    for q in queries:
        print(f"  Fetching: {q}")
        props = get_properties(q, input_type)
        if props:
            results.append(props)
        time.sleep(delay)
    return results


# ── Display ───────────────────────────────────────────────────────────────────

def format_value(value) -> str:
    if value is None:
        return "—"
    return str(value)


def print_properties(p: CompoundProperties, show_raw: bool = False) -> None:
    smiles_display = p["smiles"][:60] + "..." if len(p["smiles"]) > 60 else p["smiles"]

    print(f"\n{'─'*60}")
    print(f"  🧪 {p['query'].upper()}  (CID: {p['cid']})")
    print(f"  {'─'*58}")
    print(f"  {'Formula':<24} {p['molecular_formula']}")
    print(f"  {'MW':<24} {p['molecular_weight']} g/mol")
    print(f"  {'SMILES':<24} {smiles_display}")
    print(f"  {'XLogP':<24} {format_value(p['xlogp'])}  (lipophilicity)")
    print(f"  {'TPSA':<24} {format_value(p['tpsa'])} Å²  (polar surface area)")
    print(f"  {'HBD / HBA':<24} {format_value(p['hbd'])} / {format_value(p['hba'])}")
    print(f"  {'Rotatable bonds':<24} {format_value(p['rotatable_bonds'])}")
    print(f"  {'Charge':<24} {format_value(p['charge'])}")
    print(f"  {'PubChem URL':<24} {p['pubchem_url']}")

    if show_raw:
        print(f"\n  Raw data:")
        print(json.dumps(p, indent=4, ensure_ascii=False))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch physicochemical properties from PubChem")
    parser.add_argument(
        "query",
        nargs="?",
        help="Compound name, CAS number, or SMILES. Omit to run demo batch."
    )
    parser.add_argument(
        "--input-type", "-t",
        choices=["name", "cas", "smiles"],
        default="name",
        help="Input type (default: name)",
    )
    parser.add_argument(
        "--show-raw",
        action="store_true",
        help="Print raw dict output",
    )
    args = parser.parse_args()

    if args.query:
        props = get_properties(args.query, input_type=args.input_type)
        if props:
            print_properties(props, show_raw=args.show_raw)
    else:
        print(f"\n📋 Demo batch: {DEFAULT_COMPOUNDS}\n")
        results = batch_fetch(DEFAULT_COMPOUNDS)
        print(f"\n{'═'*64}")
        for r in results:
            print_properties(r)
        print(f"\n✅ Fetched {len(results)} / {len(DEFAULT_COMPOUNDS)} compounds successfully.")


if __name__ == "__main__":
    main()
