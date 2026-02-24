# Plan: Thesis Fetching & Term Discovery Pipeline

## Overview

Add a new script `scripts/fetch_theses.py` (and supporting modules) that:
1. Harvests thesis metadata from three Estonian university repositories via OAI-PMH
2. Extracts data-related terms from bilingual abstracts (EN + ET)
3. Compares found terms against existing `data/terms.yml`
4. Produces a report of candidate terms missing from the glossary

## Architecture

```
scripts/
├── generate_glossary.py          # existing
├── fetch_theses.py               # NEW: main entry point / CLI
├── thesis/                       # NEW: package for thesis harvesting
│   ├── __init__.py
│   ├── harvester.py              # OAI-PMH harvesting logic
│   ├── parser.py                 # Parse Dublin Core XML metadata
│   ├── term_extractor.py         # NLP + curated list term extraction
│   ├── reference_terms.py        # Curated list of ~300+ known data terms (EN)
│   └── reporter.py               # Generate candidate term reports
data/
├── terms.yml                     # existing glossary (single source of truth)
├── harvest_state.json            # NEW: watermark file tracking last harvest dates
└── candidate_terms.yml           # NEW: output report of discovered candidate terms
```

## Step-by-step Plan

### Step 1: Add new dependencies to `pyproject.toml`

Add to a new `[dependency-groups] harvest` group (separate from dev/main):
- `requests` — HTTP client for OAI-PMH requests
- `lxml` — XML parsing for OAI-PMH Dublin Core responses
- `spacy` — NLP for noun phrase extraction (with `en_core_web_sm` model)
- `pyyaml` — already a project dependency

The harvest group keeps thesis-fetching deps separate from the core glossary tool.

### Step 2: Create `scripts/thesis/harvester.py` — OAI-PMH Harvester

Handles communication with all three university repositories:

**University Endpoints:**
| University | Base URL | Notes |
|---|---|---|
| Tartu (UT) | `https://dspace.ut.ee/oai/request` | DSpace, well-documented OAI-PMH |
| TalTech | `https://digikogu.taltech.ee/oai/request` | OAI-PMH (DART-Europe member) |
| Tallinn (TLU) | `https://www.etera.ee/oai` | OAI-PMH endpoint |

**Key functions:**
- `discover_sets(base_url)` → Call `verb=ListSets` to find CS/data science collections. Cache results.
- `harvest_records(base_url, sets, from_date, until_date)` → Call `verb=ListRecords` with `metadataPrefix=oai_dc`, filter by relevant sets and date range. Handle resumption tokens for pagination.
- Built-in rate limiting: 2-second delay between requests.
- Retry logic: up to 3 retries with exponential backoff on HTTP errors.

**Set Discovery Strategy (CS & Data Science):**
- First run: use `ListSets` to enumerate all collections, then filter by name keywords: `informaatika`, `informatics`, `computer science`, `arvutiteadus`, `data science`, `andmeteadus`, `tarkvaratehnika`, `software engineering`, `IT`, `infotehnoloogia`.
- Store discovered set specs in `harvest_state.json` for reuse.

### Step 3: Create `scripts/thesis/parser.py` — Dublin Core Metadata Parser

Parse OAI-PMH XML responses (Dublin Core `oai_dc` format):

**Extracted fields per thesis:**
- `identifier` — OAI identifier (for dedup/tracking)
- `title` — thesis title (may have EN and ET versions via multiple `dc:title`)
- `abstract_en` — English abstract (`dc:description` with `xml:lang="en"`)
- `abstract_et` — Estonian abstract (`dc:description` with `xml:lang="et"`)
- `subject` — keywords/subjects (`dc:subject`)
- `date` — publication date (`dc:date`)
- `type` — thesis type (`dc:type`, e.g., "masterThesis", "bachelorThesis")
- `url` — link to full record (`dc:identifier` with URL)

**Language detection fallback:** If `xml:lang` attributes are missing, use a simple heuristic (presence of Estonian characters õ/ä/ö/ü in high frequency = Estonian, otherwise English).

