"""
dailymed_utils.py — Fetch drug formulation data (API + inactive ingredients) from DailyMed.

Setup:
    pip install requests rapidfuzz

Usage:
    python dailymed_utils.py                        # run demo batch (5 drugs)
    python dailymed_utils.py aspirin                # single drug lookup
    python dailymed_utils.py aspirin --show-raw     # show raw API response
    python dailymed_utils.py aspirin --sampled 5    # fetch 5 SPLs

    from dailymed_utils import get_drug_formulation, batch_fetch

    result = get_drug_formulation("aspirin")
    results = batch_fetch(["aspirin", "metformin", "ibuprofen"])

NOTE: Drug name matching uses DailyMed's own search — first result is returned by default.
      Use --pick / pick_index to select a different result if the first hit is not what you want.
"""

import json
import time
import argparse
import requests
import xml.etree.ElementTree as ET

from pathlib import Path
from typing import TypedDict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Types ─────────────────────────────────────────────────────────────────────

class ActiveIngredient(TypedDict):
    name: str
    strength: str

class Product(TypedDict):
    product_name: str
    dosage_form: str
    route: str                          # from XML routeCode
    manufacturer: str                   # 廠商名稱
    ndc: str                            # NDC code (unique per manufacturer + strength)    
    active_ingredients: list[ActiveIngredient]
    inactive_ingredients: list[str]

class DrugFormulation(TypedDict):
    drug_name: str                      # query name (input)
    set_id: str                         # DailyMed SPL set ID
    spl_version: str
    label: str                          # full label title
    products: list[Product]             # per-product breakdown
    label_url: str

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2"

DEFAULT_DRUGS = [
    "aspirin",
    "metformin",
    "ibuprofen",
    "lisinopril",
    "atorvastatin",
]

# ── Core API ──────────────────────────────────────────────────────────────────

def _search(drug_name: str, limit: int = 5) -> list[dict]:
    """Search DailyMed SPL index by drug name."""
    resp = requests.get(
        f"{BASE_URL}/spls.json",
        params={"drug_name": drug_name, "pagesize": limit},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])

def _get_spl(set_id: str) -> dict:
    resp = requests.get(f"{BASE_URL}/spls/{set_id}.xml", timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)

    products = []
    # ── 新增 1: manufacturer ──────────────────────────────────
    mfr_el = root.find(".//{urn:hl7-org:v3}representedOrganization/{urn:hl7-org:v3}name")
    manufacturer = mfr_el.text.strip() if mfr_el is not None else ""

    for outer in root.findall(".//{urn:hl7-org:v3}manufacturedProduct"):
        inner = outer.find("{urn:hl7-org:v3}manufacturedProduct")
        if inner is None:
            continue

        active, inactive = [], []

        form_el = inner.find(".//{urn:hl7-org:v3}formCode")
        dosage_form = form_el.get("displayName", "") if form_el is not None else ""

        name_el = inner.find("{urn:hl7-org:v3}name")
        product_name = name_el.text.strip() if name_el is not None else ""

        route_el = outer.find(".//{urn:hl7-org:v3}consumedIn//{urn:hl7-org:v3}routeCode")
        route = route_el.get("displayName", "") if route_el is not None else ""

        # ── 新增 2: NDC ───────────────────────────────────────────
        ndc_el = inner.find("{urn:hl7-org:v3}code")
        ndc = ndc_el.get("code", "") if ndc_el is not None else ""

        for ingredient in inner.iter("{urn:hl7-org:v3}ingredient"):
            class_code = ingredient.get("classCode", "")
            iname = ingredient.find(".//{urn:hl7-org:v3}ingredientSubstance/{urn:hl7-org:v3}name")
            if iname is None or not iname.text:
                continue
            if class_code == "IACT":
                inactive.append(iname.text.strip())
            elif class_code in ("ACTIB", "ACTIM"):
                numerator = ingredient.find(".//{urn:hl7-org:v3}quantity/{urn:hl7-org:v3}numerator")
                strength = ""
                if numerator is not None:
                    strength = f"{numerator.get('value', '')} {numerator.get('unit', '')}".strip()
                active.append({"name": iname.text.strip(), "strength": strength})

        if active or inactive:
            products.append(Product(
                product_name=product_name,
                dosage_form=dosage_form,
                route=route,
                manufacturer=manufacturer,      # ── 新增 3
                ndc=ndc,                        # ── 新增 4
                active_ingredients=active,
                inactive_ingredients=inactive,
            ))

    # # ── 新增 5: dedup（保留配方或劑量真正不同的）────────────────
    # seen = set()
    # unique_products = []
    # for p in products:
    #     key = (
    #         frozenset((a["name"], a["strength"]) for a in p["active_ingredients"]),
    #         frozenset(p["inactive_ingredients"]),
    #     )
    #     if key not in seen:
    #         seen.add(key)
    #         unique_products.append(p)

    # return {"products": unique_products}
    return {"products": products}

def parse_formulation(set_id: str, drug_name: str, hit: dict) -> DrugFormulation | None:
    try:
        detail = _get_spl(set_id)
        return DrugFormulation(
            drug_name=drug_name,
            set_id=set_id,
            spl_version="",
            label=hit.get("title", ""),
            products=detail["products"],
            label_url=f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}",
        )
    except Exception as e:
        print(f"  ❌ {drug_name}  [parse failed: {e}]")
        return None

