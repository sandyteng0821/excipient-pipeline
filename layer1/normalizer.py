"""
layer1/normalizer.py

Cleans raw OCR JSON before extraction.
Handles: noisy section keys, image artefacts, whitespace, encoding issues.
"""

import re
import json
from pathlib import Path


# Load section mapping once
_MAPPING_PATH = Path(__file__).parent.parent / "config" / "section_mapping.json"
_SECTION_MAP: dict = json.loads(_MAPPING_PATH.read_text())["section_to_field"]


def normalize_section_key(key: str) -> str:
    """
    Normalize a raw section key to a stable lookup string.
    e.g. "7_Applications in Pharmaceutical Formulation or Technology"
      -> "applications in pharmaceutical formulation or technology"
    """
    # Strip leading number prefix like "7_" or "7."
    key = re.sub(r"^\d+[_.\s]+", "", key)
    return key.lower().strip()


def find_section(sections: dict, fragment: str) -> str:
    """
    Find a section by partial match on normalized keys.
    Returns section text or empty string.
    """
    fragment_lower = fragment.lower()
    for raw_key, value in sections.items():
        if fragment_lower in normalize_section_key(raw_key):
            return value or ""
    return ""


def clean_section_text(text: str) -> str:
    """
    Remove known OCR/PDF artefacts from section text.
    - SEM image labels
    - HTML comment placeholders
    - Excessive whitespace
    """
    # Remove SEM image blocks
    text = re.sub(r"SEM:\s*\d+.*?(?=\n\n|\Z)", "", text, flags=re.DOTALL)
    # Remove HTML comment artefacts (image placeholders from PDF parser)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Normalize whitespace within lines
    text = "\n".join(line.strip() for line in text.splitlines())
    return text.strip()


def normalize(raw_json: dict) -> dict:
    """
    Entry point: takes a raw excipient JSON, returns a cleaned version
    with normalized section keys and cleaned text values.

    Input format:
        { "name": "...", "sections": { "7_Applications ...": "text", ... } }

    Output format:
        { "name": "...", "sections": { "7_Applications ...": "cleaned text", ... } }
        (keys unchanged — downstream uses find_section() for fuzzy lookup)
    """
    sections = raw_json.get("sections", {})

    cleaned_sections = {
        key: clean_section_text(value)
        for key, value in sections.items()
        if isinstance(value, str)
    }

    return {
        "name": raw_json.get("name", ""),
        "sections": cleaned_sections,
    }
