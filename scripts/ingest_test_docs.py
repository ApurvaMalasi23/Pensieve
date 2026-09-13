"""
scripts/ingest_test_docs.py
----------------------------
Ingest TEST DOC - 3.pdf, TEST DOC - 4.pdf, and TEST DOC - 5.pdf
through Phase 1 (Docling conversion, LLM metadata extraction, risk flagging)
and Phase 2 (chunking, embedding with bge-small-en-v1.5, Qdrant upsert).
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

from pensieve.batch_runner import ManifestWriter, process_document
from pensieve.config import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_OUTPUT_DIR,
    EMBEDDING_PROVIDER,
    QDRANT_COLLECTION,
)
from pensieve.embed_runner import EmbedManifestWriter, process_json
from pensieve.embedder import get_vector_dim
from pensieve.logger import get_logger
from pensieve.vector_store import ensure_collection, get_client

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

log = get_logger("pensieve.ingest_test_docs")

DEFAULT_DOCS = [
    Path("TEST DOC - 3.pdf"),
    Path("TEST DOC - 4.pdf"),
    Path("TEST DOC - 5.pdf"),
]


def ingest_documents(
    doc_paths: list[Path],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    manifest_phase1: Path = DEFAULT_MANIFEST_PATH,
    manifest_phase2: Path = Path("./manifest_phase2.csv"),
    provider: str = EMBEDDING_PROVIDER,
    collection: str = QDRANT_COLLECTION,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize Qdrant collection
    dim = get_vector_dim(provider)
    client = get_client()
    ensure_collection(client, dim, collection)

    p1_writer = ManifestWriter(manifest_phase1)
    p2_writer = EmbedManifestWriter(manifest_phase2)

    total_docs = len(doc_paths)
    print(f"\n=======================================================")
    print(f" Starting Ingestion of {total_docs} Documents into Pensieve")
    print(f" Output dir: {output_dir}")
    print(f" Qdrant collection: {collection} (dim={dim}, provider={provider})")
    print(f"=======================================================\n")

    for i, doc_path in enumerate(doc_paths, 1):
        if not doc_path.exists():
            print(f"[{i}/{total_docs}] ERROR: File not found: {doc_path}")
            continue

        print(f"\n>>> [{i}/{total_docs}] Processing Phase 1 for {doc_path.name}...")
        t_start = time.perf_counter()

        # Step 1: Phase 1 Ingestion
        row_p1 = process_document(doc_path, output_dir, p1_writer)
        print(f"    Phase 1 Result: status={row_p1.status}, doc_id={row_p1.doc_id}, company='{row_p1.company}', FY='{row_p1.fiscal_year}', pages={row_p1.pages}, tables={row_p1.tables} (flagged={row_p1.tables_flagged})")

        if not row_p1.doc_id or row_p1.status == "failed":
            print(f"    Phase 1 failed for {doc_path.name}: {row_p1.error}. Skipping Phase 2.")
            continue

        # Step 2: Phase 2 Chunking & Vector Upsert
        json_path = output_dir / f"{row_p1.doc_id}.json"
        print(f">>> [{i}/{total_docs}] Processing Phase 2 (Embedding & Upsert) for {json_path.name}...")
        row_p2 = process_json(json_path, p2_writer, provider=provider, collection=collection)
        print(f"    Phase 2 Result: status={row_p2.status}, narrative={row_p2.narrative_chunks}, tables={row_p2.table_chunks} (flagged={row_p2.table_chunks_flagged}), truncated={row_p2.truncated_chunks}")

        elapsed = time.perf_counter() - t_start
        print(f">>> [{i}/{total_docs}] Completed {doc_path.name} in {elapsed:.1f}s\n")

    p1_writer.close()
    p2_writer.close()

    print("\n=======================================================")
    print(" Ingestion complete for all target documents.")
    print("=======================================================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest specific test documents")
    parser.add_argument("docs", nargs="*", default=[str(p) for p in DEFAULT_DOCS])
    args = parser.parse_args()

    target_paths = [Path(d) for d in args.docs]
    ingest_documents(target_paths)
