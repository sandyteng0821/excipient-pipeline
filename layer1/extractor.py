"""
layer1/extractor.py

Rule-based extraction for each schema field.
Reads ontology from config/ontology.json.
Uses normalizer.find_section() for robust section lookup.
"""

import re
import json
from pathlib import Path

from .normalizer import find_section


# Load ontology once
_ONTOLOGY_PATH = Path(__file__).parent.parent / "config" / "ontology.json"
_ONTOLOGY: dict = json.loads(_ONTOLOGY_PATH.read_text())


def _match_ontology(text: str, ontology_key: str) -> list[str]:
    """Return canonical terms whose keywords appear in text."""
    text_lower = text.lower()
    ontology = _ONTOLOGY[ontology_key]
    return [
        canonical
        for canonical, keywords in ontology.items()
        if any(kw in text_lower for kw in keywords)
    ]


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        if item.lower() not in seen and item.strip():
            seen.add(item.lower())
            out.append(item)
    return out


# ── Field extractors ──────────────────────────────────────────────────────────

def get_name(sections: dict, raw_name: str) -> str:
    """Prefer the top-level name field; fall back to section 1."""
    if raw_name:
        return raw_name
    text = find_section(sections, "Nonproprietary")
    first_line = text.strip().splitlines()[0] if text else ""
    # Strip "BP: " prefix if present
    return first_line.split(":", 1)[-1].strip().title() if first_line else ""


def get_synonyms(sections: dict) -> list[str]:
    text = find_section(sections, "Synonyms")
    if not text:
        return []
    # Synonyms are semicolon-delimited in the handbook
    parts = [p.strip().rstrip(".") for p in text.split(";")]
    return [p for p in parts if p]


def get_description(sections: dict) -> str:
    return find_section(sections, "Description")


def get_roles(sections: dict) -> list[str]:
    # Section 6 (Functional Category) is authoritative; section 7 supplements
    functional   = find_section(sections, "Functional Category")
    applications = find_section(sections, "Applications")
    combined = f"{functional} {applications}"
    return _match_ontology(combined, "roles")


