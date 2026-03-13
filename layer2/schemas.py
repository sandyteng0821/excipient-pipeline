"""
layer2/schemas.py

Pydantic models for LLM-extracted fields.
Import these in prompts.py and llm_enricher.py.

To add a new extraction task:
    1. Define a new BaseModel here
    2. Add a corresponding prompt builder in prompts.py
    3. Call it from llm_enricher.py
"""
import json
from pydantic import BaseModel, Field, field_validator


class ExcipientEnrichment(BaseModel):
    """
    Fields that rule-based Layer 1 cannot reliably extract.
    All fields default to empty — LLM should never invent data.
    """

    dosage_forms: list[str] = Field(
        default_factory=list,
        description=(
            "Dosage forms this excipient is used in. "
            "Use only values from the provided valid list. "
            "Include all forms mentioned (e.g. tablet, solution, suspension)."
        ),
    )

    processing_notes: str = Field(
        default="",
        description=(
            "Practical formulation guidance for formulators: "
            "concentration ranges (e.g. '1–5% as tablet binder, 10–20% as emulsifier'), "
            "mixing order, heating warnings, or processing tips. "
            "Always extract numeric concentration ranges when present."
        ),
    )

    ph_sensitivity: str = Field(
        default="",
        description=(
            "pH value or range and its effect on stability or function. "
            "Extract even if only briefly mentioned (e.g. 'pH = 4.5–5.0 for 5% w/v solution'). "
            "Leave empty string only if pH is truly not discussed."
        ),
    )

    incompatibilities: list[str] = Field(
        default_factory=list,
        description=(
            "Specific substance or chemical names incompatible with this excipient. "
            "Extract only names (e.g. 'ethanol', 'ferric salts', 'tannins'). "
            "Exclude generic phrases like 'a number of substances' or any text "
            "that is not a specific substance name."
        ),
    )

    compatibilities: list[str] = Field(
        default_factory=list,
        description=(
            "Explicitly confirmed compatible substances or excipients. "
            "Do NOT infer — only include if the text directly states compatibility. "
            "Usually []."
        ),
    )

    # pydantic class validation
    @field_validator("ph_sensitivity", "processing_notes", mode="before")
    @classmethod
    def coerce_to_str(cls, v):
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False)
        return v

    @field_validator("dosage_forms", "incompatibilities", "compatibilities", mode="before")
    @classmethod
    def coerce_to_list(cls, v):
        if isinstance(v, str):
            return [v]
        if isinstance(v, dict):
            return list(v.values()) if v else []
        if isinstance(v, list):
            # flatten nested lists
            result = []
            for item in v:
                if isinstance(item, list):
                    result.extend([str(i) for i in item])
                else:
                    result.append(item)
            return result
        return v