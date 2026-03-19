"""
layer2/prompts.py

Prompt builder functions for each LLM extraction task.
Imported by llm_enricher.py — no LLM logic here.

To add a new prompt:
    1. Define build_<task>_prompt(...)
    2. Add field → section mapping to FIELD_SECTIONS
    3. Import and call it from llm_enricher.py
"""

import json
from layer2.schemas import ExcipientEnrichment


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a pharmaceutical science expert. "
    "Extract structured data from excipient handbook text. "
    "Return ONLY valid JSON — no explanation, no markdown fences."
)


# ── Field → Section mapping ───────────────────────────────────────────────────
# Defines which handbook sections each field reads from.
# Used both for context filtering (less noise) and for debug provenance.
#
# Key:   field name in ExcipientEnrichment
# Value: list of section keywords to match (case-insensitive substring match)

FIELD_SECTIONS: dict[str, list[str]] = {
    "dosage_forms":     ["Functional Category", "Applications", "Regulatory"],
    "processing_notes": ["Applications", "Method of Manufacture"],
    "ph_sensitivity":   ["Typical Properties", "Stability"],
    "compatibilities":  ["Incompatibilities", "Stability"],
    "incompatibilities": ["Incompatibilities", "Applications", "Typical Properties"],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _schema_descriptions(model_class) -> dict:
    """Extract field descriptions from a Pydantic model as a plain dict."""
    return {
        field_name: field_info.description or ""
        for field_name, field_info in model_class.model_fields.items()
    }


def _schema_defaults(model_class) -> dict:
    """Extract default values from a Pydantic model for use as JSON template."""
    return model_class().model_dump()


def _filter_sections(sections: dict, keywords: list[str], max_chars: int | None = None) -> str:
    """
    Return handbook text for sections whose names match any of the keywords.
    Each matched section is prefixed with its name for LLM context.

    Args:
        sections: Raw sections dict from Layer 1 (key = section name)
        keywords: List of keywords to match against section names
        max_chars: If set, truncate combined context to this many characters.
                   Use None (default) for no truncation (e.g. paid providers).
    """
    matched = [
        f"[{section_name}]\n{text}"
        for keyword in keywords
        for section_name, text in sections.items()
        if keyword.lower() in section_name.lower()
    ]
    full_context = "\n\n".join(matched) if matched else "(no relevant section found)"

    if max_chars and len(full_context) > max_chars:
        return full_context[:max_chars] + "\n...[truncated]"    
    return full_context


def get_field_context(field: str, sections: dict, max_chars: int | None = None) -> str:
    """
    Public helper: return the filtered section text for a single field.
    Useful for debugging — lets you see exactly what context the LLM received.

    Usage:
        from layer2.prompts import get_field_context
        print(get_field_context("ph_sensitivity", clean_json["raw"]["sections"]))
    """
    keywords = FIELD_SECTIONS.get(field, [])
    return _filter_sections(sections, keywords, max_chars=max_chars)


# ── Prompt builders ───────────────────────────────────────────────────────────

def build_enrichment_prompt(
    excipient_name: str,
    sections: dict,
    l1_dosage_forms: list[str],
    valid_dosage_forms: list[str],
    target_fields: list[str] | None = None,
    max_context_chars: int | None = None,
) -> str:
    """
    Build the prompt for ExcipientEnrichment extraction.

    Each field only sees the handbook sections it needs (defined in FIELD_SECTIONS),
    reducing noise and making it easier to debug why a field was extracted a certain way.

    Args:
        excipient_name:     Name of the excipient (e.g. "Acacia")
        sections:           Raw handbook sections dict from Layer 1
        l1_dosage_forms:    Dosage forms already extracted by Layer 1 (may have errors)
        valid_dosage_forms: Allowed values from ontology.json
        target_fields:      Target fields for text extraction
        max_context_chars:  Per-field context char limit. None = no truncation (paid providers).
    """
    # Determine fields to extract
    active_fields = target_fields if target_fields is not None else list(FIELD_SECTIONS.keys())

    # Build per-field context blocks (each field only reads its own sections)
    context_blocks = []
    for field in active_fields:
        if field not in FIELD_SECTIONS:
            continue
        keywords = FIELD_SECTIONS[field]
        text = _filter_sections(sections, keywords, max_chars=max_context_chars)
        context_blocks.append(
            f"### Context for `{field}` (sections: {keywords})\n{text}"
        )
    context = "\n\n".join(context_blocks) if context_blocks else "(no relevant sections)"

    # Field descriptions from schema — single source of truth
    all_schema_desc = _schema_descriptions(ExcipientEnrichment)
    # Keep only description in active_fields
    schema_desc = {f: all_schema_desc[f] for f in active_fields if f in all_schema_desc}

    # Inject valid dosage_forms list into description at prompt-build time
    if "dosage_forms" in schema_desc:
        schema_desc["dosage_forms"] = (
            f"{schema_desc['dosage_forms']} "
            f"Valid values: {valid_dosage_forms}"
        )

    # Empty output template so model knows the exact shape (only for active_fields)
    all_defaults = _schema_defaults(ExcipientEnrichment)
    output_template = json.dumps(
        {f: all_defaults[f] for f in active_fields if f in all_defaults}, indent=2
    )

    # Layer 1 block
    l1_block = (
        f"\n--- LAYER 1 EXTRACTED (may have errors, use as reference only) ---\n"
        f"dosage_forms: {l1_dosage_forms}\n"
        if "dosage_forms" in active_fields else ""
    )

    return f"""Excipient: {excipient_name}

--- HANDBOOK TEXT (grouped by field) ---
{context}
{l1_block}
--- TASK ---
Return a JSON object with EXACTLY these keys and constraints:
{json.dumps(schema_desc, indent=2)}

RULES:
- Each field has its own context block above — use only the relevant block
- All list fields MUST be JSON arrays, never comma-separated strings
- Numbers must be actual numbers, not strings
- Use "" or [] if information is absent — do NOT invent data
- Extract ALL numeric concentration ranges when present

Output template (replace values, keep all keys):
{output_template}"""
