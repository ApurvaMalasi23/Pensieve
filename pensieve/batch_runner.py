"""
pensieve/batch_runner.py
------------------------
Task 5 — Batch Processing Script + Manifest

Processes a folder of documents end-to-end:
    convert → extract metadata → build JSON → risk-flag → save JSON → manifest

Usage (CLI)
-----------
    python -m pensieve.batch_runner \\
        --input-dir ./pdfs \\
        --output-dir ./output \\
        --manifest ./manifest.csv

    # Or the installed entry-point:
    pensieve-ingest --input-dir ./pdfs

Usage (programmatic)
--------------------
    from pensieve.batch_runner import run_batch
    run_batch(input_dir=Path("./pdfs"), output_dir=Path("./output"))
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from tabulate import tabulate

from pensieve.config import DEFAULT_MANIFEST_PATH, DEFAULT_OUTPUT_DIR, JSON_INDENT
from pensieve.converter import convert_document
from pensieve.logger import get_logger
from pensieve.metadata_extractor import extract_document_metadata
from pensieve.structurer import build_document_json

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Manifest row dataclass
# ---------------------------------------------------------------------------

_MANIFEST_FIELDS = [
    "filename",
    "doc_id",
    "company",
    "fiscal_year",
    "pages",
    "tables",
    "tables_flagged",
    "status",
    "error",
]


@dataclass
class ManifestRow:
    filename: str
    doc_id: str = ""
    company: str = ""
    fiscal_year: str = ""
    pages: int = 0
    tables: int = 0
    tables_flagged: int = 0
    status: str = "failed"
    error: str = ""


# ---------------------------------------------------------------------------
# Manifest writer
# ---------------------------------------------------------------------------

class ManifestWriter:
    """Append-mode CSV writer — each row is written immediately so a
    partial batch run doesn't lose already-processed rows."""

    def __init__(self, manifest_path: Path) -> None:
        self._path = manifest_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write header if the file is new / empty.
        write_header = not self._path.exists() or self._path.stat().st_size == 0
        self._fh = self._path.open("a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=_MANIFEST_FIELDS)
        if write_header:
            self._writer.writeheader()

    def append(self, row: ManifestRow) -> None:
        d = asdict(row)
        # Ensure all fields are present and in order.
        self._writer.writerow({k: d.get(k, "") for k in _MANIFEST_FIELDS})
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


# ---------------------------------------------------------------------------
# Per-document processing
# ---------------------------------------------------------------------------

def process_document(
    source_path: Path,
    output_dir: Path,
    manifest: ManifestWriter,
) -> ManifestRow:
    """Process one document through the full pipeline.

    Returns a ManifestRow with the outcome (success or failure).
    Never raises — all exceptions are caught, logged, and recorded in
    the manifest so the batch can continue.
    """
    row = ManifestRow(filename=source_path.name)
    t0 = time.perf_counter()

    # --- Step 1: Convert ---
    result = convert_document(source_path)
    if result is None:
        row.status = "failed"
        row.error = "Conversion returned None (see pensieve.log for details)"
        manifest.append(row)
        return row

    # Collect any non-fatal conversion errors for the JSON schema.
    # (result itself is still usable — it may be PARTIAL_SUCCESS)
    conversion_errors = [str(e) for e in result.errors] if result.errors else []

    # --- Step 2: Extract metadata ---
    metadata = extract_document_metadata(result, source_path.name)

    # --- Step 3: Build JSON ---
    try:
        doc_json = build_document_json(source_path, result, metadata)
    except Exception as exc:  # noqa: BLE001
        log.error(
            "%s — failed to build document JSON: %s",
            source_path.name,
            exc,
            exc_info=True,
        )
        row.status = "failed"
        row.error = f"JSON build error: {exc}"
        manifest.append(row)
        return row

    # --- Step 4: Save JSON ---
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{doc_json['doc_id']}.json"
    try:
        output_path.write_text(
            json.dumps(doc_json, indent=JSON_INDENT, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        log.error("%s — failed to write output JSON: %s", source_path.name, exc)
        row.status = "failed"
        row.error = f"File write error: {exc}"
        manifest.append(row)
        return row

    # --- Populate manifest row ---
    tables_flagged = sum(1 for t in doc_json["tables"] if t["risk_flag"])
    elapsed = time.perf_counter() - t0

    row.doc_id = doc_json["doc_id"]
    row.company = doc_json.get("company_name") or ""
    row.fiscal_year = doc_json.get("fiscal_year") or ""
    row.pages = doc_json["num_pages"]
    row.tables = len(doc_json["tables"])
    row.tables_flagged = tables_flagged
    row.status = "success"
    row.error = ""

    if conversion_errors:
        row.error = f"partial: {'; '.join(conversion_errors[:2])}"

    if metadata.get("needs_review"):
        row.status = "success (needs_review)"

    log.info(
        "%s — done in %.1fs  [%d pages, %d tables, %d flagged]",
        source_path.name,
        elapsed,
        row.pages,
        row.tables,
        row.tables_flagged,
    )

    manifest.append(row)
    return row


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

# File extensions that Docling supports for PDF input in this phase.
_SUPPORTED_EXTENSIONS = {".pdf"}


def run_batch(
    input_dir: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> list[ManifestRow]:
    """Process all supported documents in input_dir.

    Parameters
    ----------
    input_dir:
        Directory to scan for input documents (non-recursive).
    output_dir:
        Directory where per-document JSON files are written.
    manifest_path:
        Path to the manifest CSV (appended to if it already exists).

    Returns
    -------
    List of ManifestRow objects (one per document found).
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    manifest_path = Path(manifest_path)

    if not input_dir.exists():
        log.error("Input directory does not exist: %s", input_dir)
        sys.exit(1)

    sources = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS
    )

    if not sources:
        log.warning("No supported documents found in %s", input_dir)
        return []

    log.info(
        "=== Pensieve Phase 1 — starting batch: %d document(s) in %s ===",
        len(sources),
        input_dir,
    )

    manifest = ManifestWriter(manifest_path)
    rows: list[ManifestRow] = []

    try:
        for idx, source_path in enumerate(sources, start=1):
            log.info("[%d/%d] %s", idx, len(sources), source_path.name)
            row = process_document(source_path, output_dir, manifest)
            rows.append(row)
    finally:
        manifest.close()

    _print_summary(rows, manifest_path)
    return rows


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(rows: list[ManifestRow], manifest_path: Path) -> None:
    total = len(rows)
    successes = sum(1 for r in rows if r.status.startswith("success"))
    failures = total - successes
    total_tables = sum(r.tables for r in rows)
    total_flagged = sum(r.tables_flagged for r in rows)
    needs_review = sum(1 for r in rows if "needs_review" in r.status)

    print()
    print("=" * 60)
    print("  Pensieve Phase 1 — Batch Summary")
    print("=" * 60)
    print(f"  Documents processed : {total}")
    print(f"  Successful          : {successes}")
    print(f"  Failed              : {failures}")
    print(f"  Needs review        : {needs_review}")
    print(f"  Total tables        : {total_tables}")
    print(f"  Tables risk-flagged : {total_flagged}")
    print(f"  Manifest saved to   : {manifest_path.resolve()}")
    print("=" * 60)
    print()

    # Pretty-print the manifest as a table to stdout.
    table_data = [
        [
            r.filename,
            r.doc_id[:8] + "…" if r.doc_id else "",
            (r.company[:28] + "…") if len(r.company) > 30 else r.company,
            r.fiscal_year,
            r.pages,
            r.tables,
            r.tables_flagged,
            r.status,
            (r.error[:35] + "…") if len(r.error) > 37 else r.error,
        ]
        for r in rows
    ]

    headers = [
        "Filename", "Doc ID", "Company", "FY",
        "Pg", "Tbl", "Flag", "Status", "Error",
    ]

    print(
        tabulate(table_data, headers=headers, tablefmt="grid")
    )
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pensieve-ingest",
        description="Pensieve Phase 1 — batch document ingestion pipeline",
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing input PDFs to process.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for output JSON files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        dest="manifest",
        help=f"Path to the manifest CSV. Default: {DEFAULT_MANIFEST_PATH}",
    )

    args = parser.parse_args()

    run_batch(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        manifest_path=args.manifest,
    )


if __name__ == "__main__":
    main()
