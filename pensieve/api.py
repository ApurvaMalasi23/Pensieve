"""
pensieve/api.py
---------------
Phase 3 + 4 — FastAPI Backend for Pensieve RAG

Exposes:
    POST /query  - Narrative-only RAG retrieval and grounded generation with citations.
    POST /ask    - Intent-routing endpoint: classifies query as narrative or numeric,
                   routes to appropriate pipeline, and includes numeric verification.
    GET  /health - Health check verifying Qdrant connectivity and collection status.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from typing import Any
import uuid

import uvicorn
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pensieve.classifier import classify_intent
from pensieve.chunker import chunk_document
from pensieve.config import (
    DEFAULT_OUTPUT_DIR,
    EMBEDDING_PROVIDER,
    GENERATION_LLM_MODEL,
    JSON_INDENT,
    NUMERIC_RETRIEVAL_TOP_K,
    QDRANT_COLLECTION,
    QDRANT_URL,
    RATE_LIMIT_ASK_PER_MINUTE,
    RETRIEVAL_TOP_K_DEFAULT,
    SHOWCASE_MODE,
)
from pensieve.comparator import (
    ComparisonEntity,
    detect_comparison_intent,
    execute_comparison,
)
from pensieve.embedder import embed_texts, get_vector_dim
from pensieve.generator import generate_answer, parse_citations
from pensieve.logger import get_logger
from pensieve.metadata_extractor import extract_document_metadata
from pensieve.numeric_grounding import (
    VerificationResult,
    extract_numbers_from_text,
    fit_tables_to_context,
    generate_numeric_answer,
    verify_numbers_against_grid,
)
from pensieve.retriever import retrieve_narrative_chunks, retrieve_table_chunks
from pensieve.structurer import build_document_json
from pensieve.vector_store import ensure_collection, get_client, upsert_chunks
from qdrant_client.http import models as qmodels

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory sliding window rate limiting
# ---------------------------------------------------------------------------
_ip_request_timestamps: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()


def check_rate_limit(
    request: Request,
    max_requests: int | None = None,
    window_seconds: float = 60.0,
) -> None:
    """Lightweight in-memory sliding window rate limiter per client IP."""
    if max_requests is None:
        max_requests = RATE_LIMIT_ASK_PER_MINUTE

    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    now = time.time()
    with _rate_limit_lock:
        timestamps = _ip_request_timestamps[client_ip]
        valid_timestamps = [t for t in timestamps if now - t < window_seconds]
        if len(valid_timestamps) >= max_requests:
            retry_after = int(window_seconds - (now - valid_timestamps[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({max_requests} inquiries/min). Please wait {retry_after}s before submitting additional questions.",
                headers={"Retry-After": str(max(1, retry_after))},
            )
        valid_timestamps.append(now)
        _ip_request_timestamps[client_ip] = valid_timestamps


app = FastAPI(
    title="Pensieve API",
    description="Financial-report document intelligence and grounded citation RAG",
    version="0.1.0",
)

# Enable CORS for Next.js frontend integration (Phase 6)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:[0-9]+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="Natural language question to answer from narrative documents.",
        examples=["What are Republic Bancorp's primary lending activities?"],
    )
    company_name: str | None = Field(
        None,
        description="Optional exact match filter for company name.",
        examples=["Republic Bancorp"],
    )
    fiscal_year: str | None = Field(
        None,
        description="Optional exact match filter for fiscal year.",
        examples=["2024"],
    )
    top_k: int | None = Field(
        RETRIEVAL_TOP_K_DEFAULT,
        ge=1,
        le=20,
        description="Maximum number of chunks to retrieve.",
    )


class CitationSchema(BaseModel):
    marker: str = Field(..., description="Citation marker used in the answer text, e.g. [1]")
    chunk_id: str = Field(..., description="Chunk identifier")
    doc_id: str = Field(..., description="Document hash identifier")
    source_filename: str = Field(..., description="Source PDF filename")
    company_name: str | None = Field(None, description="Company name associated with chunk")
    fiscal_year: str | None = Field(None, description="Fiscal year of the report")
    page_start: int = Field(..., description="Starting page number (1-indexed)")
    page_end: int = Field(..., description="Ending page number (1-indexed)")
    excerpt: str = Field(..., description="Text excerpt of the cited chunk")


class TableCitationSchema(BaseModel):
    """Extended citation schema for table chunks — adds table-specific quality fields."""

    marker: str = Field(..., description="Citation marker used in the answer text, e.g. [1]")
    chunk_id: str = Field(..., description="Chunk identifier")
    doc_id: str = Field(..., description="Document hash identifier")
    source_filename: str = Field(..., description="Source PDF filename")
    company_name: str | None = Field(None, description="Company name associated with chunk")
    fiscal_year: str | None = Field(None, description="Fiscal year of the report")
    page_start: int = Field(..., description="Starting page number (1-indexed)")
    page_end: int = Field(..., description="Ending page number (1-indexed)")
    table_id: str | None = Field(None, description="Table identifier from Phase 1 extraction")
    risk_flag: bool = Field(False, description="True if Pensieve flagged this table for potential extraction issues")
    risk_reasons: list[str] = Field(default_factory=list, description="Extraction quality warning details")
    excerpt: str = Field(..., description="Text excerpt (first 300 chars of the table markdown)")


class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: list[CitationSchema]
    no_context_found: bool


class VerificationSchema(BaseModel):
    """Programmatic numeric verification result for /ask numeric responses."""

    status: str = Field(
        ...,
        description=(
            "'verified': figures found in clean tables. "
            "'verified_low_confidence': figures found but table has extraction warnings. "
            "'unverified': figures not found in any retrieved table. "
            "'not_applicable': answer contains no numeric figures, or narrative intent."
        ),
    )
    reason: str = Field(..., description="Human-readable explanation of the verification outcome.")


class AskRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="Natural language question — intent is auto-classified (narrative vs. numeric).",
        examples=["What were total deposits as of December 31, 2024?"],
    )
    company_name: str | None = Field(
        None,
        description="Optional exact match filter for company name.",
    )
    fiscal_year: str | None = Field(
        None,
        description="Optional exact match filter for fiscal year.",
    )
    top_k: int | None = Field(
        None,
        ge=1,
        le=20,
        description=(
            "Maximum chunks to retrieve. Defaults to RETRIEVAL_TOP_K_DEFAULT for narrative, "
            "NUMERIC_RETRIEVAL_TOP_K for numeric."
        ),
    )


class PerEntityResultSchema(BaseModel):
    """Execution and verification outcome for a single entity in a comparison."""

    entity: dict[str, Any]
    intent: str
    answer: str
    verification_status: str
    verification_reason: str
    citations: list[dict[str, Any]]
    numbers_extracted: list[str] = Field(default_factory=list)
    risk_flag: bool = False
    risk_reasons: list[str] = Field(default_factory=list)


class AskResponse(BaseModel):
    query: str
    intent: str = Field(..., description="'narrative' or 'numeric' — as classified by the router.")
    answer: str
    citations: list[TableCitationSchema | CitationSchema]
    verification: VerificationSchema
    no_context_found: bool
    comparison: bool = Field(False, description="True if query was processed as a multi-document comparison.")
    entities_compared: list[dict[str, Any]] = Field(default_factory=list, description="List of entity targets compared.")
    per_entity_results: list[PerEntityResultSchema] = Field(default_factory=list, description="Detailed per-entity answers and verification.")
    deltas: dict[str, Any] | None = Field(None, description="Programmatically calculated numerical deltas if numeric comparison.")


class HealthResponse(BaseModel):
    status: str
    qdrant_connected: bool
    collection: str
    points_count: int
    active_generation_model: str
    showcase_mode: bool = False
    detail: str | None = None


class UploadResponse(BaseModel):
    job_id: str
    status: str


class DocumentStatusResponse(BaseModel):
    job_id: str
    status: str
    doc_id: str | None = None
    company_name: str | None = None
    fiscal_year: str | None = None
    error: str | None = None
    progress_message: str | None = None


class DocumentItemSchema(BaseModel):
    doc_id: str
    company_name: str
    fiscal_year: str
    reporting_period_type: str
    num_pages: int
    narrative_chunks: int
    table_chunks: int
    table_chunks_flagged: int


class DeleteDocumentResponse(BaseModel):
    deleted: bool
    doc_id: str
    chunks_removed: int


# ---------------------------------------------------------------------------
# Background Job State for Asynchronous Ingestion
# ---------------------------------------------------------------------------

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _run_ingestion_job(job_id: str, file_path: Path, filename: str) -> None:
    """Worker task executing Phase 1 and Phase 2 document ingestion."""
    try:
        log.info("[Job %s] Starting background ingestion for %s", job_id, filename)
        with _jobs_lock:
            _jobs[job_id]["status"] = "processing"
            _jobs[job_id]["progress_message"] = "Converting PDF document with Docling..."

        # Phase 1: Convert document (lazy-loaded so API server starts instantly)
        from pensieve.converter import convert_document

        result = convert_document(file_path)
        if result is None:
            log.error("[Job %s] Conversion failed for %s", job_id, filename)
            with _jobs_lock:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = "Docling conversion returned None. Check document format or OCR requirements."
                _jobs[job_id]["progress_message"] = "Conversion failed."
            return

        with _jobs_lock:
            _jobs[job_id]["progress_message"] = "Extracting document metadata..."

        metadata = extract_document_metadata(result, filename)

        with _jobs_lock:
            _jobs[job_id]["progress_message"] = "Structuring document JSON and risk flagging..."

        doc_json = build_document_json(file_path, result, metadata)

        # Save Phase 1 output JSON
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_json_path = DEFAULT_OUTPUT_DIR / f"{doc_json['doc_id']}.json"
        out_json_path.write_text(
            json.dumps(doc_json, indent=JSON_INDENT, ensure_ascii=False),
            encoding="utf-8",
        )

        with _jobs_lock:
            _jobs[job_id]["doc_id"] = doc_json["doc_id"]
            _jobs[job_id]["company_name"] = doc_json.get("company_name")
            _jobs[job_id]["fiscal_year"] = doc_json.get("fiscal_year")
            _jobs[job_id]["progress_message"] = "Chunking document..."

        # Phase 2: Chunking, Embedding, Qdrant Upsert
        chunks = chunk_document(doc_json, provider=EMBEDDING_PROVIDER)
        if not chunks:
            log.warning("[Job %s] No chunks produced for %s", job_id, filename)
            with _jobs_lock:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["progress_message"] = "Document processed but generated 0 chunks."
            return

        with _jobs_lock:
            _jobs[job_id]["progress_message"] = f"Embedding {len(chunks)} chunks..."

        texts = [c.embed_text for c in chunks]
        vectors = embed_texts(texts, provider=EMBEDDING_PROVIDER)

        with _jobs_lock:
            _jobs[job_id]["progress_message"] = "Upserting vectors into Qdrant..."

        client = get_client()
        dim = get_vector_dim(EMBEDDING_PROVIDER)
        ensure_collection(client, dim, collection=QDRANT_COLLECTION)
        upsert_chunks(client, chunks, vectors, collection=QDRANT_COLLECTION)

        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["progress_message"] = "Ingestion complete."
        log.info("[Job %s] Successfully finished ingestion for %s (doc_id=%s)", job_id, filename, doc_json["doc_id"])

    except Exception as exc:
        log.exception("[Job %s] Exception in background ingestion for %s: %s", job_id, filename, exc)
        with _jobs_lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(exc)
            _jobs[job_id]["progress_message"] = "Ingestion failed."
    finally:
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/")
def root_endpoint() -> dict[str, Any]:
    return {"status": "ok", "app": "Pensieve API", "version": "0.1.0"}


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Check connectivity to Qdrant and report collection status."""
    try:
        client = get_client()
        collections_info = client.get_collections()
        existing = {c.name for c in collections_info.collections}

        if QDRANT_COLLECTION not in existing:
            return HealthResponse(
                status="ok",
                qdrant_connected=True,
                collection=QDRANT_COLLECTION,
                points_count=0,
                active_generation_model=GENERATION_LLM_MODEL,
                showcase_mode=SHOWCASE_MODE,
                detail=f"Collection '{QDRANT_COLLECTION}' does not exist in Qdrant.",
            )

        info = client.get_collection(collection_name=QDRANT_COLLECTION)
        points = info.points_count or 0

        return HealthResponse(
            status="ok",
            qdrant_connected=True,
            collection=QDRANT_COLLECTION,
            points_count=points,
            active_generation_model=GENERATION_LLM_MODEL,
            showcase_mode=SHOWCASE_MODE,
        )
    except Exception as exc:
        log.exception("Health check failed connecting to Qdrant at %s", QDRANT_URL)
        return HealthResponse(
            status="unhealthy",
            qdrant_connected=False,
            collection=QDRANT_COLLECTION,
            points_count=0,
            active_generation_model=GENERATION_LLM_MODEL,
            showcase_mode=SHOWCASE_MODE,
            detail=str(exc),
        )