def get_incompatibilities(sections: dict) -> list[str]:
    text = find_section(sections, "Incompatibilities")
    if not text:
        return []

    results = []
    patterns = [
        r"[Ii]ncompatible\s+with\s+(.+?)(?:\.|$)",
        r"[Cc]annot be used in products containing\s+(.+?)(?:\.|$)",
        r"[Aa]void\s+(?:mixing|contact)\s+with\s+(.+?)(?:\.|$)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            # Split on comma/and, preserve multi-word items
            items = re.split(r",\s*(?:and\s+)?|\s+and\s+", m.group(1))
            results.extend(i.strip().rstrip(".") for i in items if i.strip())

    return _dedupe(results)


def get_stability_block(sections: dict) -> dict:
    """Returns stability_notes, storage_conditions, temperature_sensitivity."""
    text = find_section(sections, "Stability")
    out = {"stability_notes": "", "storage_conditions": "", "temperature_sensitivity": ""}
    if not text:
        return out

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    stability_sentences = []

    for s in sentences:
        s_lower = s.lower()
        if any(kw in s_lower for kw in ["store", "storage", "container", "cool", "dry"]):
            out["storage_conditions"] = s.strip()
        elif any(kw in s_lower for kw in ["temperature", "°c", "heat", "drying"]):
            out["temperature_sensitivity"] = s.strip()
        else:
            stability_sentences.append(s.strip())

    out["stability_notes"] = " ".join(s for s in stability_sentences if len(s) > 15)
    return out


def get_toxicity_notes(sections: dict) -> str:
    text = find_section(sections, "Safety")
    if not text:
        return ""
    keywords = ["nontoxic", "non-toxic", "toxic", "ld50", "laxative",
                "irritat", "carcinogen", "regarded as", "inhalation", "oral"]
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    relevant = [s.strip() for s in sentences if any(kw in s.lower() for kw in keywords)]
    return " ".join(relevant)


def get_regulatory_status(sections: dict) -> str:
    text = find_section(sections, "Regulatory")
    return re.sub(r"\s+", " ", text).strip() if text else ""


def get_temperature_fallback(sections: dict) -> str:
    """Fallback: parse melting range from Typical Properties."""
    text = find_section(sections, "Typical Properties")
    m = re.search(r"[Mm]elting[^:]*:\s*([^\n]+)", text)
    return f"Melting range: {m.group(1).strip()}" if m else ""


def get_cross_references(sections: dict) -> dict[str, list[str]]:
    """
    Scan all sections for 'See Section X' patterns.
    Returns {section_name: [referenced_section_numbers]}

    Example: {"7_Applications": ["18"], "10_Typical Properties": ["12"]}
    """
    pattern = re.compile(r"[Ss]ee\s+(?:also\s+)?[Ss]ection\s+(\d+)", re.IGNORECASE)
    refs = {}
    for section_name, text in sections.items():
        found = pattern.findall(text)
        if found:
            refs[section_name] = found
    return refs


# ── Main ──────────────────────────────────────────────────────────────────────

def extract(normalized: dict) -> tuple[dict, dict]:
    """
    Run all rule-based extractors on a normalized excipient dict.

    Returns:
        extracted  — schema fields with values
        provenance — per-field method + source section
    """
    sections = normalized["sections"]
    name     = get_name(sections, normalized.get("name", ""))
    stability = get_stability_block(sections)
    temp = stability["temperature_sensitivity"] or get_temperature_fallback(sections)

    extracted = {
        "excipient_name":          name,
        "synonyms":                get_synonyms(sections),
        "description":             get_description(sections),
        "roles":                   get_roles(sections),
        "dosage_forms":            [],        # → Layer 2
        # "incompatibilities":       get_incompatibilities(sections), # deprecated
        "incompatibilities": [],  # → Layer 2 (LLM enrichment, see layer2/llm_enricher.py),
        "compatibilities":         [],        # → Layer 2
        "stability_notes":         stability["stability_notes"],
        "ph_sensitivity":          "",        # → Layer 2
        "temperature_sensitivity": temp,
        "toxicity_notes":          get_toxicity_notes(sections),
        "regulatory_status":       get_regulatory_status(sections),
        "processing_notes":        "",        # → Layer 2
        "storage_conditions":      stability["storage_conditions"],
        "cross_references":        get_cross_references(sections),
    }

    provenance = {
        "excipient_name":          {"section": "1_Nonproprietary / name",         "method": "rule"},
        "synonyms":                {"section": "2_Synonyms",                       "method": "rule"},
        "description":             {"section": "8_Description",                    "method": "rule"},
        "roles":                   {"section": "6_Functional + 7_Applications",    "method": "rule"},
        "dosage_forms":            {"section": "7_Applications + 16_Regulatory",   "method": "llm"},
        "incompatibilities":       {"section": "12_Incompatibilities",             "method": "rule"},
        "compatibilities":         {"section": "12_Incompatibilities",             "method": "llm"},
        "stability_notes":         {"section": "11_Stability",                     "method": "rule"},
        "ph_sensitivity":          {"section": "11_Stability / 10_Properties",     "method": "llm"},
        "temperature_sensitivity": {"section": "11_Stability / 10_Properties",     "method": "rule"},
        "toxicity_notes":          {"section": "14_Safety",                        "method": "rule"},
        "regulatory_status":       {"section": "16_Regulatory Acceptance",         "method": "rule"},
        "processing_notes":        {"section": "7_Applications",                   "method": "llm"},
        "storage_conditions":      {"section": "11_Stability",                     "method": "rule"},
        "cross_references":        {"section": "all", "method": "rule"},
    }

    return extracted, provenance
