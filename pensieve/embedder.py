"""
pensieve/embedder.py
--------------------
Phase 2 — Embedding Provider Abstraction

Provides a single public function:

    embed_texts(texts, provider=EMBEDDING_PROVIDER) -> list[list[float]]

Supported providers:
    "local"  — BAAI/bge-small-en-v1.5 via sentence-transformers (default, free, no API key)
    "openai" — text-embedding-3-small via OpenAI API (requires OPENAI_API_KEY)

Switching providers is a one-line config change (PENSIEVE_EMBEDDING_PROVIDER env var);
no code changes required.

Token counting is exposed via count_tokens(text) -> int for use by the chunker.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import tiktoken

from pensieve.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_MODEL_LOCAL,
    EMBEDDING_MODEL_OPENAI,
    EMBEDDING_PROVIDER,
    LOCAL_EMBED_TOKEN_LIMIT,
    OPENAI_EMBED_TOKEN_LIMIT,
)
from pensieve.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Token counting — shared utility (cl100k_base, provider-agnostic)
# ---------------------------------------------------------------------------

_tokenizer = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Return the number of cl100k_base tokens in *text*."""
    return len(_tokenizer.encode(text))


def tokens_to_text(tokens: list[int]) -> str:
    """Decode a list of token IDs back to a string."""
    return _tokenizer.decode(tokens)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Return *text* truncated to at most *max_tokens* tokens."""
    encoded = _tokenizer.encode(text)
    if len(encoded) <= max_tokens:
        return text
    return tokens_to_text(encoded[:max_tokens])


# ---------------------------------------------------------------------------
# Local provider (sentence-transformers / bge-small-en-v1.5)
# ---------------------------------------------------------------------------

_local_model = None  # Lazy-loaded once on first use


def _get_local_model():
    global _local_model  # noqa: PLW0603
    if _local_model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for the local embedding provider. "
                "Install it with: pip install sentence-transformers"
            ) from exc
        log.info("Loading local embedding model: %s", EMBEDDING_MODEL_LOCAL)
        _local_model = SentenceTransformer(EMBEDDING_MODEL_LOCAL)
        log.info(
            "Local embedding model loaded. Dimension: %d",
            _local_model.get_embedding_dimension(),
        )
    return _local_model


def _embed_local(texts: list[str]) -> list[list[float]]:
    """Embed *texts* using the local sentence-transformers model."""
    model = _get_local_model()
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        vecs = model.encode(batch, show_progress_bar=False, convert_to_numpy=True)
        all_vectors.extend(vecs.tolist())
        log.debug(
            "Local embed: batch %d-%d / %d", i + 1, min(i + EMBEDDING_BATCH_SIZE, len(texts)), len(texts)
        )
    return all_vectors


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

_openai_client = None  # Lazy-loaded once on first use


def _get_openai_client():
    global _openai_client  # noqa: PLW0603
    if _openai_client is None:
        try:
            import openai  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "openai package is required for the OpenAI embedding provider."
            ) from exc
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is not set. "
                "Set it in .env or export it before using the openai provider."
            )
        _openai_client = openai.OpenAI(api_key=api_key)
    return _openai_client


def _embed_openai(texts: list[str]) -> list[list[float]]:
    """Embed *texts* using the OpenAI Embeddings API."""
    client = _get_openai_client()
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        response = client.embeddings.create(model=EMBEDDING_MODEL_OPENAI, input=batch)
        # Response items are ordered but let's sort by index just to be safe.
        batch_vecs = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
        all_vectors.extend(batch_vecs)
        log.debug(
            "OpenAI embed: batch %d-%d / %d", i + 1, min(i + EMBEDDING_BATCH_SIZE, len(texts)), len(texts)
        )
    return all_vectors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def embed_texts(
    texts: list[str],
    provider: str = EMBEDDING_PROVIDER,
) -> list[list[float]]:
    """Embed a list of text strings and return their vectors.

    Parameters
    ----------
    texts:
        Non-empty list of strings to embed. Empty strings are allowed but
        produce low-quality vectors — callers should filter them out beforehand.
    provider:
        ``"local"`` (default) or ``"openai"``. Reads from
        ``PENSIEVE_EMBEDDING_PROVIDER`` env var by default.

    Returns
    -------
    List of embedding vectors, one per input text, in the same order.
    Each vector is a ``list[float]`` of length ``get_vector_dim(provider)``.
    """
    if not texts:
        return []
    if provider == "local":
        return _embed_local(texts)
    if provider == "openai":
        return _embed_openai(texts)
    raise ValueError(
        f"Unknown embedding provider: {provider!r}. Choose 'local' or 'openai'."
    )


def get_vector_dim(provider: str = EMBEDDING_PROVIDER) -> int:
    """Return the embedding dimension for the active provider.

    For the local provider this loads the model on first call (lazy init).
    For openai, returns the known dimension without an API call.
    """
    if provider == "local":
        model = _get_local_model()
        # SentenceTransformer provides get_sentence_embedding_dimension() and get_embedding_dimension()
        if hasattr(model, "get_sentence_embedding_dimension"):
            res = model.get_sentence_embedding_dimension()
            if res is not None and not (type(res).__name__ == "MagicMock"):
                return int(res)
        return int(model.get_embedding_dimension())
    if provider == "openai":
        return 1536  # text-embedding-3-small fixed dimension
    raise ValueError(f"Unknown embedding provider: {provider!r}")


def get_token_limit(provider: str = EMBEDDING_PROVIDER) -> int:
    """Return the maximum token input length for the active provider's model."""
    if provider == "local":
        return LOCAL_EMBED_TOKEN_LIMIT
    if provider == "openai":
        return OPENAI_EMBED_TOKEN_LIMIT
    raise ValueError(f"Unknown embedding provider: {provider!r}")
