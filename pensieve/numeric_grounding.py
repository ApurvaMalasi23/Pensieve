"""
pensieve/numeric_grounding.py
------------------------------
Phase 4 — Numeric Grounding: Context Management, Generation, Extraction & Verification

This is Pensieve's core differentiator: numeric answers are verified against
Docling's *actual extracted table cells*, not just vector-similarity text chunks.

Modules in this file:
  fit_tables_to_context     — drop lowest-scoring tables that exceed token budget
  generate_numeric_answer   — LLM generation from whole tables, strict grounding prompt
  extract_numbers_from_text — regex extraction of numeric figures from model output
  normalize_number          — canonical string form of a financial figure
  verify_numbers_against_grid — check extracted figures against cited table grids

Design decisions (see implementation_plan.md for full rationale):
  A. No retry on unverified — return the unverified answer honestly.
  B. Exact normalisation only — no rounding tolerance.
  C. Verify against cited chunks first; fall back to all retrieved chunks.
  D. Drop whole tables (not truncate) when context budget is exceeded.

Public API
----------
    VerificationResult
    fit_tables_to_context(chunks, max_tokens) -> list[RetrievedChunk]
    generate_numeric_answer(query, chunks, model=None, client=None) -> GenerationResult
    extract_numbers_from_text(text) -> list[str]
    normalize_number(s) -> str
    verify_numbers_against_grid(numbers, cited_chunks, all_retrieved) -> VerificationResult
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pensieve.config import (
    GENERATION_LLM_BASE_URL,
    LLM_GENERATION_MAX_TOKENS,
    LLM_GENERATION_TIMEOUT,
    LLM_MAX_RETRIES,
    LLM_RETRY_WAIT_BASE,
    NUMERIC_CONTEXT_MAX_TOKENS,
    NUMERIC_LLM_MODEL,
)
from pensieve.embedder import count_tokens
from pensieve.generator import GenerationResult, parse_citations
from pensieve.logger import get_logger

if TYPE_CHECKING:
    from pensieve.retriever import RetrievedChunk

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class VerificationResult:
    """Outcome of programmatic numeric verification against extracted table cells.

    Attributes
    ----------
    status:
        - "verified"               : figure(s) found in table cells; table passed QC.
        - "verified_low_confidence": figure(s) found but table has risk_flag=True.
        - "unverified"             : numeric figures in answer not found in any table cell.
        - "not_applicable"         : answer contains no numeric figures to verify.
    reason:
        Human-readable explanation suitable for display to an end user.
    matched_figures:
        Figures from the answer that were confirmed in at least one table cell.
    unmatched_figures:
        Figures from the answer that could NOT be confirmed in any table cell.
    """

    status: Literal["verified", "verified_low_confidence", "unverified", "not_applicable"]
    reason: str
    matched_figures: list[str] = field(default_factory=list)
    unmatched_figures: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 4a. Context window management
# ---------------------------------------------------------------------------


def fit_tables_to_context(
    chunks: list[RetrievedChunk],
    max_tokens: int = NUMERIC_CONTEXT_MAX_TOKENS,
) -> list[RetrievedChunk]:
    """Return the largest prefix of chunks that fits within max_tokens.

    Chunks are assumed to be sorted by relevance score (highest first) as
    returned by retrieve_table_chunks().  We never truncate a table mid-content
    because that would corrupt cell values.  Instead we drop whole low-scoring
    tables until the total fits.

    Parameters
    ----------
    chunks:
        Table chunks sorted by score descending.
    max_tokens:
        Maximum total token count across all chunks (default: NUMERIC_CONTEXT_MAX_TOKENS).

    Returns
    -------
    The subset of chunks (in original order) whose combined token count ≤ max_tokens.
    """
    if not chunks:
        return []

    # Compute token counts once — avoid calling count_tokens inside the loop.
    token_counts = [count_tokens(c.text) for c in chunks]
    total = sum(token_counts)

    if total <= max_tokens:
        return list(chunks)

    # Drop from the tail (lowest score) until we fit.
    result = list(chunks)
    result_tokens = list(token_counts)
    while result and sum(result_tokens) > max_tokens:
        dropped = result.pop()
        result_tokens.pop()
        log.info(
            "fit_tables_to_context: dropped table %s (page %d, %d tokens) — "
            "combined context exceeded budget of %d tokens.",
            dropped.table_id,
            dropped.page_start,
            count_tokens(dropped.text),
            max_tokens,
        )

    log.info(
        "fit_tables_to_context: %d/%d table(s) fit within %d tokens (%d total).",
        len(result),
        len(chunks),
        max_tokens,
        sum(result_tokens),
    )
    return result


# ---------------------------------------------------------------------------
# 4b. Numeric answer generation
# ---------------------------------------------------------------------------

_NUMERIC_SYSTEM_PROMPT = """\
You are a financial analyst assistant for Pensieve, a financial-report intelligence system.