### Step 4: Create `scripts/thesis/reference_terms.py` — Curated Term List

A Python module containing a curated dictionary of ~300-500 known data engineering/analytics terms in English, organized by category:

**Categories:**
- Data Storage: data warehouse, data lake, data lakehouse, data mesh, data fabric, ...
- Data Modeling: star schema, snowflake schema, fact table, dimension table, surrogate key, natural key, ...
- ETL/ELT: ETL, ELT, data pipeline, data ingestion, CDC (change data capture), ...
- Analytics & BI: OLAP, OLTP, KPI, dashboard, ad-hoc query, ...
- Machine Learning: neural network, deep learning, gradient descent, overfitting, cross-validation, ...
- Data Governance: data quality, data lineage, data catalog, master data, metadata, ...
- Big Data: distributed computing, MapReduce, Spark, Hadoop, stream processing, ...
- Cloud & Infrastructure: data engineering, orchestration, containerization, microservices, ...
- Statistics: regression, classification, clustering, time series, A/B testing, ...
- NLP / AI: natural language processing, large language model, transformer, tokenization, ...

Each term stored as: `{"en": "term", "et_hints": ["possible ET translations"]}` — the ET hints help with matching in Estonian abstracts too.

### Step 5: Create `scripts/thesis/term_extractor.py` — Dual Extraction Strategy

**Strategy A: Curated List Matching**
- Load reference terms from `reference_terms.py`
- For each thesis abstract (EN and ET), check which reference terms appear
- Use case-insensitive matching with word boundary awareness
- Track frequency: how many theses mention each term

