"""
pensieve/embed_runner.py
------------------------
Phase 2 — Batch Embedding + Qdrant Upsert Runner

Processes a folder of Phase 1 JSON outputs end-to-end:
    chunk → embed → upsert

Produces a Phase 2 manifest CSV:
    filename | doc_id | company | fiscal_year | narrative_chunks | table_chunks
             | table_chunks_flagged | truncated_chunks | status | error

Usage (CLI)
-----------
    python -m pensieve.embed_runner \\
        --json-dir ./output \\
        --manifest ./manifest_phase2.csv \\
        [--provider local|openai] \\
        [--collection pensieve_chunks] \\
        [--recreate-collection]

    # Or the installed entry-point:
    pensieve-embed --json-dir ./output

Usage (programmatic)
--------------------
    from pensieve.embed_runner import run_embed_batch
    run_embed_batch(json_dir=Path("./output"))
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path

from tabulate import tabulate

from pensieve.chunker import chunk_document, Chunk
from pensieve.config import (
    DEFAULT_OUTPUT_DIR,
    EMBEDDING_PROVIDER,
    JSON_INDENT,
    QDRANT_COLLECTION,
)
from pensieve.embedder import embed_texts, get_vector_dim, get_token_limit
from pensieve.logger import get_logger
from pensieve.vector_store import get_client, ensure_collection, recreate_collection, upsert_chunks

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

_MANIFEST_FIELDS = [
    "filename",
    "doc_id",
    "company",
    "fiscal_year",
    "narrative_chunks",
    "table_chunks",
    "table_chunks_flagged",
    "truncated_chunks",
    "status",
    "error",
]


@dataclass
class EmbedManifestRow:
    filename: str
    doc_id: str = ""
    company: str = ""
    fiscal_year: str = ""
    narrative_chunks: int = 0
    table_chunks: int = 0
    table_chunks_flagged: int = 0
    truncated_chunks: int = 0
    status: str = "failed"
    error: str = ""


class EmbedManifestWriter:
    """Append-mode CSV writer — each row is flushed immediately."""

    def __init__(self, manifest_path: Path) -> None:
        self._path = manifest_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self._path.exists() or self._path.stat().st_size == 0
        self._fh = self._path.open("a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=_MANIFEST_FIELDS)
        if write_header:
            self._writer.writeheader()

    def append(self, row: EmbedManifestRow) -> None:
        d = asdict(row)
        self._writer.writerow({k: d.get(k, "") for k in _MANIFEST_FIELDS})
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


# ---------------------------------------------------------------------------
# Per-document processing
# ---------------------------------------------------------------------------

def process_json(
    json_path: Path,
    manifest: EmbedManifestWriter,
    provider: str,
    collection: str,
) -> EmbedManifestRow:
    """Load one Phase 1 JSON, chunk + embed + upsert it, write manifest row.

    Never raises — exceptions are caught and recorded in the manifest row.
    """
    row = EmbedManifestRow(filename=json_path.name)
    t0 = time.perf_counter()

    # --- Load JSON ---
    try:
        doc = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        row.error = f"JSON load error: {exc}"
        manifest.append(row)
        return row

    row.doc_id = doc.get("doc_id", "")
    row.company = doc.get("company_name") or ""
    row.fiscal_year = doc.get("fiscal_year") or ""

    # --- Chunk ---
    try:
        chunks = chunk_document(doc, provider=provider)
    except Exception as exc:  # noqa: BLE001
        log.error("%s — chunking failed: %s", json_path.name, exc, exc_info=True)
        row.error = f"Chunking error: {exc}"
        manifest.append(row)
        return row

    narrative = [c for c in chunks if c.section_type == "narrative"]
    tables = [c for c in chunks if c.section_type == "table"]
    flagged = [c for c in tables if c.risk_flag]
    truncated = [c for c in chunks if c.truncated_for_embedding]

    row.narrative_chunks = len(narrative)
    row.table_chunks = len(tables)
    row.table_chunks_flagged = len(flagged)
    row.truncated_chunks = len(truncated)

    if not chunks:
        log.warning("%s — no chunks produced; skipping embed+upsert.", json_path.name)
        row.status = "success (empty)"
        manifest.append(row)
        return row

    # --- Embed ---
    try:
        # Use embed_text for the actual embedding vector.
        texts = [c.embed_text for c in chunks]
        vectors = embed_texts(texts, provider=provider)
    except Exception as exc:  # noqa: BLE001
        log.error("%s — embedding failed: %s", json_path.name, exc, exc_info=True)
        row.error = f"Embedding error: {exc}"
        manifest.append(row)
        return row

    # --- Upsert ---
    try:
        client = get_client()
        upsert_chunks(client, chunks, vectors, collection=collection)
    except Exception as exc:  # noqa: BLE001
        log.error("%s — Qdrant upsert failed: %s", json_path.name, exc, exc_info=True)
        row.error = f"Upsert error: {exc}"
        manifest.append(row)
        return row

    elapsed = time.perf_counter() - t0
    log.info(
        "%s — done in %.1fs  [%d narrative + %d table chunks, %d flagged, %d truncated]",
        json_path.name, elapsed,
        len(narrative), len(tables), len(flagged), len(truncated),
    )
    row.status = "success"
    manifest.append(row)
    return row


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_embed_batch(
    json_dir: Path,
    manifest_path: Path = Path("./manifest_phase2.csv"),
    provider: str = EMBEDDING_PROVIDER,
    collection: str = QDRANT_COLLECTION,
    recreate: bool = False,
) -> list[EmbedManifestRow]:
    """Embed all Phase 1 JSON files in json_dir and upsert to Qdrant.

    Parameters
    ----------
    json_dir:
        Directory containing Phase 1 JSON files (*.json).
    manifest_path:
        Path to write the Phase 2 manifest CSV.
    provider:
        Embedding provider: "local" or "openai".
    collection:
        Qdrant collection name.
    recreate:
        If True, delete and recreate the collection before ingesting.

    Returns
    -------
    List of EmbedManifestRow — one per JSON file processed.
    """
    json_dir = Path(json_dir)
    if not json_dir.exists():
        log.error("JSON directory does not exist: %s", json_dir)
        sys.exit(1)

    json_files = sorted(json_dir.glob("*.json"))
    if not json_files:
        log.warning("No JSON files found in %s", json_dir)
        return []

    log.info(
        "=== Pensieve Phase 2 — starting batch: %d file(s) in %s (provider=%s) ===",
        len(json_files), json_dir, provider,
    )

    # Initialise embedding provider (triggers model download on first run).
    vector_dim = get_vector_dim(provider)
    log.info("Embedding provider: %s  |  vector dim: %d", provider, vector_dim)

    # Set up Qdrant collection.
    client = get_client()
    if recreate:
        recreate_collection(client, vector_dim, collection)
    else:
        ensure_collection(client, vector_dim, collection)

    manifest = EmbedManifestWriter(manifest_path)
    rows: list[EmbedManifestRow] = []

    try:
        for idx, json_path in enumerate(json_files, start=1):
            log.info("[%d/%d] %s", idx, len(json_files), json_path.name)
            row = process_json(json_path, manifest, provider, collection)
            rows.append(row)
    finally:
        manifest.close()

    _print_summary(rows, manifest_path, provider, collection)
    return rows


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(
    rows: list[EmbedManifestRow],
    manifest_path: Path,
    provider: str,
    collection: str,
) -> None:
    total = len(rows)
    successes = sum(1 for r in rows if r.status.startswith("success"))
    failures = total - successes
    total_narrative = sum(r.narrative_chunks for r in rows)
    total_tables = sum(r.table_chunks for r in rows)
    total_flagged = sum(r.table_chunks_flagged for r in rows)
    total_truncated = sum(r.truncated_chunks for r in rows)

    print()
    print("=" * 66)
    print("  Pensieve Phase 2 — Embedding Batch Summary")
    print("=" * 66)
    print(f"  JSON files processed  : {total}")
    print(f"  Successful            : {successes}")
    print(f"  Failed                : {failures}")
    print(f"  Narrative chunks      : {total_narrative}")
    print(f"  Table chunks          : {total_tables}")
    print(f"  Table chunks flagged  : {total_flagged}")
    print(f"  Truncated for embed   : {total_truncated}")
    print(f"  Embedding provider    : {provider}")
    print(f"  Qdrant collection     : {collection}")
    print(f"  Manifest saved to     : {manifest_path.resolve()}")
    print("=" * 66)
    print()

    table_data = [
        [
            r.filename,
            r.doc_id[:8] + "…" if r.doc_id else "",
            (r.company[:24] + "…") if len(r.company) > 26 else r.company,
            r.fiscal_year,
            r.narrative_chunks,
            r.table_chunks,
            r.table_chunks_flagged,
            r.truncated_chunks,
            r.status,
            (r.error[:30] + "…") if len(r.error) > 32 else r.error,
        ]
        for r in rows
    ]

    headers = [
        "Filename", "Doc ID", "Company", "FY",
        "Narr", "Tbl", "Flag", "Trunc", "Status", "Error",
    ]
    print(tabulate(table_data, headers=headers, tablefmt="simple"))
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pensieve-embed",
        description="Pensieve Phase 2 — batch embedding + Qdrant upsert pipeline",
    )
    parser.add_argument(
        "--json-dir",
        required=True,
        type=Path,
        help="Directory containing Phase 1 JSON output files.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("./manifest_phase2.csv"),
        help="Path to the Phase 2 manifest CSV. Default: ./manifest_phase2.csv",
    )
    parser.add_argument(
        "--provider",
        choices=["local", "openai"],
        default=EMBEDDING_PROVIDER,
        help=f"Embedding provider. Default: {EMBEDDING_PROVIDER}",
    )
    parser.add_argument(
        "--collection",
        default=QDRANT_COLLECTION,
        help=f"Qdrant collection name. Default: {QDRANT_COLLECTION}",
    )
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        default=False,
        help="Delete and recreate the Qdrant collection before ingesting (wipes existing vectors).",
    )

    args = parser.parse_args()
    run_embed_batch(
        json_dir=args.json_dir,
        manifest_path=args.manifest,
        provider=args.provider,
        collection=args.collection,
        recreate=args.recreate_collection,
    )


if __name__ == "__main__":
    main()