@app.get("/documents", response_model=list[DocumentItemSchema])
def list_documents_endpoint() -> list[DocumentItemSchema]:
    """List all ingested documents aggregated from Qdrant chunk payloads."""
    try:
        client = get_client()
        collections_info = client.get_collections()
        existing = {c.name for c in collections_info.collections}
        if QDRANT_COLLECTION not in existing:
            return []

        offset = None
        docs: dict[str, dict[str, Any]] = {}
        while True:
            records, offset = client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=250,
                with_payload=[
                    "doc_id",
                    "company_name",
                    "fiscal_year",
                    "reporting_period_type",
                    "page_start",
                    "page_end",
                    "section_type",
                    "risk_flag",
                ],
                with_vectors=False,
                offset=offset,
            )
            for r in records:
                p = r.payload or {}
                doc_id = p.get("doc_id")
                if not doc_id:
                    continue
                if doc_id not in docs:
                    docs[doc_id] = {
                        "doc_id": doc_id,
                        "company_name": p.get("company_name") or "Unknown",
                        "fiscal_year": p.get("fiscal_year") or "Unknown",
                        "reporting_period_type": p.get("reporting_period_type") or "Unknown",
                        "num_pages": 0,
                        "narrative_chunks": 0,
                        "table_chunks": 0,
                        "table_chunks_flagged": 0,
                    }
                d = docs[doc_id]
                pe = p.get("page_end") or p.get("page_start") or 0
                if pe > d["num_pages"]:
                    d["num_pages"] = pe

                section = p.get("section_type")
                if section == "narrative":
                    d["narrative_chunks"] += 1
                elif section == "table":
                    d["table_chunks"] += 1
                    if p.get("risk_flag"):
                        d["table_chunks_flagged"] += 1

            if offset is None:
                break

        return list(docs.values())
    except Exception as exc:
        log.exception("Error listing documents from Qdrant: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query document catalog from Qdrant: {exc}",
        ) from exc