**Strategy B: NLP Noun Phrase Extraction**
- Use spaCy `en_core_web_sm` for English abstracts
- Extract noun phrases (noun chunks)
- Filter for multi-word phrases (2-4 words) that look like technical terms
- Apply heuristics to filter noise: discard overly generic phrases, keep phrases with technical-sounding words
- For Estonian abstracts: use simple n-gram extraction (spaCy doesn't have a good Estonian model) — extract 2-3 word sequences, filter by frequency across theses

**Combining results:**
- Curated matches = high confidence candidates
- NLP-discovered terms that appear in 3+ theses = medium confidence candidates
- Both lists get compared against existing `data/terms.yml` to find what's missing

### Step 6: Create `scripts/thesis/reporter.py` — Report Generation

Generate `data/candidate_terms.yml` with discovered terms:

```yaml
# Auto-generated by fetch_theses.py on 2026-02-22
# Candidates NOT yet in data/terms.yml

- en: "data pipeline"
  confidence: high         # matched from curated list
  frequency: 47            # appeared in 47 theses
  source: curated
  sample_theses:
    - title: "Building Real-Time Data Pipelines..."
      url: "https://dspace.ut.ee/..."
      university: "UT"

- en: "random forest"
  confidence: medium       # discovered via NLP
  frequency: 12
  source: nlp
  sample_theses:
    - title: "..."
```

Also produce a human-readable markdown summary to stdout:

```
=== Thesis Term Discovery Report ===
Theses analyzed: 342 (UT: 180, TalTech: 112, TLU: 50)
Date range: 2015-01-01 to 2025-12-31

HIGH CONFIDENCE (curated list match, not in glossary): 28 terms
  data pipeline (47 mentions)
  data mesh (23 mentions)
  ...

MEDIUM CONFIDENCE (NLP-discovered, 3+ theses): 15 terms
  ...

Already in glossary (confirmed): 4/5 terms found
  data warehouse: 89 mentions
  ...
```

### Step 7: Create `scripts/fetch_theses.py` — CLI Entry Point

Main script with `argparse` CLI:

```
Usage:
  uv run python scripts/fetch_theses.py [OPTIONS]

Options:
  --from-date DATE    Start date (default: from harvest_state.json or 2015-01-01)
  --until-date DATE   End date (default: today)
  --full              Ignore harvest state, do full historical run
  --output PATH       Output candidate terms file (default: data/candidate_terms.yml)
  --universities      Comma-separated: ut,taltech,tlu (default: all)
  --min-frequency N   Minimum thesis mentions for NLP terms (default: 3)
  --verbose           Show detailed progress
```

**Workflow:**
1. Load `data/harvest_state.json` (or create if first run)
2. Load existing terms from `data/terms.yml`
3. For each university: harvest thesis records via OAI-PMH
4. Parse metadata, extract abstracts
5. Run term extraction (curated + NLP) on all abstracts
6. Compare against existing glossary terms
7. Generate report → `data/candidate_terms.yml`
8. Update `data/harvest_state.json` with new watermark dates
9. Print summary to stdout

### Step 8: Create `data/harvest_state.json` — Watermark Tracking

Simple, lightweight state file:

```json
{
  "last_run": "2026-02-22T10:00:00",
  "universities": {
    "ut": {
      "last_harvest_date": "2026-02-22",
      "sets": ["com_10062_1", "com_10062_55"],
      "total_records_harvested": 180
    },
    "taltech": {
      "last_harvest_date": "2026-02-22",
      "sets": ["col_123_456"],
      "total_records_harvested": 112
    },
    "tlu": {
      "last_harvest_date": "2026-02-22",
      "sets": ["set_abc"],
      "total_records_harvested": 50
    }
  }
}
```

This avoids tracking individual thesis IDs (which could be thousands). Instead, on monthly runs we simply use the `from` parameter of OAI-PMH to only harvest new/modified records since the last run date. OAI-PMH natively supports this — it's the intended use pattern.

**Idempotency:** If the same thesis appears in both a full run and an incremental run, deduplication happens at the term-extraction level (we're looking for terms, not tracking theses). The candidate report always reflects the cumulative picture.

### Step 9: Update `.gitignore`

Add:
```
# Thesis harvesting cache (large, regenerable)
data/harvest_cache/
```

Don't ignore `harvest_state.json` or `candidate_terms.yml` — these should be committed so the team can see results and track harvest progress.

### Step 10: Update `pyproject.toml` with harvest dependency group

```toml
[dependency-groups]
dev = [
  "mkdocs>=1.6.1",
  "mkdocs-material>=9.6.14",
]
harvest = [
  "requests>=2.31",
  "lxml>=5.0",
  "spacy>=3.7",
]
```

To install: `uv sync --group harvest`
Then: `uv run python -m spacy download en_core_web_sm`

### Step 11: Test the pipeline

1. First do a small test run with `--from-date 2024-01-01` for one university to validate OAI-PMH connectivity and parsing
2. Then run the full historical harvest `--full --from-date 2015-01-01`
3. Review generated `data/candidate_terms.yml`
4. Print summary report

## Key Design Decisions

1. **Watermark-based tracking vs thesis ID tracking**: Using date watermarks is far more practical than tracking thousands of individual thesis IDs. OAI-PMH's `from`/`until` parameters are designed for exactly this incremental harvesting pattern.

2. **Separate dependency group**: The `harvest` group keeps heavy NLP dependencies (spaCy ~200MB with model) out of the core glossary toolchain. Team members who only edit terms don't need these.

3. **Dual extraction (curated + NLP)**: The curated list catches known terms reliably. NLP catches emerging/novel terms the curated list doesn't know about. Together they provide good coverage.

4. **Estonian NLP limitation**: spaCy has no Estonian model. For ET abstracts, we use simpler n-gram matching + the curated list with ET hints. This is a pragmatic compromise.

5. **Output as YAML**: The candidate report is YAML to match the project's data format. It can be reviewed and terms can be cherry-picked into `data/terms.yml` by a human.

6. **No thesis content storage**: We don't store thesis PDFs or full abstracts. We only extract and store discovered terms with sample thesis references. This keeps the repo lightweight.

## Implementation Order

1. Step 1 + 10: Set up dependencies
2. Step 2: Harvester (test with one university)
3. Step 3: Parser
4. Step 4: Curated reference term list
5. Step 5: Term extractor
6. Step 6: Reporter
7. Step 7: CLI entry point
8. Step 8-9: State management and gitignore
9. Step 11: End-to-end testing