def get_drug_formulation(drug_name: str, pick_index: int = 0) -> DrugFormulation | None:
    results = _search(drug_name, limit=pick_index + 1)
    if not results:
        print(f"  ❌ {drug_name}  [NOT FOUND in DailyMed]")
        return None
    hit = results[pick_index]
    set_id = hit.get("setid")
    if not set_id:
        return None
    return parse_formulation(set_id, drug_name, hit)

def get_drug_formulations_sampled(
    drug_name: str,
    max_spls: int = 10,
    delay: float = 0.3,
) -> list[DrugFormulation]:
    """
    Fetch multiple SPLs for a drug and return as a list of DrugFormulation.
    Each SPL = one manufacturer's label = one DrugFormulation.

    Args:
        drug_name: e.g. "aspirin"
        max_spls:  how many SPLs to fetch (default: 10)
        delay:     seconds between requests
    """
    hits = _search(drug_name, limit=max_spls)
    results = []
    for hit in hits:
        set_id = hit.get("setid")
        if not set_id:
            continue
        f = parse_formulation(set_id, drug_name, hit)
        if f:
            results.append(f)
        time.sleep(delay)
    return results

def batch_fetch(
    drug_names: list[str],
    delay: float = 0.5,
) -> list[DrugFormulation]:
    """
    Fetch formulations for a list of drug names.

    Args:
        drug_names: list of drug names
        delay:      seconds between requests (be polite to the API)
    Returns:
        list of successfully parsed DrugFormulation dicts
    """
    results = []
    for name in drug_names:
        print(f"  Fetching: {name}")
        formulation = get_drug_formulation(name)
        if formulation:
            results.append(formulation)
        time.sleep(delay)
    return results


# ── Excipient resolver (mirrors query_drug.py) ────────────────────────────────

def resolve_excipients(
    formulation: DrugFormulation,
    index: dict[str, str],
) -> dict[str, str | None]:
    """
    Map inactive ingredient names from a drug label to excipient JSON stems.
    Mirrors resolve_excipient() in query_drug.py.

    Args:
        formulation: DrugFormulation dict
        index:       {normalized_name: file_stem} from query_drug.build_index()
    Returns:
        {raw_ingredient_name: stem_or_None}
    """
    from rapidfuzz import process, fuzz
    
    all_inactive = set()
    for product in formulation["products"]:
        all_inactive.update(product["inactive_ingredients"])

    mapping = {}
    for raw_name in all_inactive:
        result = process.extractOne(
            raw_name.lower(),
            index.keys(),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=80,
        )
        mapping[raw_name] = index[result[0]] if result else None
    return mapping


# ── Display ───────────────────────────────────────────────────────────────────

def print_formulation(f: DrugFormulation, show_raw: bool = False) -> None:
    print(f"\n{'═'*64}")
    print(f"💊 {f['drug_name'].upper()}")
    print(f"   {f['label']}")
    print(f"   {f['label_url']}")
    print(f"{'═'*64}")
    
    # show per-product information
    for i, p in enumerate(f["products"], 1):
        print(f"\n  Product {i}: {p['product_name']}  [{p['dosage_form']}]  {p['route']}")
        print(f"  NDC: {p['ndc']}  |  {p['manufacturer']}")
        print(f"  {'─'*60}")
        print(f"  Active ({len(p['active_ingredients'])}):")
        for a in p["active_ingredients"]:
            print(f"    • {a['name']}  {a['strength']}")
        print(f"  Inactive ({len(p['inactive_ingredients'])}):")
        for ii in p["inactive_ingredients"]:
            print(f"    • {ii}")

    if show_raw:
        print(f"\n  Raw data:")
        print(json.dumps(f, indent=4, ensure_ascii=False))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch drug formulation data from DailyMed")
    parser.add_argument(
        "drug",
        nargs="?",
        help="Drug name (e.g. aspirin). Omit to run demo batch."
    )
    parser.add_argument(
        "--show-raw",
        action="store_true",
        help="Print raw JSON response",
    )
    parser.add_argument(
        "--pick", "-p",
        type=int,
        default=0,
        help="Which search result to use (default: 0 = first hit)",
    )
    parser.add_argument(
        "--sampled", "-s",
        type=int,
        default=0,
        metavar="N",
        help="Fetch N SPLs instead of just the first (e.g. --sampled 5)",
    )    
    args = parser.parse_args()

    if args.drug:
        if args.sampled:
            formulations = get_drug_formulations_sampled(args.drug, max_spls=args.sampled)
            for f in formulations:
                print_formulation(f, show_raw=args.show_raw)
            print(f"\n✅ Fetched {len(formulations)} SPLs for '{args.drug}'.")
        else:
            f = get_drug_formulation(args.drug, pick_index=args.pick)
            if f:
                print_formulation(f, show_raw=args.show_raw)
    else:
        print(f"\n📋 Demo batch: {DEFAULT_DRUGS}\n")
        formulations = batch_fetch(DEFAULT_DRUGS)
        for f in formulations:
            print_formulation(f)
        print(f"\n✅ Fetched {len(formulations)} / {len(DEFAULT_DRUGS)} drugs successfully.")


if __name__ == "__main__":
    main()
