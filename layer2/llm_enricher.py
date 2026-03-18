"""
layer2/llm_enricher.py

LLM enrichment with swappable providers via LangChain.
Responsible for: provider init, LLM call, response parsing, provenance tracking.

Schema and prompt logic live in schemas.py and prompts.py respectively.

Setup:
    pip install langchain-core

    Then install the provider you want to use:
        HuggingFace:  pip install langchain-huggingface
        Groq:         pip install langchain-groq
        Ollama:       pip install langchain-ollama  (no API key needed)
        OpenAI:       pip install langchain-openai
        Anthropic:    pip install langchain-anthropic

    Add the relevant key to .env:
        HF_TOKEN=hf_...
        GROQ_API_KEY=gsk_...
        OPENAI_API_KEY=sk-...
        ANTHROPIC_API_KEY=sk-ant-...
        (Ollama needs no key — just run: ollama serve)

    Set provider in .env or environment:
        LLM_PROVIDER=groq
"""

import os
import re
import json
import time
from pathlib import Path
from dotenv import load_dotenv

from layer2.schemas import ExcipientEnrichment
from layer2.prompts import SYSTEM_PROMPT, FIELD_SECTIONS, build_enrichment_prompt

load_dotenv()

# ── Provider config ───────────────────────────────────────────────────────────

PROVIDER = os.environ.get("LLM_PROVIDER", "groq")

PROVIDER_CONFIGS = {
    "huggingface": {
        "model": "HuggingFaceH4/zephyr-7b-beta",
        "init":  lambda model: _init_hf(model),
        "max_context_chars": 3000,  # 免費，保守截斷
    },
    "groq": {
        "model": "llama-3.3-70b-versatile",
        "init":  lambda model: _init_groq(model),
        "max_context_chars": 3000,  # 免費，保守截斷
    },
    "ollama": {
        "model": "llama3.2",
        "init":  lambda model: _init_ollama(model),
        "max_context_chars": 3000,  # 本地，視 GPU 而定
    },
    "openai": {
        "model": "gpt-4o-mini",
        "init":  lambda model: _init_openai(model),
        "max_context_chars": None,  # 付費，不截斷
    },
    "anthropic": {
        "model": "claude-haiku-4-5-20251001",
        "init":  lambda model: _init_anthropic(model),
        "max_context_chars": None,  # 付費，不截斷
    },
}


def _init_hf(model: str):
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
    llm = HuggingFaceEndpoint(
        repo_id=model,
        huggingfacehub_api_token=os.environ["HF_TOKEN"],
        temperature=0.1,
    )
    return ChatHuggingFace(llm=llm)

def _init_groq(model: str):
    from langchain_groq import ChatGroq
    return ChatGroq(model=model, temperature=0, api_key=os.environ["GROQ_API_KEY"])

def _init_ollama(model: str):
    from langchain_ollama import ChatOllama
    return ChatOllama(model=model, temperature=0)

def _init_openai(model: str):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, temperature=0, api_key=os.environ["OPENAI_API_KEY"])

def _init_anthropic(model: str):
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=model, temperature=0, api_key=os.environ["ANTHROPIC_API_KEY"])


# ── Load model (lazy, once) ───────────────────────────────────────────────────

_llm = None

def _get_llm():
    global _llm
    if _llm is None:
        config = PROVIDER_CONFIGS.get(PROVIDER)
        if not config:
            raise ValueError(
                f"Unknown provider: '{PROVIDER}'. "
                f"Choose from: {list(PROVIDER_CONFIGS)}"
            )
        print(f"  [L2] Provider: {PROVIDER} / {config['model']}")
        _llm = config["init"](config["model"])
    return _llm


# ── Ontology ──────────────────────────────────────────────────────────────────

_ONTOLOGY_PATH = Path(__file__).parent.parent / "config" / "ontology.json"
_VALID_DOSAGE_FORMS = list(
    json.loads(_ONTOLOGY_PATH.read_text())["dosage_forms"].keys()
)


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_llm(prompt: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage
    llm = _get_llm()
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]
    return llm.invoke(messages).content


# ── Parse + validate ──────────────────────────────────────────────────────────

def _parse_response(raw: str) -> dict:
    """Strip markdown fences and extract the first JSON object."""
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")
    start, end = cleaned.find("{"), cleaned.rfind("}") + 1
    if start == -1:
        raise ValueError(f"No JSON object found in LLM response:\n{raw}")
    return json.loads(cleaned[start:end])


def _validate(data: dict) -> ExcipientEnrichment:
    """
    Validate raw dict against ExcipientEnrichment schema.
    Pydantic will coerce types where possible and raise on hard failures.
    dosage_forms are additionally filtered against the ontology.
    """
    enriched = ExcipientEnrichment(**data)
    enriched.dosage_forms = [
        df for df in enriched.dosage_forms
        if df in _VALID_DOSAGE_FORMS
    ]
    return enriched


# ── Provenance builder ────────────────────────────────────────────────────────

def _build_provenance(field: str, existing: dict) -> dict:
    """
    Return updated provenance entry for a field.
    Preserves existing section info and adds LLM metadata.
    """
    return {
        **existing.get(field, {}),
        "method":   "llm",
        "provider": PROVIDER,
        "model":    PROVIDER_CONFIGS[PROVIDER]["model"],
        "sections": FIELD_SECTIONS.get(field, []),  # which sections were used
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def enrich(clean_json: dict) -> dict:
    """
    Fill L2 fields in a Layer 1 clean JSON using the configured LLM provider.

    Only overwrites fields that are empty or need LLM correction (dosage_forms).
    Adds full provenance including which sections were used as context.

    Returns updated dict with enriched extracted fields and provenance.
    """
    name       = clean_json["meta"]["excipient_name"]
    sections   = clean_json["raw"]["sections"]
    extracted  = clean_json["extracted"].copy()
    provenance = clean_json["provenance"].copy()

    # Build prompt (section context is filtered per-field inside build_enrichment_prompt)
    for field in FIELD_SECTIONS:
        print(f"  [L2] Field: {field}")
        
        prompt = build_enrichment_prompt(
            excipient_name=name,
            sections=sections,
            l1_dosage_forms=extracted.get("dosage_forms", []),
            valid_dosage_forms=_VALID_DOSAGE_FORMS,
            target_fields=[field],
            max_context_chars=PROVIDER_CONFIGS[PROVIDER]["max_context_chars"],
        )

        # Call LLM and validate response
        for attempt in range(1, 4):
            try:
                raw_response = _call_llm(prompt)
                enriched: ExcipientEnrichment = _validate(_parse_response(raw_response))
                break
            except (json.JSONDecodeError, ValueError) as e:
                if attempt == 3:
                    raise
                print(f"  [L2] Attempt {attempt} failed, retrying in {2**attempt}s...")
                time.sleep(2 ** attempt)

        # Write back: target_fields
        value = enriched.model_dump()[field]
        if field in ("dosage_forms", "incompatibilities") or not extracted.get(field):
            extracted[field]  = value
            provenance[field] = _build_provenance(field, provenance)

    return {
        **clean_json,
        "extracted":  extracted,
        "provenance": provenance,
        "meta": {
            **clean_json["meta"],
            "annotator": f"layer1_rule+layer2_{PROVIDER}",
        },
    }