@app.post("/documents/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
def upload_document_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> UploadResponse:
    """Accept a multipart PDF upload and begin asynchronous ingestion."""
    if SHOWCASE_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Showcase mode active: document upload and ingestion are disabled in this public deployment.",
        )

    filename = file.filename or "uploaded_document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported for ingestion.",
        )

    job_id = uuid.uuid4().hex
    staging_dir = Path("./staging_input")
    staging_dir.mkdir(parents=True, exist_ok=True)
    temp_path = staging_dir / f"upload_{job_id}.pdf"

    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        log.exception("Failed to save uploaded file: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {exc}",
        ) from exc

    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "doc_id": None,
            "company_name": None,
            "fiscal_year": None,
            "error": None,
            "progress_message": "Queued for processing...",
        }

    background_tasks.add_task(_run_ingestion_job, job_id, temp_path, filename)

    return UploadResponse(job_id=job_id, status="queued")


@app.get("/documents/status/{job_id}", response_model=DocumentStatusResponse)
def get_document_status_endpoint(job_id: str) -> DocumentStatusResponse:
    """Check progress of an asynchronous document ingestion job."""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    return DocumentStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        doc_id=job.get("doc_id"),
        company_name=job.get("company_name"),
        fiscal_year=job.get("fiscal_year"),
        error=job.get("error"),
        progress_message=job.get("progress_message"),
    )


