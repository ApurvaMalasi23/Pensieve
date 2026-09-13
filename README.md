# Pensieve — Phase 1: Docling Ingestion Pipeline

RAG system ingestion pipeline for Indian company annual reports and broker research PDFs.

**Phase 1 scope:** PDF → structured JSON (one file per document). No chunking, embeddings, or retrieval.

---

## Quick Start

### 1. Install

```bash
# Create and activate a virtual environment (Python 3.11+)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install the package and its dependencies
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — add your NVIDIA_API_KEY
```

### 3. Run a batch

```bash
python -m pensieve.batch_runner \
    --input-dir ./pdfs \
    --output-dir ./output \
    --manifest ./manifest.csv
```

Or use the installed entry point:

```bash
pensieve-ingest --input-dir ./pdfs --output-dir ./output
```

### 4. Check the results

- **`output/<doc_id>.json`** — one structured JSON per document
- **`manifest.csv`** — batch summary with company, fiscal year, page count, table flags, and errors

---

## Output JSON Schema

```json
{
  "doc_id": "<sha256 hex prefix>",
  "source_filename": "...",
  "company_name": "...",
  "fiscal_year": "...",
  "reporting_period_type": "annual | quarterly | other",
  "num_pages": 0,
  "extraction_metadata": {
    "docling_version": "...",
    "converted_at": "<ISO-8601 timestamp>",
    "conversion_errors": [],
    "needs_review": false
  },
  "text_blocks": [
    {
      "block_id": "...",
      "page": 0,
      "text": "...",
      "section_hint": "narrative | heading | footnote | unknown"
    }
  ],
  "tables": [
    {
      "table_id": "...",
      "page": 0,
      "rows": 0,
      "cols": 0,
      "grid": [["cell", "text"], ["..."]],
      "caption": "<string or null>",
      "risk_flag": false,
      "risk_reasons": []
    }
  ]
}
```

---

## Manifest CSV Columns

| Column | Description |
|---|---|
| `filename` | Original source filename |
| `doc_id` | Content-based SHA-256 prefix |
| `company` | Extracted company name |
| `fiscal_year` | Extracted fiscal year / period |
| `pages` | Total page count |
| `tables` | Total tables extracted |
| `tables_flagged` | Tables with `risk_flag: true` |
| `status` | `success` or `failed` |
| `error` | Error message if status is `failed` |

---

## Architecture

```
pensieve/
├── config.py            # Tunable constants and env-var defaults
├── logger.py            # Centralised logging setup
├── converter.py         # Task 1: Docling document conversion
├── metadata_extractor.py# Task 2: Company + fiscal year via NVIDIA NIM (Llama 3.1 70B)
├── risk_flagger.py      # Task 4: Table risk assessment (modular, tunable)
├── structurer.py        # Task 3: Build output JSON schema
└── batch_runner.py      # Task 5: CLI batch processor + manifest
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Design Notes

- **No VLM pipeline.** Standard `DocumentConverter` with `TableFormer` only.
- **OCR always on.** Target set includes older / scanned filings; disabling OCR would silently return empty pages.
- **PDF-centric naming, format-agnostic interface.** Variables use "document" where it costs nothing, but no multi-format support is claimed or tested in this phase.
- **Risk flagging is a signal, not an action.** Flagged tables are included normally in output; the flag exists for the frontend disclaimer layer (Phase 6) and for Phase 4 numeric confidence scoring.
- **Batch runs are fault-tolerant.** A failed document is logged and skipped; the run continues and reports a summary.
