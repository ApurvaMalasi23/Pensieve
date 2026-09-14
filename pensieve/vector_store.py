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


def get_client(refresh: bool = False) -> QdrantClient:
    """Return a (cached) Qdrant client connected to QDRANT_URL."""
    global _client  # noqa: PLW0603
    if _client is None or refresh:
        log.info("Connecting to Qdrant at %s", QDRANT_URL)
        kwargs: dict = {"url": QDRANT_URL, "timeout": 120.0}
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
    """
    existing = set()
    import time
    for attempt in range(1, 4):
        try:
            existing = {c.name for c in client.get_collections().collections}
            break
        except Exception as exc:
            if attempt == 3:
                log.error("Failed to connect to Qdrant after 3 attempts: %s", exc)
                raise
            log.warning("Connecting to Qdrant attempt %d failed (%s). Retrying in 3s...", attempt, exc)
            time.sleep(3.0)

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
        info = None
        for attempt in range(1, 4):
            try:
                info = client.get_collection(collection_name=collection)
                break
            except Exception as exc:
                if attempt == 3:
                    raise
                time.sleep(2.0)
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

# Batch size for upserting points to Qdrant. Smaller batches prevent HTTP write timeouts.
UPSERT_BATCH_SIZE: int = 32


def upsert_chunks(
    client: QdrantClient,
    chunks: list["Chunk"],
    vectors: list[list[float]],
    collection: str = QDRANT_COLLECTION,
) -> None:
    """Upsert chunk points (vectors + metadata payloads) into Qdrant."""
    if not chunks:
        log.warning("upsert_chunks called with empty chunk list — nothing to do.")
        return

    if len(chunks) != len(vectors):
        raise ValueError(
            f"Chunk count ({len(chunks)}) does not match vector count ({len(vectors)})."
        )

    points: list[qmodels.PointStruct] = []
    for chunk, vector in zip(chunks, vectors, strict=True):
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

    # Upsert in small batches with retry to prevent network timeouts to Qdrant Cloud
    total = len(points)
    import time
    for i in range(0, total, UPSERT_BATCH_SIZE):
        batch = points[i : i + UPSERT_BATCH_SIZE]
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                client.upsert(collection_name=collection, points=batch, wait=True)
                break
            except Exception as exc:
                if attempt == max_attempts:
                    log.error("Failed to upsert batch %d-%d after %d attempts: %s", i + 1, min(i + UPSERT_BATCH_SIZE, total), max_attempts, exc)
                    raise
                log.warning("Batch %d-%d upsert attempt %d failed (%s). Retrying in 2s...", i + 1, min(i + UPSERT_BATCH_SIZE, total), attempt, exc)
                time.sleep(2.0)
        log.info("Upserted points %d-%d / %d", i + 1, min(i + UPSERT_BATCH_SIZE, total), total)

    log.info("Successfully upserted %d point(s) into collection '%s'.", total, collection)


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
