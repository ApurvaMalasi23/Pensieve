"""
pensieve/generator.py
---------------------
Phase 3 — Grounded Generation with Programmatic Citation Mapping

Generates strictly grounded answers from retrieved narrative chunks using
an OpenAI-compatible LLM endpoint (NVIDIA NIM), and maps citation markers [N]
back to the verified chunk metadata.

Public API
----------
    GenerationResult
    generate_answer(query, chunks, model=None, client=None) -> GenerationResult
    format_context_blocks(chunks) -> str
    parse_citations(answer_text, chunks) -> list[dict]
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pensieve.config import (
    GENERATION_LLM_BASE_URL,
    GENERATION_LLM_MODEL,
    LLM_GENERATION_MAX_TOKENS,
    LLM_GENERATION_TIMEOUT,
    LLM_MAX_RETRIES,
    LLM_RETRY_WAIT_BASE,
)
from pensieve.logger import get_logger

if TYPE_CHECKING:
    from pensieve.retriever import RetrievedChunk

log = get_logger(__name__)

# Common phrases indicating refusal or lack of context in generated output
_REFUSAL_PATTERNS = [
    r"cannot\s+answer",
    r"can\s+not\s+answer",
    r"unable\s+to\s+answer",
    r"cannot\s+verify",
    r"can\s+not\s+verify",
    r"unable\s+to\s+verify",
    r"cannot\s+find",
    r"can\s+not\s+find",
    r"unable\s+to\s+find",
    r"does\s+not\s+contain",
    r"do\s+not\s+contain",
    r"does\s+not\s+mention",
    r"do\s+not\s+mention",
    r"no\s+relevant\s+information",
    r"no\s+information\s+provided",
    r"not\s+mentioned\s+in\s+the\s+provided",
    r"not\s+available\s+in\s+the\s+provided",
]


@dataclass
class Citation:
    """Programmatically mapped citation referencing verified chunk metadata."""

    marker: str
    chunk_id: str       # used by Phase 4 verification to look up the cited table
    doc_id: str
    source_filename: str
    company_name: str | None
    fiscal_year: str | None
    page_start: int
    page_end: int
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationResult:
    """Output of the RAG generation step."""

    query: str
    answer: str
    citations: list[dict[str, Any]]
    no_context_found: bool


def format_context_blocks(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks into numbered context blocks for prompt injection.

    Example output:
        [1] Source: Republic Bancorp, FY2024, page 12
        <chunk text>

        [2] Source: Republic Bancorp, FY2024, pages 47-48
        <chunk text>
    """
    blocks: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        company = chunk.company_name or "Unknown Company"
        fy = f"FY{chunk.fiscal_year}" if chunk.fiscal_year else "FY Unknown"
        if chunk.page_start == chunk.page_end:
            page_str = f"page {chunk.page_start}"
        else:
            page_str = f"pages {chunk.page_start}-{chunk.page_end}"

        header = f"[{idx}] Source: {company}, {fy}, {page_str}"
        body = chunk.text.strip()
        blocks.append(f"{header}\n{body}")

    return "\n\n".join(blocks)


def parse_citations(
    answer_text: str,
    chunks: list[RetrievedChunk],
    max_excerpt_chars: int = 300,
) -> list[dict[str, Any]]:
    """Parse citation markers [N] from the generated text and map to chunk metadata.

    CRITICAL RULE:
    Never trust model-generated source descriptions. Citations are created
    strictly from the verified chunks array at index N-1. Any hallucinated
    marker numbers (e.g. [9] when only 6 chunks were provided) are dropped.
    """
    # Find all citation markers of the form [1], [2], etc.
    raw_indices = re.findall(r"\[(\d+)\]", answer_text)

    seen_indices: set[int] = set()
    citations: list[dict[str, Any]] = []

    for num_str in raw_indices:
        idx = int(num_str)
        if idx in seen_indices:
            continue
        seen_indices.add(idx)

        # Validate index is within bounds of provided chunks (1-indexed)
        if 1 <= idx <= len(chunks):
            chunk = chunks[idx - 1]
            excerpt = chunk.text.strip()
            if len(excerpt) > max_excerpt_chars:
                excerpt = excerpt[:max_excerpt_chars].rsplit(" ", 1)[0] + "..."

            cit = Citation(
                marker=f"[{idx}]",
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                source_filename=chunk.source_filename,
                company_name=chunk.company_name,
                fiscal_year=chunk.fiscal_year,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                excerpt=excerpt,
            )
            citations.append(cit.to_dict())
        else:
            log.warning(
                "Dropping hallucinated citation marker [%d] (only %d chunks in context)",
                idx,
                len(chunks),
            )

    return citations


