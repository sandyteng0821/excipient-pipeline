# excipient-pipeline

Structured data extraction from Handbook of Pharmaceutical Excipients raw JSON files.  
Sits downstream of [`ocr-docling-pdfparser`](https://github.com/sandyteng0821/ocr-docling-pdfparser), which handles PDF → raw JSON.

```
PDF → [ocr-docling-pdfparser] → raw JSON
                                      ↓
                               pipeline.py
                                      ↓
                           normalizer.py       清理 OCR noise
                                      ↓
                           extractor.py        rule-based 欄位抓取 (Layer 1)
                                      ↓
                           llm_enricher.py     LLM 補充，optional (Layer 2)
                                      ↓
                               clean JSON
```

---

## Repository Structure

```
excipient_pipeline/
├── pipeline.py              # entry point (single file + batch)
├── batch_report.py          # batch runner + quality statistics
├── report_all.py            # aggregate quality report across all clean JSONs
├── requirements.txt
├── config/
│   ├── ontology.json        # roles / dosage form keyword mapping
│   └── section_mapping.json
├── layer1/
│   ├── normalizer.py        # cleans OCR noise, fuzzy section lookup
│   └── extractor.py         # rule-based field extraction
├── layer2/
│   ├── schemas.py           # Pydantic models for LLM-extracted fields
│   ├── prompts.py           # prompt builders (FIELD_SECTIONS mapping)
│   └── llm_enricher.py      # swappable LLM provider (Groq / OpenAI / etc.)
├── tools/
│   ├── raw_status.py        # raw JSON coverage audit tool
│   ├── analyze_ontology_coverage.py  # ontology gap analysis
│   └── query_drug.py        # demo tool for excipient json querying
├── utils/
│   ├── dailymed_utils.py    # DailyMed formulation fetcher
│   └── pubchem_utils.py     # PubChem physicochemical property fetcher
└── data/
    ├── raw/                 # input: raw JSON from ocr-docling-pdfparser
    ├── clean/               # output: enriched clean JSON + quality report CSV
    ├── clean-layer1-only/   # output generated from pipeline (layer 1) => input ussed for query_drug.py
    └── manual/
        └── raw_status_curated.tsv   # human-curated name corrections
```

## Data Directories

| Directory | Content | Source |
|---|---|---|
| `data/raw/` | Raw JSON from OCR pipeline | `ocr-docling-pdfparser` |
| `data/clean/` | Enriched JSON (Layer 1 + Layer 2) | `batch_report.py --enrich` |
| `data/clean-layer1-only/` | Rule-based extraction only (Layer 1) | `batch_report.py` (no `--enrich`) |

`query_drug.py` prefers `data/clean/` (L1+L2), falls back to `data/clean-layer1-only/` (L1 only).

---

## Input Format

Expected raw JSON structure (output from `ocr-docling-pdfparser`):

```json
{
  "name": "Magnesium Stearate",
  "sections": {
    "6_Functional Category": "Tablet and capsule lubricant.",
    "7_Applications in Pharmaceutical Formulation or Technology": "...",
    "12_Incompatibilities": "Incompatible with strong acids..."
  }
}
```

Sections follow the standard Handbook numbering (1–22). Missing sections are tolerated.

---

## Setup

```bash
cd excipient_pipeline

# Layer 1 only — no install needed (Python 3.9+ standard library only)

# Layer 2 (optional LLM enrichment)
pip install -r requirements.txt

# Add API keys to .env
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...

# Set provider (default: groq)
LLM_PROVIDER=groq
```

### Supported LLM Providers

| Provider | Model | Cost | Notes |
|----------|-------|------|-------|
| `groq` | llama-3.3-70b-versatile | Free (100k tokens/day) | Recommended |
| `openai` | gpt-4o-mini | ~$0.002/call | Most stable output |
| `openai` | gpt-4o | ~$0.04/call | |
| `anthropic` | claude-haiku | ~$0.001/call | |
| `ollama` | llama3.2 | Free (local) | Requires local GPU |

> **Groq free tier**: resets daily at UTC 00:00 (~50 excipients/day). Use cron to resume automatically — see [Operations](#operations).

---

## Usage

### Single file

```bash
# Layer 1 only
python pipeline.py data/raw/Acacia.json

# Layer 1 + Layer 2
python pipeline.py data/raw/Acacia.json --enrich
```

### Batch

```bash
# Layer 1 only (fast, no API calls)
python batch_report.py data/raw/

# Layer 1 + 2 (full enrichment)
python batch_report.py data/raw/ --enrich

# Run in background (recommended for --enrich)
nohup python3 batch_report.py data/raw/ --enrich > batch_enrich.log 2>&1 &
tail -f batch_enrich.log
```

Already-completed files are skipped automatically — re-running is safe.

---

## Output Schema

Each clean JSON contains:

```json
{
  "meta":      { "excipient_name": "...", "extraction_date": "...", "annotator": "..." },
  "raw":       { "...original input preserved..." },
  "extracted": { "...structured fields..." },
  "provenance":{ "...per-field method + source section..." }
}
```

### Field Assignment

| Field | Layer | Method |
|-------|-------|--------|
| `excipient_name`, `synonyms`, `description` | L1 | rule |
| `roles` | L1 | ontology keyword match |
| `stability_notes`, `toxicity_notes`, `regulatory_status`, `storage_conditions` | L1 | rule |
| `temperature_sensitivity`, `cross_references` | L1 | rule |
| `dosage_forms`, `processing_notes`, `ph_sensitivity`, `compatibilities`, `incompatibilities` | L2 | LLM |

---

## Quality Report

`batch_report.py` outputs a CSV quality report alongside the clean JSONs:

```
data/clean/quality_report_YYYYMMDD_HHMMSS.csv
```

| Score | Meaning |
|-------|---------|
| 🟢 ≥80% | Good |
| 🟡 50–79% | Partial |
| 🔴 <50% | Poor |

---

## Tools

### `tools/raw_status.py` — Raw JSON Coverage Audit

Audits raw JSON files against the book's table of contents to identify missing or mismatched excipients.

```bash
# Basic: section coverage only
python3 tools/raw_status.py data/raw/

# With table of contents for cross-referencing
python3 tools/raw_status.py data/raw/ contents.tsv
```

**`contents.tsv` format** (tab-separated):
```
Category    Item                    Page
Monograph   Acacia                  1
Monograph   Acesulfame Potassium    4
```

**Output: `raw_status.tsv`** columns:

| Column | Description |
|--------|-------------|
| `file_name` | JSON filename stem |
| `excipient_name` | `name` field from raw JSON |
| `file_path` | full path |
| `fields_found` | sections present (out of 22) |
| `fields_missing` | missing section count |
| `missing_sections` | comma-separated missing section numbers |
| `book_name` | matched name from contents |
| `page` | page number from contents |
| `category` | e.g. `Monograph` |
| `in_contents` | `yes` / `no` / `missing_from_raw` |
| `manual_checked_book_name` | human-corrected book name |
| `manual_checked_page` | inferred from contents |
| `manual_checked_category` | inferred from contents |

**Human curation workflow:**

When `in_contents=no`, add corrections to `data/manual/raw_status_curated.tsv`:

```
file_name       manual_checked_book_name
Unknown36       Agar
Kaliicitras     Potassium Citrate
SeeTableI       Aliphatic Polyesters
```

Re-running `raw_status.py` will automatically merge corrections and infer page/category from contents.

### `utils/dailymed_utils.py` — DailyMed Formulation Fetcher

Fetches active/inactive ingredients from DailyMed SPL XML by drug name.
```bash
# Single SPL (first result)
python3 utils/dailymed_utils.py aspirin

# Fetch N SPLs (multiple manufacturers)
python3 utils/dailymed_utils.py aspirin --sampled 5
```

### `utils/pubchem_utils.py` — PubChem Property Fetcher

Fetches physicochemical properties (SMILES, MW, XLogP, TPSA, HBD/HBA) by compound name or CAS number.
```bash
python3 utils/pubchem_utils.py aspirin
python3 utils/pubchem_utils.py 50-78-2 --input-type cas
```

> **Note:** Polymers and mixtures (e.g. MCC, HPMC, Povidone) have no single CID in PubChem and will return `NOT FOUND`.

---

## Operations

### Automated daily batch (Groq free tier)

Groq resets token quota at UTC 00:00 (08:00 Taiwan time). Schedule the batch to resume each morning:

```bash
crontab -e
```

```
0 10 * * * cd /home/sandy/dev-workplace/excipient_pipeline && \
  venv/bin/python3 batch_report.py data/raw/ --enrich \
  >> batch_cron_$(date +\%Y\%m\%d).log 2>&1
```

- Runs at 10:00 Taiwan time (safe margin after UTC reset)
- Already-completed excipients are skipped automatically
- One log file per day: `batch_cron_YYYYMMDD.log`

---

## Customisation

### Adding a new role or dosage form

Edit `config/ontology.json` — no code change needed:

```json
{
  "roles": {
    "your_new_role": ["keyword1", "keyword2"]
  }
}
```

### Adding a new LLM-extracted field

1. `layer2/schemas.py` — add a `Field(...)` to `ExcipientEnrichment`
2. `layer2/prompts.py` — add the field to `FIELD_SECTIONS`
3. `layer2/llm_enricher.py` — add to the overwrite list in `enrich()` if needed

### Debugging LLM context

```python
from layer2.prompts import get_field_context
import json

raw = json.load(open("data/raw/Acacia.json"))
print(get_field_context("ph_sensitivity", raw["sections"]))
```