@app.delete("/documents/{doc_id}", response_model=DeleteDocumentResponse)
def delete_document_endpoint(doc_id: str) -> DeleteDocumentResponse:
    """Delete an ingested document by doc_id from Qdrant and disk."""
    if SHOWCASE_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Showcase mode active: document deletion is disabled in this public deployment.",
        )
    try:
        client = get_client()
        collections_info = client.get_collections()
        existing = {c.name for c in collections_info.collections}
        if QDRANT_COLLECTION not in existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{QDRANT_COLLECTION}' not found.",
            )

        count_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="doc_id",
                    match=qmodels.MatchValue(value=doc_id),
                )
            ]
        )
        cnt_res = client.count(collection_name=QDRANT_COLLECTION, count_filter=count_filter, exact=True)
        chunks_count = cnt_res.count

        output_file = DEFAULT_OUTPUT_DIR / f"{doc_id}.json"
        if chunks_count == 0 and not output_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{doc_id}' not found.",
            )

        if chunks_count > 0:
            client.delete(
                collection_name=QDRANT_COLLECTION,
                points_selector=qmodels.FilterSelector(filter=count_filter),
                wait=True,
            )
            log.info("Deleted %d chunks matching doc_id '%s' from Qdrant", chunks_count, doc_id)

        if output_file.exists():
            try:
                output_file.unlink()
                log.info("Removed output file %s", output_file)
            except Exception as exc:
                log.warning("Failed to remove output file %s: %s", output_file, exc)

        # Cancel / clean up any pending/running job with this doc_id
        with _jobs_lock:
            for jid, job in list(_jobs.items()):
                if job.get("doc_id") == doc_id and job.get("status") in ("queued", "processing"):
                    job["status"] = "failed"
                    job["error"] = "Document was deleted during processing."

        return DeleteDocumentResponse(
            deleted=True,
            doc_id=doc_id,
            chunks_removed=chunks_count,
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to delete document '%s': %s", doc_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document '{doc_id}': {exc}",
        ) from exc