def _is_refusal_answer(answer_text: str) -> bool:
    """Detect if the LLM output explicitly states that it cannot answer."""
    lower = answer_text.lower()
    return any(re.search(pat, lower) for pat in _REFUSAL_PATTERNS)


def _get_generation_client() -> OpenAI:
    """Initialize an OpenAI client pointed at the NVIDIA NIM endpoint."""
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        log.warning("NVIDIA_API_KEY is not set in environment.")
    return OpenAI(
        base_url=GENERATION_LLM_BASE_URL,
        api_key=api_key or "missing-key",
        timeout=LLM_GENERATION_TIMEOUT,
    )


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=LLM_RETRY_WAIT_BASE, min=2, max=10),
    reraise=True,
)
def _call_llm_with_retry(
    client: OpenAI,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> str:
    """Call the LLM chat completion endpoint with retry on transient errors."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        max_tokens=max_tokens,
        temperature=0.1,  # Low temperature for factual precision
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""


def generate_answer(
    query: str,
    chunks: list[RetrievedChunk],
    model: str | None = None,
    client: OpenAI | None = None,
) -> GenerationResult:
    """Generate a grounded answer for a narrative query using retrieved chunks.

    Parameters
    ----------
    query:
        The original user question.
    chunks:
        List of retrieved narrative chunks (from retrieve_narrative_chunks).
    model:
        LLM model identifier. Defaults to GENERATION_LLM_MODEL config constant.
    client:
        Optional OpenAI client instance (for testing/mocking).

    Returns
    -------
    GenerationResult:
        Contains answer text, validated citation objects, and no_context_found flag.
    """
    # 1. Zero-chunk guard: skip LLM call entirely if retrieval returned nothing.
    if not chunks:
        log.info("No chunks provided for query %r — skipping LLM call.", query)
        return GenerationResult(
            query=query,
            answer="No relevant information found in the ingested documents for this query.",
            citations=[],
            no_context_found=True,
        )

    target_model = model or GENERATION_LLM_MODEL
    llm_client = client or _get_generation_client()

    context_str = format_context_blocks(chunks)

    system_prompt = (
        "You are Pensieve, a financial-report assistant used by retail investors.\n"
        "Your task is to answer the user's question accurately and objectively based ONLY on the "
        "numbered context passages provided below.\n\n"
        "Strict rules:\n"
        "1. Grounding: Rely ONLY on facts stated in the provided context passages. Do NOT use external "
        "knowledge or extrapolate beyond what is explicitly written.\n"
        "2. Citations: Every statement or claim you make must cite the supporting context passage(s) "
        "using bracket notation [N], e.g. [1] or [1][2]. Do not combine brackets like [1, 2].\n"
        "3. Refusal: If the provided passages do NOT contain sufficient information to address the "
        "question, you MUST state clearly that the provided documents do not contain the answer. "
        "Do NOT guess or construct an answer.\n"
        "4. Exactness: Financial accuracy and refusal when uncertain are far more important than a "
        "complete-sounding answer."
    )

    user_prompt = (
        f"Numbered Context Passages:\n"
        f"-------------------------\n"
        f"{context_str}\n\n"
        f"-------------------------\n"
        f"Question: {query}\n\n"
        f"Provide a clear, grounded answer with inline citations [N] for each claim:"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    log.info("Calling generation LLM (%s) with %d chunks...", target_model, len(chunks))
    raw_answer = _call_llm_with_retry(
        client=llm_client,
        model=target_model,
        messages=messages,
        max_tokens=LLM_GENERATION_MAX_TOKENS,
    )

    # 2. Programmatically map citations from the model output.
    citations = parse_citations(raw_answer, chunks)

    # 3. Check for refusal / lack of context.
    refusal = _is_refusal_answer(raw_answer)
    no_context = refusal or (len(citations) == 0 and len(chunks) > 0)

    log.info(
        "Generation complete. Answer length: %d chars, Valid citations: %d, Refusal: %s",
        len(raw_answer),
        len(citations),
        no_context,
    )

    return GenerationResult(
        query=query,
        answer=raw_answer,
        citations=citations,
        no_context_found=no_context,
    )