You will be given numbered blocks of extracted financial table data from a specific company's report.
Answer the user's question using ONLY the information in these tables.

Rules:
1. State each specific figure EXACTLY as it appears in the table — do not round, abbreviate,
   convert units, or paraphrase numeric values. If the table shows "4,572,044", say "4,572,044".
2. Cite your source by table block number, e.g. [1] or [2].
3. If the tables do not contain enough information to answer the question, say so explicitly —
   do not guess or use external knowledge.
4. Include only one citation per fact — do not repeat citation markers.
"""


def _format_table_context_blocks(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved table chunks as numbered context blocks for the LLM prompt."""
    blocks: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        meta = f"[Table {i}] Page {chunk.page_start}"
        if chunk.company_name:
            meta += f" | {chunk.company_name}"
        if chunk.fiscal_year:
            meta += f" FY{chunk.fiscal_year}"
        if chunk.table_id:
            meta += f" | table_id={chunk.table_id}"
        # Use the full untruncated text — Phase 2 stored it in payload.text
        blocks.append(f"{meta}\n{chunk.text}")
    return "\n\n---\n\n".join(blocks)


def _get_numeric_client() -> OpenAI:
    """Return an OpenAI client for the numeric generation path."""
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        log.warning("NVIDIA_API_KEY is not set — numeric generation will fail.")
    return OpenAI(
        base_url=GENERATION_LLM_BASE_URL,
        api_key=api_key or "missing-key",
        timeout=LLM_GENERATION_TIMEOUT,
    )


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=LLM_RETRY_WAIT_BASE, min=2, max=30),
    reraise=True,
)
def _call_numeric_llm(
    client: OpenAI,
    model: str,
    messages: list[dict],
) -> str:
    """Call the LLM with retry/backoff and return the content string."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=LLM_GENERATION_MAX_TOKENS,
        temperature=0.0,  # Deterministic for numeric grounding
    )
    content = response.choices[0].message.content
    return content or ""


def generate_numeric_answer(
    query: str,
    chunks: list[RetrievedChunk],
    model: str | None = None,
    client: OpenAI | None = None,
) -> GenerationResult:
    """Generate a numeric answer grounded in retrieved table chunks.

    Uses the same GenerationResult type as Phase 3's generate_answer() for
    API consistency, so the /ask endpoint can handle both paths uniformly.

    Parameters
    ----------
    query:
        The user's numeric question.
    chunks:
        Retrieved table chunks (already fitted to context budget).
    model:
        LLM model override. Defaults to NUMERIC_LLM_MODEL.
    client:
        OpenAI client override (for testing).

    Returns
    -------
    GenerationResult with answer, citations (programmatic), and no_context_found flag.
    """
    target_model = model or NUMERIC_LLM_MODEL
    llm_client = client or _get_numeric_client()

    if not chunks:
        log.info("generate_numeric_answer: no table chunks — returning no-context response.")
        return GenerationResult(
            query=query,
            answer=(
                "I cannot find any relevant table data in the ingested documents to answer "
                "this question. Please check the source document directly."
            ),
            citations=[],
            no_context_found=True,
        )

    context = _format_table_context_blocks(chunks)
    messages = [
        {"role": "system", "content": _NUMERIC_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Tables:\n\n{context}\n\nQuestion: {query}",
        },
    ]

    try:
        answer_text = _call_numeric_llm(llm_client, target_model, messages)
    except Exception:
        log.exception("generate_numeric_answer: LLM call failed for query %r", query)
        raise

    # Programmatic citation mapping — same logic as Phase 3's parse_citations()
    citations = parse_citations(answer_text, chunks)

    no_context = not bool(answer_text.strip()) or (
        not citations and not bool(re.search(r"\b\d", answer_text))
    )

    log.info(
        "generate_numeric_answer: generated answer (%d chars, %d citations) for query %r",
        len(answer_text),
        len(citations),
        query,
    )
    return GenerationResult(
        query=query,
        answer=answer_text,
        citations=citations,
        no_context_found=no_context,
    )


# ---------------------------------------------------------------------------
# 4c. Numeric extraction from model output
# ---------------------------------------------------------------------------

# Captures the main numeric patterns that appear in financial statements:
#   (1)  $4,572,044  or  $ 4,572,044  (dollar amounts, with optional space)
#   (2)  (4,572,044)  or  ($4,572,044)  (negative/loss convention)
#   (3)  5.25%   or  5.25 %  (percentages)
#   (4)  312,154  (plain numbers with commas)
#   (5)  0.85  (plain decimals, e.g. EPS)
#   (6)  -1,482  (signed numbers)
# We do NOT extract bare integers < 4 digits (page numbers, years, counts).
_NUMBER_PATTERN = re.compile(
    r"""
    (?:
        \(                          # open paren (negative convention)
        \$?\s*
        \d{1,3}(?:,\d{3})+         # comma-grouped number
        (?:\.\d+)?                  # optional decimal
        \)                          # close paren
      |
        \$\s*\d{1,3}(?:,\d{3})+    # dollar + comma-grouped
        (?:\.\d+)?
      |
        -?\d{1,3}(?:,\d{3})+       # signed comma-grouped
        (?:\.\d+)?
        (?:\s*%)?                   # optional percent
      |
        -?\d+\.\d+                  # plain decimal (e.g. EPS 1.23)
        (?:\s*%)?
    )
    """,
    re.VERBOSE,
)


def extract_numbers_from_text(text: str) -> list[str]:
    """Extract candidate numeric figures from model-generated text.

    Returns a list of raw matched strings (not yet normalized).
    Small integers (< 4 digits, no commas) are excluded to avoid matching
    page numbers, years, and item counts.

    Parameters
    ----------
    text:
        The answer text generated by the LLM.

    Returns
    -------
    List of raw numeric string matches from the text.
    """
    if not text:
        return []
    matches = _NUMBER_PATTERN.findall(text)
    # Deduplicate while preserving order (first occurrence wins)
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        m = m.strip()
        if m and m not in seen:
            seen.add(m)
            result.append(m)
    return result


# ---------------------------------------------------------------------------
# 4d. Numeric normalization
# ---------------------------------------------------------------------------


def normalize_number(s: str) -> str:
    """Return a canonical form of a financial numeric string for comparison.

    Transforms common financial number representations into a plain decimal
    string suitable for equality comparison against table cell values.

    Transformations applied (in order):
      1. Strip surrounding whitespace.
      2. Remove dollar signs, commas, percent signs.
      3. Handle parenthesized negatives: "(1,482)" → "-1482".
      4. Remove trailing/leading whitespace again.

    Note: We compare as *strings* (not floats) to avoid floating-point
    precision issues with large financial figures.

    Parameters
    ----------
    s:
        Raw numeric string, e.g. "$4,572,044 $", "(1,482)", "5.25%".

    Returns
    -------
    Normalized string, e.g. "4572044", "-1482", "5.25".
    """
    s = s.strip()

    # Detect parenthesized negative before stripping parens
    is_negative = s.startswith("(") and s.endswith(")")
    # Strip: parens, $, ,, %, whitespace
    s = re.sub(r"[\s$,%()\u2013\u2014]", "", s)
    s = s.strip()
    if is_negative and s and not s.startswith("-"):
        s = "-" + s

    return s


# ---------------------------------------------------------------------------
# 4e. Grid-based verification
# ---------------------------------------------------------------------------


def _parse_markdown_table_cells(markdown_text: str) -> list[str]:
    """Extract all non-empty cell values from a markdown table in chunk.text.

    Returns a flat list of normalized cell strings for fast set membership tests.
    """
    cells: list[str] = []
    for line in markdown_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Skip the separator row (|---|---|)
        if re.match(r"^\|[\s\-\|]+\|$", line):
            continue
        # Split on pipe, skip first/last empty segments
        raw_cells = line.split("|")[1:-1]
        for cell in raw_cells:
            cell = cell.strip()
            if cell:
                cells.append(cell)
    return cells


def _summarize_risk_reasons(risk_reasons: list[str], max_len: int = 120) -> str:
    """Return a short, human-readable summary of risk reasons."""
    if not risk_reasons:
        return "extraction quality warning"
    # Take only the first reason, clip it at max_len chars
    first = risk_reasons[0]
    if len(first) > max_len:
        first = first[:max_len] + "…"
    return first


def verify_numbers_against_grid(
    numbers_from_answer: list[str],
    cited_chunks: list[dict],
    all_retrieved_chunks: list[RetrievedChunk],
) -> VerificationResult:
    """Verify numeric figures from the model's answer against extracted table cells.

    Design decisions (from implementation_plan.md):
      - Primary check: each figure vs. cells in its SPECIFICALLY CITED chunk.
      - Fallback: if not found in cited chunk, search ALL retrieved table chunks.
        (Handles the case where the LLM answered correctly but forgot the marker.)
      - No retry on mismatch — return unverified honestly.
      - Exact normalised comparison only (no rounding tolerance).

    Parameters
    ----------
    numbers_from_answer:
        Raw numeric strings extracted from the model's answer.
    cited_chunks:
        Citation dicts from parse_citations() — each has 'chunk_id' and 'text'
        fields (the specific tables the answer cited by marker).
    all_retrieved_chunks:
        All table chunks that were retrieved (for fallback search).

    Returns
    -------
    VerificationResult with status, reason, and matched/unmatched figure lists.
    """
    # ---- 0. Trivial case: no numbers to verify ----------------------------
    if not numbers_from_answer:
        return VerificationResult(
            status="not_applicable",
            reason=(
                "This answer is descriptive rather than numeric — "
                "no specific figures to verify."
            ),
        )

    # ---- 1. Build normalised cell sets for each cited chunk ---------------
    # Map: chunk_id → (set of normalised cell values, RetrievedChunk object)
    cited_ids = {c.get("chunk_id", "") for c in cited_chunks}
    cited_chunk_objects = [rc for rc in all_retrieved_chunks if rc.chunk_id in cited_ids]

    # Build cell lookup per cited chunk
    def _cell_set(chunk: RetrievedChunk) -> frozenset[str]:
        cells = _parse_markdown_table_cells(chunk.text)
        return frozenset(normalize_number(c) for c in cells if c.strip())

    cited_cell_sets = {rc.chunk_id: _cell_set(rc) for rc in cited_chunk_objects}
    all_cell_sets = {rc.chunk_id: _cell_set(rc) for rc in all_retrieved_chunks}

    # ---- 2. Attempt to match each extracted number ------------------------
    matched: list[str] = []
    unmatched: list[str] = []
    matched_chunk_ids: list[str] = []  # which chunks provided the match
    matched_via_fallback: list[str] = []  # figures matched only via fallback

    for raw_num in numbers_from_answer:
        norm = normalize_number(raw_num)
        if not norm:
            continue

        # 2a. Check specifically cited chunks first
        found_in_cited = False
        for chunk_id, cell_set in cited_cell_sets.items():
            if norm in cell_set:
                found_in_cited = True
                matched.append(raw_num)
                matched_chunk_ids.append(chunk_id)
                break

        if found_in_cited:
            continue

        # 2b. Fallback: check ALL retrieved table chunks
        found_in_any = False
        for chunk_id, cell_set in all_cell_sets.items():
            if norm in cell_set:
                found_in_any = True
                matched.append(raw_num)
                matched_via_fallback.append(raw_num)
                matched_chunk_ids.append(chunk_id)
                break

        if not found_in_any:
            unmatched.append(raw_num)

    # ---- 3. Determine verification status --------------------------------
    if not matched:
        # No figures from the answer appear anywhere in the retrieved tables
        return VerificationResult(
            status="unverified",
            reason=(
                f"The figure(s) {', '.join(numbers_from_answer)} stated in this answer "
                "could not be confirmed in the table data extracted from this document. "
                "This may indicate a generation error. "
                "Please verify against the source document."
            ),
            matched_figures=[],
            unmatched_figures=list(numbers_from_answer),
        )

    # At least one figure matched — find which chunks they came from
    matched_chunk_set = set(matched_chunk_ids)
    matched_rc = [rc for rc in all_retrieved_chunks if rc.chunk_id in matched_chunk_set]

    # Aggregate risk flag across all matched source chunks
    any_risk_flagged = any(rc.risk_flag for rc in matched_rc)

    # Pick one representative chunk for the reason string
    representative = matched_rc[0] if matched_rc else None

    # Build figure summary for reason string
    matched_display = ", ".join(matched[:3])
    if len(matched) > 3:
        matched_display += f" (and {len(matched) - 3} more)"

    fallback_note = ""
    if matched_via_fallback:
        fallback_note = (
            " Note: the citation marker was approximate — the figure was found in "
            "a retrieved table but not the specifically cited one."
        )

    if any_risk_flagged:
        # At least one matched table has a quality warning
        representative_risk = representative.risk_reasons if representative else []
        risk_summary = _summarize_risk_reasons(representative_risk)
        page = representative.page_start if representative else "?"
        company = representative.company_name or "the company"
        fy = representative.fiscal_year or "?"

        return VerificationResult(
            status="verified_low_confidence",
            reason=(
                f"The figure(s) {matched_display} were found in the extracted table "
                f"on page {page} from {company}'s FY{fy} report, but this table has "
                f"an extraction quality warning: '{risk_summary}'. "
                "The value exists in Pensieve's extracted data, but may not accurately "
                "reflect the source document. Please verify against the original PDF."
                + fallback_note
            ),
            matched_figures=matched,
            unmatched_figures=unmatched,
        )
    else:
        # All matched tables passed QC
        page = representative.page_start if representative else "?"
        company = representative.company_name or "the company"
        fy = representative.fiscal_year or "?"

        return VerificationResult(
            status="verified",
            reason=(
                f"The figure(s) {matched_display} were found in the table "
                f"on page {page} from {company}'s FY{fy} report. "
                "This table passed Pensieve's extraction quality check."
                + fallback_note
            ),
            matched_figures=matched,
            unmatched_figures=unmatched,
        )