@app.post("/query", response_model=QueryResponse)
def query_endpoint(req: QueryRequest, request: Request) -> QueryResponse:
    """Answer a narrative question grounded in ingested documents with citations."""
    check_rate_limit(request)
    query_text = req.query.strip()
    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query cannot be empty or whitespace.",
        )

    # 1. Retrieval
    try:
        chunks = retrieve_narrative_chunks(
            query=query_text,
            top_k=req.top_k or RETRIEVAL_TOP_K_DEFAULT,
            company_name=req.company_name,
            fiscal_year=req.fiscal_year,
        )
    except Exception as exc:
        log.exception("Error during Qdrant retrieval for query: %r", query_text)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Retrieval service failure: {exc}",
        ) from exc

    # 2. Generation & Programmatic Citation Mapping
    try:
        result = generate_answer(query=query_text, chunks=chunks)
    except Exception as exc:
        log.exception("Error during LLM answer generation for query: %r", query_text)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM generation service failure: {exc}",
        ) from exc

    citations = [
        CitationSchema(
            marker=c["marker"],
            chunk_id=c.get("chunk_id", ""),
            doc_id=c["doc_id"],
            source_filename=c["source_filename"],
            company_name=c.get("company_name"),
            fiscal_year=c.get("fiscal_year"),
            page_start=c["page_start"],
            page_end=c["page_end"],
            excerpt=c["excerpt"],
        )
        for c in result.citations
    ]

    return QueryResponse(
        query=result.query,
        answer=result.answer,
        citations=citations,
        no_context_found=result.no_context_found,
    )


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(req: AskRequest, request: Request) -> AskResponse:
    """Route a question through intent classification then the appropriate retrieval + generation pipeline.

    - "narrative" intent: Phase 3 path (retrieve_narrative_chunks + generate_answer).
      verification.status is always "not_applicable" for narrative responses.
    - "numeric" intent: Phase 4 path (retrieve_table_chunks + generate_numeric_answer +
      verify_numbers_against_grid).

    The existing /query endpoint is UNCHANGED. /ask is a new, additive endpoint.
    """
    check_rate_limit(request)
    query_text = req.query.strip()
    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query cannot be empty or whitespace.",
        )

    # -----------------------------------------------------------------------
    # Step 0: Check for Multi-Document Comparison Intent (Phase 5)
    # Only triggered if the caller did not pin a single company_name filter.
    # -----------------------------------------------------------------------
    if not req.company_name:
        is_comparison, entities = detect_comparison_intent(query_text)
        if is_comparison:
            log.info("[/ask] Multi-document comparison detected with %d entities: %s", len(entities), entities)
            try:
                comp_res = execute_comparison(query=query_text, entities=entities)
            except Exception as exc:
                log.exception("[/ask] Multi-document comparison execution failed: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Comparison execution failure: {exc}",
                ) from exc

            citations_out: list[TableCitationSchema | CitationSchema] = []
            for c in comp_res.citations:
                if c.get("table_id") is not None or "risk_flag" in c:
                    citations_out.append(
                        TableCitationSchema(
                            marker=c.get("marker", "[?]"),
                            chunk_id=c.get("chunk_id", ""),
                            doc_id=c.get("doc_id", ""),
                            source_filename=c.get("source_filename", ""),
                            company_name=c.get("company_name"),
                            fiscal_year=c.get("fiscal_year"),
                            page_start=c.get("page_start", 0),
                            page_end=c.get("page_end", 0),
                            table_id=c.get("table_id"),
                            risk_flag=c.get("risk_flag", False),
                            risk_reasons=c.get("risk_reasons", []),
                            excerpt=c.get("excerpt", ""),
                        )
                    )
                else:
                    citations_out.append(
                        CitationSchema(
                            marker=c.get("marker", "[?]"),
                            chunk_id=c.get("chunk_id", ""),
                            doc_id=c.get("doc_id", ""),
                            source_filename=c.get("source_filename", ""),
                            company_name=c.get("company_name"),
                            fiscal_year=c.get("fiscal_year"),
                            page_start=c.get("page_start", 0),
                            page_end=c.get("page_end", 0),
                            excerpt=c.get("excerpt", ""),
                        )
                    )

            verification_out = VerificationSchema(
                status=comp_res.verification_status,
                reason=comp_res.verification_reason,
            )

            per_entity_schema = [
                PerEntityResultSchema(
                    entity=r["entity"],
                    intent=r["intent"],
                    answer=r["answer"],
                    verification_status=r["verification_status"],
                    verification_reason=r["verification_reason"],
                    citations=r["citations"],
                    numbers_extracted=r.get("numbers_extracted", []),
                    risk_flag=r.get("risk_flag", False),
                    risk_reasons=r.get("risk_reasons", []),
                )
                for r in comp_res.per_entity_results
            ]

            return AskResponse(
                query=query_text,
                intent=comp_res.intent,
                answer=comp_res.comparison_answer,
                citations=citations_out,
                verification=verification_out,
                no_context_found=comp_res.no_context_found,
                comparison=True,
                entities_compared=[e.to_dict() for e in entities],
                per_entity_results=per_entity_schema,
                deltas=comp_res.deltas,
            )

    # -----------------------------------------------------------------------
    # Step 1: Intent classification (Single-document Phase 3/4 path)
    # -----------------------------------------------------------------------
    intent = classify_intent(query_text)

    # -----------------------------------------------------------------------
    # Step 2: Retrieve + Generate (intent-routed)
    # -----------------------------------------------------------------------
    if intent == "narrative":
        # Phase 3 path — unchanged
        try:
            chunks = retrieve_narrative_chunks(
                query=query_text,
                top_k=req.top_k or RETRIEVAL_TOP_K_DEFAULT,
                company_name=req.company_name,
                fiscal_year=req.fiscal_year,
            )
        except Exception as exc:
            log.exception("[/ask] Narrative retrieval failed for query: %r", query_text)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Retrieval service failure: {exc}",
            ) from exc

        try:
            result = generate_answer(query=query_text, chunks=chunks)
        except Exception as exc:
            log.exception("[/ask] Narrative generation failed for query: %r", query_text)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM generation failure: {exc}",
            ) from exc

        citations_out: list[TableCitationSchema | CitationSchema] = [
            CitationSchema(
                marker=c["marker"],
                chunk_id=c.get("chunk_id", ""),
                doc_id=c["doc_id"],
                source_filename=c["source_filename"],
                company_name=c.get("company_name"),
                fiscal_year=c.get("fiscal_year"),
                page_start=c["page_start"],
                page_end=c["page_end"],
                excerpt=c["excerpt"],
            )
            for c in result.citations
        ]
        verification_out = VerificationSchema(
            status="not_applicable",
            reason="Narrative intent query: numeric verification is not applicable.",
        )

    else:
        # intent == "numeric" — Phase 4 path
        try:
            table_chunks = retrieve_table_chunks(
                query=query_text,
                top_k=req.top_k or NUMERIC_RETRIEVAL_TOP_K,
                company_name=req.company_name,
                fiscal_year=req.fiscal_year,
            )
        except Exception as exc:
            log.exception("[/ask] Table retrieval failed for query: %r", query_text)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Retrieval service failure: {exc}",
            ) from exc

        # Fit tables within context budget (drop lowest-scored tables whole)
        table_chunks = fit_tables_to_context(table_chunks)

        try:
            result = generate_numeric_answer(query=query_text, chunks=table_chunks)
        except Exception as exc:
            log.exception("[/ask] Numeric generation failed for query: %r", query_text)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM numeric generation failure: {exc}",
            ) from exc

        # Extract numbers and verify against table grids
        numbers = extract_numbers_from_text(result.answer)
        verification_result: VerificationResult = verify_numbers_against_grid(
            numbers_from_answer=numbers,
            cited_chunks=result.citations,
            all_retrieved_chunks=table_chunks,
        )

        # Build table-extended citations (with risk_flag, risk_reasons, table_id)
        chunk_by_id = {c.chunk_id: c for c in table_chunks}
        citations_out = []
        for cit_dict in result.citations:
            cid = cit_dict.get("chunk_id", "")
            rc = chunk_by_id.get(cid)
            citations_out.append(
                TableCitationSchema(
                    marker=cit_dict["marker"],
                    chunk_id=cid,
                    doc_id=cit_dict["doc_id"],
                    source_filename=cit_dict["source_filename"],
                    company_name=cit_dict.get("company_name"),
                    fiscal_year=cit_dict.get("fiscal_year"),
                    page_start=cit_dict["page_start"],
                    page_end=cit_dict["page_end"],
                    table_id=rc.table_id if rc else None,
                    risk_flag=rc.risk_flag if rc else False,
                    risk_reasons=rc.risk_reasons if rc else [],
                    excerpt=cit_dict["excerpt"],
                )
            )
        verification_out = VerificationSchema(
            status=verification_result.status,
            reason=verification_result.reason,
        )

    return AskResponse(
        query=query_text,
        intent=intent,
        answer=result.answer,
        citations=citations_out,
        verification=verification_out,
        no_context_found=result.no_context_found,
    )


def main() -> None:
    """CLI entry point to launch the Pensieve FastAPI server."""
    env_port = int(os.environ.get("PORT", "8000"))
    parser = argparse.ArgumentParser(description="Pensieve API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=env_port, help=f"Port to listen on (default: {env_port})")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    log.info("Starting Pensieve API server on %s:%d", args.host, args.port)
    uvicorn.run("pensieve.api:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
