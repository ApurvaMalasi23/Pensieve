"""
pensieve/config.py
------------------
Centralised constants for the Pensieve ingestion pipeline.

Edit values here rather than hunting through pipeline modules.
All environment-variable overrides are also resolved here so the rest
of the codebase never calls os.environ directly.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env (silently no-ops if the file is absent — production envs
# will have vars injected by the platform instead).
load_dotenv()

# ---------------------------------------------------------------------------
# LLM — metadata extraction (Task 2)
# ---------------------------------------------------------------------------

#: NVIDIA NIM OpenAI-compatible endpoint URL.
#: Override via NVIDIA_BASE_URL env var.
METADATA_LLM_BASE_URL: str = os.environ.get(
    "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
)

#: NVIDIA NIM model used for company / fiscal-year extraction.
#: Override via PENSIEVE_LLM_MODEL env var.
METADATA_LLM_MODEL: str = os.environ.get(
    "PENSIEVE_LLM_MODEL", "meta/llama-3.1-70b-instruct"
)

#: Maximum characters from cover pages sent to the LLM.
#: Keeps the prompt small; cover pages rarely need more than this.
COVER_PAGE_MAX_CHARS: int = 4_000

#: How many pages from the start of the document to treat as "cover pages"
#: for metadata extraction.
COVER_PAGE_MAX_PAGES: int = 3

#: Number of retry attempts on transient LLM API errors.
LLM_MAX_RETRIES: int = 3

#: Base wait time (seconds) for exponential back-off between LLM retries.
LLM_RETRY_WAIT_BASE: float = 2.0

# ---------------------------------------------------------------------------
# Risk flagging — tunable thresholds (Task 4)
# ---------------------------------------------------------------------------

#: Minimum number of words for a phrase to be considered "header-like"
#: when checking for repeated header phrases within a row.
REPEATED_PHRASE_MIN_WORDS: int = 2

#: How many times a header-like phrase must appear in a single row
#: before the signal fires.
REPEATED_PHRASE_MIN_OCCURRENCES: int = 2

#: If (num_rows / distinct_leading_column_labels) exceeds this ratio,
#: the row-label duplication signal fires.
ROW_LABEL_DUPLICATION_RATIO: float = 2.5

#: Minimum distinct leading-column labels required before the duplication
#: ratio is even evaluated (avoids false positives on tiny tables).
ROW_LABEL_MIN_DISTINCT: int = 3

#: A cell must contain at least this many number-like tokens to be counted
#: as a "multi-value cell".
MULTI_VALUE_CELL_MIN_NUMBERS: int = 2

#: Fraction of rows in the table that must contain a multi-value cell
#: before the multi-value signal fires.  Kept high to avoid over-flagging
#: dense-text tables.
MULTI_VALUE_ROW_FRACTION: float = 0.30

# ---------------------------------------------------------------------------
# Output / file paths
# ---------------------------------------------------------------------------

#: Default output directory for structured JSON files.
DEFAULT_OUTPUT_DIR: Path = Path(
    os.environ.get("PENSIEVE_OUTPUT_DIR", "./output")
)

#: Default manifest CSV path.
DEFAULT_MANIFEST_PATH: Path = Path(
    os.environ.get("PENSIEVE_MANIFEST_PATH", "./manifest.csv")
)

#: JSON indentation for output files.
JSON_INDENT: int = 2

# ---------------------------------------------------------------------------
# Validation — fiscal year sanity range
# ---------------------------------------------------------------------------

FISCAL_YEAR_MIN: int = 1990
FISCAL_YEAR_MAX: int = 2030

# ---------------------------------------------------------------------------
# Phase 2 — Embedding provider
# ---------------------------------------------------------------------------

#: Which embedding provider to use. Choices: "local" (bge-small-en-v1.5 via
#: sentence-transformers, free, no API key) or "openai" (text-embedding-3-small,
#: requires OPENAI_API_KEY).  Override via PENSIEVE_EMBEDDING_PROVIDER env var.
EMBEDDING_PROVIDER: str = os.environ.get("PENSIEVE_EMBEDDING_PROVIDER", "local")

#: HuggingFace model identifier for the local embedding provider.
EMBEDDING_MODEL_LOCAL: str = os.environ.get(
    "PENSIEVE_EMBEDDING_MODEL_LOCAL", "BAAI/bge-small-en-v1.5"
)

#: OpenAI model name used when EMBEDDING_PROVIDER="openai".
EMBEDDING_MODEL_OPENAI: str = os.environ.get(
    "PENSIEVE_EMBEDDING_MODEL_OPENAI", "text-embedding-3-small"
)

#: Number of texts to encode in a single batch call.
#: Keep ≤64 for local GPU-less inference; OpenAI supports up to 2048.
EMBEDDING_BATCH_SIZE: int = int(os.environ.get("PENSIEVE_EMBEDDING_BATCH_SIZE", "64"))

#: Maximum token length accepted by each provider's model.
#: bge-small-en-v1.5 has a hard limit of 512 sub-word tokens.
#: OpenAI text-embedding-3-small supports up to 8191 tokens.
LOCAL_EMBED_TOKEN_LIMIT: int = 512
OPENAI_EMBED_TOKEN_LIMIT: int = 8191

# ---------------------------------------------------------------------------
# Phase 2 — Qdrant vector store
# ---------------------------------------------------------------------------

#: Qdrant instance URL. Default: local Docker instance.
#: Override via QDRANT_URL env var (e.g. for Qdrant Cloud: https://xyz.cloud.qdrant.io:6333)
QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://localhost:6333")

#: Qdrant API key — required for Qdrant Cloud; leave blank for local instances.
QDRANT_API_KEY: str | None = os.environ.get("QDRANT_API_KEY") or None

#: Name of the Qdrant collection to use/create.
QDRANT_COLLECTION: str = os.environ.get("QDRANT_COLLECTION", "pensieve_chunks")

# ---------------------------------------------------------------------------
# Phase 2 — Chunking thresholds
# ---------------------------------------------------------------------------

#: Target size for narrative chunks in tiktoken cl100k_base tokens.
CHUNK_TARGET_TOKENS: int = int(os.environ.get("PENSIEVE_CHUNK_TARGET_TOKENS", "400"))

#: Hard upper limit — chunks will not exceed this many tokens.
CHUNK_MAX_TOKENS: int = int(os.environ.get("PENSIEVE_CHUNK_MAX_TOKENS", "500"))

#: Overlap between consecutive narrative chunks (tokens re-included from
#: the end of the previous chunk at the start of the next).
CHUNK_OVERLAP_TOKENS: int = int(os.environ.get("PENSIEVE_CHUNK_OVERLAP_TOKENS", "50"))

#: Minimum character length for a text_block to be treated as meaningful
#: content.  Blocks shorter than this (e.g. lone page numbers like "20")
#: are merged into adjacent chunks rather than embedded alone.
CHUNK_MIN_CHARS: int = int(os.environ.get("PENSIEVE_CHUNK_MIN_CHARS", "60"))

# ---------------------------------------------------------------------------
# Phase 3 — Retrieval & LLM Generation
# ---------------------------------------------------------------------------

#: NVIDIA NIM OpenAI-compatible base URL for answer generation.
GENERATION_LLM_BASE_URL: str = os.environ.get(
    "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
)

#: Model used for grounded RAG answer generation.
#: Override via PENSIEVE_GENERATION_MODEL env var.
GENERATION_LLM_MODEL: str = os.environ.get(
    "PENSIEVE_GENERATION_MODEL", "meta/llama-3.2-11b-vision-instruct"
)

#: Default top-k retrieved narrative chunks for RAG.
RETRIEVAL_TOP_K_DEFAULT: int = int(os.environ.get("PENSIEVE_RETRIEVAL_TOP_K", "6"))

#: Cosine similarity threshold for retrieval. If all top-k hits score below
#: this threshold, retrieval treats it as "no relevant context found".
RETRIEVAL_SIMILARITY_THRESHOLD: float = float(
    os.environ.get("PENSIEVE_RETRIEVAL_THRESHOLD", "0.45")
)

#: Maximum tokens generated in RAG answer.
LLM_GENERATION_MAX_TOKENS: int = int(
    os.environ.get("PENSIEVE_GENERATION_MAX_TOKENS", "1024")
)

#: Timeout in seconds for LLM generation requests.
LLM_GENERATION_TIMEOUT: float = float(
    os.environ.get("PENSIEVE_GENERATION_TIMEOUT", "60.0")
)

# ---------------------------------------------------------------------------
# Phase 4 — Query Classification + Numeric / Table-Grounded Generation
# ---------------------------------------------------------------------------

#: Model used for query intent classification (narrative vs numeric).
#: Falls back to the general generation model if not set.
CLASSIFICATION_LLM_MODEL: str = os.environ.get(
    "PENSIEVE_CLASSIFICATION_MODEL", GENERATION_LLM_MODEL
)

#: Model used for table-grounded numeric answer generation.
#: Kept separate so a stronger model can be used for the more demanding
#: table-reading task without affecting Phase 3's narrative path.
#: Falls back to the general generation model if not set.
NUMERIC_LLM_MODEL: str = os.environ.get(
    "PENSIEVE_NUMERIC_MODEL", GENERATION_LLM_MODEL
)

#: Default top-k for numeric/table retrieval.
#: Intentionally small — whole tables are large; retrieving many risks
#: blowing the context window and diluting specific-number grounding.
NUMERIC_RETRIEVAL_TOP_K: int = int(os.environ.get("PENSIEVE_NUMERIC_TOP_K", "3"))

#: Token budget for ALL retrieved tables combined before the numeric LLM call.
#: If combined context exceeds this, the lowest-scored table(s) are dropped
#: entirely (never truncated mid-row — that would corrupt cell values).
NUMERIC_CONTEXT_MAX_TOKENS: int = int(
    os.environ.get("PENSIEVE_NUMERIC_CONTEXT_TOKENS", "6000")
)

# ---------------------------------------------------------------------------
# Showcase Mode & Public Demo Hardening
# ---------------------------------------------------------------------------

#: When True, document upload and document deletion are forbidden (403),
#: turning the public deployment into a read-only fixed catalog showcase.
SHOWCASE_MODE: bool = os.environ.get("SHOWCASE_MODE", "false").lower() in (
    "true",
    "1",
    "yes",
)

#: Maximum number of /ask or /query requests per minute allowed per client IP.
RATE_LIMIT_ASK_PER_MINUTE: int = int(
    os.environ.get("RATE_LIMIT_ASK_PER_MINUTE", "15")
)


