"""
pensieve/vector_store.py
------------------------
Phase 2 — Qdrant Vector Store Management

Manages the Qdrant collection lifecycle and chunk upserts.

Public API
----------
    get_client() -> QdrantClient
    ensure_collection(client, vector_dim) -> None
    upsert_chunks(client, chunks, vectors) -> None
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from pensieve.config import (
    EMBEDDING_BATCH_SIZE,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_URL,
)
from pensieve.logger import get_logger

if TYPE_CHECKING:
    from pensieve.chunker import Chunk

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_client: QdrantClient | None = None  # module-level singleton


def get_client() -> QdrantClient:
    """Return a (cached) Qdrant client connected to QDRANT_URL."""
    global _client  # noqa: PLW0603
    if _client is None:
        log.info("Connecting to Qdrant at %s", QDRANT_URL)
        kwargs: dict = {"url": QDRANT_URL}
        if QDRANT_API_KEY:
            kwargs["api_key"] = QDRANT_API_KEY
        _client = QdrantClient(**kwargs, check_compatibility=False)
    return _client


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------

#: Payload fields that get a server-side index for fast filtering.
_INDEXED_FIELDS: list[tuple[str, qmodels.PayloadSchemaType]] = [
    ("company_name",  qmodels.PayloadSchemaType.KEYWORD),
    ("fiscal_year",   qmodels.PayloadSchemaType.KEYWORD),
    ("section_type",  qmodels.PayloadSchemaType.KEYWORD),
    ("risk_flag",     qmodels.PayloadSchemaType.BOOL),
]


def ensure_collection(
    client: QdrantClient,
    vector_dim: int,
    collection: str = QDRANT_COLLECTION,
) -> None:
    """Create the Qdrant collection if it doesn't exist; verify dim if it does.

    Also ensures payload indexes on company_name, fiscal_year, section_type,
    and risk_flag are present so Phase 5 filtered queries are fast.

    Parameters
    ----------
    client:
        Connected QdrantClient.
    vector_dim:
        Embedding vector dimension. Must match the collection's config if the
        collection already exists — raises ValueError on mismatch.
    collection:
        Collection name. Defaults to QDRANT_COLLECTION config constant.

    Raises
    ------
    ValueError
        If the collection exists but its vector dimension doesn't match vector_dim.
    """
    existing = {c.name for c in client.get_collections().collections}

    if collection not in existing:
        log.info(
            "Creating Qdrant collection '%s' (dim=%d, metric=Cosine)", collection, vector_dim
        )
        client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(
                size=vector_dim,
                distance=qmodels.Distance.COSINE,
            ),
        )
    else:
        # Verify dimension matches.
        info = client.get_collection(collection_name=collection)
        existing_dim = info.config.params.vectors.size
        if existing_dim != vector_dim:
            raise ValueError(
                f"Qdrant collection '{collection}' already exists with vector dimension "
                f"{existing_dim}, but the active embedding provider produces dimension "
                f"{vector_dim}. Either delete the collection, use --recreate-collection, "
                f"or switch back to the original embedding provider."
            )
        log.info("Collection '%s' already exists (dim=%d) — reusing.", collection, existing_dim)

    # Create payload indexes (idempotent — Qdrant ignores duplicates).
    for field_name, schema_type in _INDEXED_FIELDS:
        try:
            client.create_payload_index(
                collection_name=collection,
                field_name=field_name,
                field_schema=schema_type,
            )
            log.debug("Payload index ensured: %s (%s)", field_name, schema_type)
        except Exception as exc:  # noqa: BLE001
            # Qdrant raises if the index already exists with identical config on
            # some versions; treat as non-fatal.
            log.debug("Payload index '%s' may already exist: %s", field_name, exc)


# ---------------------------------------------------------------------------
# Point ID derivation
# ---------------------------------------------------------------------------

def _chunk_id_to_point_id(chunk_id: str) -> int:
    """Convert a hex chunk_id to a Qdrant numeric point ID.

    Qdrant requires unsigned 64-bit integer point IDs.  We derive a stable
    integer by taking the first 16 hex characters of SHA-256(chunk_id) and
    interpreting them as a 64-bit integer.  This is deterministic, collision-
    resistant, and produces IDs in [0, 2^64) — all valid for Qdrant.
    """
    digest = hashlib.sha256(chunk_id.encode()).hexdigest()
    return int(digest[:16], 16)


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def upsert_chunks(
    client: QdrantClient,
    chunks: list["Chunk"],
    vectors: list[list[float]],
    collection: str = QDRANT_COLLECTION,
) -> None:
    """Upsert chunk embeddings + payloads into the Qdrant collection.

    Parameters
    ----------
    client:
        Connected QdrantClient.
    chunks:
        List of Chunk dataclass instances (same order as vectors).
    vectors:
        List of embedding vectors, one per chunk.
    collection:
        Collection name. Defaults to QDRANT_COLLECTION.
    """
    if len(chunks) != len(vectors):
        raise ValueError(
            f"chunks ({len(chunks)}) and vectors ({len(vectors)}) must have the same length."
        )

    points: list[qmodels.PointStruct] = []
    for chunk, vector in zip(chunks, vectors):
        payload = {
            "chunk_id":               chunk.chunk_id,
            "doc_id":                 chunk.doc_id,
            "source_filename":        chunk.source_filename,
            "company_name":           chunk.company_name,
            "fiscal_year":            chunk.fiscal_year,
            "reporting_period_type":  chunk.reporting_period_type,
            "section_type":           chunk.section_type,
            "page_start":             chunk.page_start,
            "page_end":               chunk.page_end,
            # text stores the FULL content (even if embed_text was truncated)
            "text":                   chunk.text,
            "table_id":               chunk.table_id,
            "risk_flag":              chunk.risk_flag,
            "risk_reasons":           chunk.risk_reasons,
            "rows":                   chunk.rows,
            "cols":                   chunk.cols,
            "truncated_for_embedding": chunk.truncated_for_embedding,
        }
        points.append(
            qmodels.PointStruct(
                id=_chunk_id_to_point_id(chunk.chunk_id),
                vector=vector,
                payload=payload,
            )
        )

    # Upsert in batches.
    total = len(points)
    for i in range(0, total, EMBEDDING_BATCH_SIZE):
        batch = points[i : i + EMBEDDING_BATCH_SIZE]
        client.upsert(collection_name=collection, points=batch, wait=True)
        log.debug("Upserted points %d-%d / %d", i + 1, min(i + EMBEDDING_BATCH_SIZE, total), total)

    log.info("Upserted %d point(s) into collection '%s'.", total, collection)


# ---------------------------------------------------------------------------
# Collection recreation helper (used by CLI --recreate-collection flag)
# ---------------------------------------------------------------------------

def recreate_collection(
    client: QdrantClient,
    vector_dim: int,
    collection: str = QDRANT_COLLECTION,
) -> None:
    """Delete the collection if it exists, then recreate it fresh."""
    existing = {c.name for c in client.get_collections().collections}
    if collection in existing:
        log.warning("Deleting existing collection '%s' (--recreate-collection).", collection)
        client.delete_collection(collection_name=collection)
    ensure_collection(client, vector_dim, collection)
