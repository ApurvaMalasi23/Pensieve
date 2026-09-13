"""
pensieve/retriever.py
---------------------
Phase 3 + 4 — Qdrant Retrieval for Narrative and Table Chunks

Phase 3: retrieve_narrative_chunks — always filters section_type="narrative".
Phase 4: retrieve_table_chunks — always filters section_type="table";
          populates table-specific fields (table_id, risk_flag, risk_reasons).

Public API
----------
    RetrievedChunk
    retrieve_narrative_chunks(query, top_k=6, ...) -> list[RetrievedChunk]
    retrieve_table_chunks(query, top_k=3, ...) -> list[RetrievedChunk]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from pensieve.config import (
    EMBEDDING_PROVIDER,
    NUMERIC_RETRIEVAL_TOP_K,
    QDRANT_COLLECTION,
    RETRIEVAL_SIMILARITY_THRESHOLD,
    RETRIEVAL_TOP_K_DEFAULT,
)
from pensieve.embedder import embed_texts
from pensieve.logger import get_logger
from pensieve.vector_store import get_client

log = get_logger(__name__)


@dataclass
class RetrievedChunk:
    """Represents a retrieved chunk with its source metadata and similarity score.

    Table-specific fields (table_id, risk_flag, risk_reasons, rows, cols) are
    populated for section_type='table' chunks and left as defaults for narrative.
    """

    chunk_id: str
    doc_id: str
    source_filename: str
    company_name: str | None
    fiscal_year: str | None
    section_type: str
    page_start: int
    page_end: int
    text: str
    score: float

    # Table-specific fields (None/False/[] for narrative chunks)
    table_id: str | None = None
    risk_flag: bool = False
    risk_reasons: list[str] = field(default_factory=list)
    rows: int | None = None
    cols: int | None = None

    @classmethod
    def from_qdrant_point(cls, point: Any) -> RetrievedChunk:
        """Construct a RetrievedChunk from a Qdrant ScoredPoint object."""
        payload = point.payload or {}
        return cls(
            chunk_id=str(payload.get("chunk_id", "")),
            doc_id=str(payload.get("doc_id", "")),
            source_filename=str(payload.get("source_filename", "")),
            company_name=payload.get("company_name"),
            fiscal_year=payload.get("fiscal_year"),
            section_type=str(payload.get("section_type", "narrative")),
            page_start=int(payload.get("page_start", 0)),
            page_end=int(payload.get("page_end", 0)),
            text=str(payload.get("text", "")),
            score=float(point.score),
            # Table-specific fields
            table_id=payload.get("table_id"),
            risk_flag=bool(payload.get("risk_flag", False)),
            risk_reasons=list(payload.get("risk_reasons") or []),
            rows=payload.get("rows"),
            cols=payload.get("cols"),
        )


def retrieve_narrative_chunks(
    query: str,
    top_k: int = RETRIEVAL_TOP_K_DEFAULT,
    company_name: str | None = None,
    fiscal_year: str | None = None,
    threshold: float | None = None,
    client: QdrantClient | None = None,
    collection: str = QDRANT_COLLECTION,
    provider: str = EMBEDDING_PROVIDER,
) -> list[RetrievedChunk]:
    """Retrieve narrative chunks from Qdrant matching the given semantic query.

    Strictly applies a filter for `section_type == "narrative"`. Table chunks
    are never returned in Phase 3.

    Parameters
    ----------
    query:
        The user question or query string.
    top_k:
        Maximum number of chunks to return (default: RETRIEVAL_TOP_K_DEFAULT).
    company_name:
        Optional exact match filter on company_name.
    fiscal_year:
        Optional exact match filter on fiscal_year.
    threshold:
        Cosine similarity threshold. Hits below this score are discarded.
        Defaults to RETRIEVAL_SIMILARITY_THRESHOLD config constant.
    client:
        Optional QdrantClient. Defaults to global singleton via get_client().
    collection:
        Qdrant collection name. Defaults to QDRANT_COLLECTION.
    provider:
        Embedding provider matching Phase 2 ingestion (default: EMBEDDING_PROVIDER).

    Returns
    -------
    list[RetrievedChunk]:
        List of chunks sorted by similarity score descending, or an empty list
        if no chunks score above the threshold.
    """
    clean_query = query.strip()
    if not clean_query:
        log.warning("Empty query passed to retrieve_narrative_chunks.")
        return []

    min_score = threshold if threshold is not None else RETRIEVAL_SIMILARITY_THRESHOLD

    # 1. Embed the query using the exact same provider and model as ingestion.
    log.debug("Embedding query (provider=%s): %r", provider, clean_query)
    embeddings = embed_texts([clean_query], provider=provider)
    if not embeddings:
        log.error("Failed to generate embedding for query.")
        return []
    query_vector = embeddings[0]

    # 2. Build Qdrant payload filter.
    # RULE: section_type="narrative" is ALWAYS applied in Phase 3.
    must_conditions: list[qmodels.Condition] = [
        qmodels.FieldCondition(
            key="section_type",
            match=qmodels.MatchValue(value="narrative"),
        )
    ]

    if company_name:
        must_conditions.append(
            qmodels.FieldCondition(
                key="company_name",
                match=qmodels.MatchValue(value=company_name),
            )
        )

    if fiscal_year:
        must_conditions.append(
            qmodels.FieldCondition(
                key="fiscal_year",
                match=qmodels.MatchValue(value=fiscal_year),
            )
        )

    query_filter = qmodels.Filter(must=must_conditions)

    # 3. Query Qdrant
    qdrant = client if client is not None else get_client()
    log.debug(
        "Querying collection '%s' (top_k=%d, company=%s, year=%s, min_score=%.2f)",
        collection,
        top_k,
        company_name,
        fiscal_year,
        min_score,
    )

    results = qdrant.query_points(
        collection_name=collection,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )

    points = results.points if hasattr(results, "points") else results

    # 4. Filter by score threshold and convert to RetrievedChunk
    retrieved: list[RetrievedChunk] = []
    for pt in points:
        chunk = RetrievedChunk.from_qdrant_point(pt)
        if chunk.score >= min_score:
            retrieved.append(chunk)
        else:
            log.debug(
                "Dropping chunk %s with score %.4f below threshold %.4f",
                chunk.chunk_id,
                chunk.score,
                min_score,
            )

    log.info(
        "Retrieved %d narrative chunk(s) (out of %d Qdrant hit(s)) above threshold %.2f",
        len(retrieved),
        len(points),
        min_score,
    )
    return retrieved


def retrieve_table_chunks(
    query: str,
    top_k: int = NUMERIC_RETRIEVAL_TOP_K,
    company_name: str | None = None,
    fiscal_year: str | None = None,
    threshold: float | None = None,
    client: QdrantClient | None = None,
    collection: str = QDRANT_COLLECTION,
    provider: str = EMBEDDING_PROVIDER,
) -> list[RetrievedChunk]:
    """Retrieve table chunks from Qdrant matching the given semantic query.

    Phase 4 counterpart to retrieve_narrative_chunks. Always applies
    ``section_type == "table"`` filter. Returns full untruncated table content
    (from ``payload.text``) plus table-specific fields (table_id, risk_flag,
    risk_reasons, rows, cols).

    Parameters
    ----------
    query:
        The user question or query string.
    top_k:
        Maximum number of table chunks to return (default: NUMERIC_RETRIEVAL_TOP_K=3).
        Intentionally smaller than narrative top_k — whole tables are large.
    company_name:
        Optional exact match filter on company_name.
    fiscal_year:
        Optional exact match filter on fiscal_year.
    threshold:
        Cosine similarity threshold. Hits below this score are discarded.
        Defaults to RETRIEVAL_SIMILARITY_THRESHOLD config constant.
    client:
        Optional QdrantClient. Defaults to global singleton via get_client().
    collection:
        Qdrant collection name. Defaults to QDRANT_COLLECTION.
    provider:
        Embedding provider — must match Phase 2 ingestion (default: EMBEDDING_PROVIDER).

    Returns
    -------
    list[RetrievedChunk]:
        Table chunks sorted by similarity score descending, or [] if no chunks
        score above the threshold.
    """
    clean_query = query.strip()
    if not clean_query:
        log.warning("Empty query passed to retrieve_table_chunks.")
        return []

    min_score = threshold if threshold is not None else RETRIEVAL_SIMILARITY_THRESHOLD

    # 1. Embed the query using the exact same provider as ingestion.
    log.debug("Embedding query for table retrieval (provider=%s): %r", provider, clean_query)
    embeddings = embed_texts([clean_query], provider=provider)
    if not embeddings:
        log.error("Failed to generate embedding for table query.")
        return []
    query_vector = embeddings[0]

    # 2. Build Qdrant payload filter.
    # RULE: section_type="table" is ALWAYS applied for Phase 4 numeric retrieval.
    must_conditions: list[qmodels.Condition] = [
        qmodels.FieldCondition(
            key="section_type",
            match=qmodels.MatchValue(value="table"),
        )
    ]

    if company_name:
        must_conditions.append(
            qmodels.FieldCondition(
                key="company_name",
                match=qmodels.MatchValue(value=company_name),
            )
        )

    if fiscal_year:
        must_conditions.append(
            qmodels.FieldCondition(
                key="fiscal_year",
                match=qmodels.MatchValue(value=fiscal_year),
            )
        )

    query_filter = qmodels.Filter(must=must_conditions)

    # 3. Query Qdrant
    qdrant = client if client is not None else get_client()
    log.debug(
        "Table query: collection='%s' top_k=%d company=%s year=%s min_score=%.2f",
        collection,
        top_k,
        company_name,
        fiscal_year,
        min_score,
    )

    results = qdrant.query_points(
        collection_name=collection,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )

    points = results.points if hasattr(results, "points") else results

    # 4. Filter by score threshold and convert to RetrievedChunk (with table fields)
    retrieved: list[RetrievedChunk] = []
    for pt in points:
        chunk = RetrievedChunk.from_qdrant_point(pt)
        if chunk.score >= min_score:
            retrieved.append(chunk)
        else:
            log.debug(
                "Dropping table chunk %s (page %d) with score %.4f below threshold %.4f",
                chunk.chunk_id,
                chunk.page_start,
                chunk.score,
                min_score,
            )

    log.info(
        "Retrieved %d table chunk(s) (out of %d Qdrant hit(s)) above threshold %.2f",
        len(retrieved),
        len(points),
        min_score,
    )
    return retrieved
