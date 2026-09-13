"""
pensieve/chunker.py
-------------------
Phase 2 — Narrative + Table Chunking

Converts a Phase 1 document JSON dict into a flat list of Chunk objects ready
for embedding and Qdrant upsert.

Two chunk types:
    "narrative" — text_blocks grouped into ~300-500 token windows with 50-token
                  overlap and heading-attachment semantics.
    "table"     — one chunk per table entry; table is never split.

Public API
----------
    chunk_document(doc, provider=EMBEDDING_PROVIDER) -> list[Chunk]
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from pensieve.config import (
    CHUNK_MAX_TOKENS,
    CHUNK_MIN_CHARS,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TARGET_TOKENS,
    EMBEDDING_PROVIDER,
)
from pensieve.embedder import count_tokens, get_token_limit, truncate_to_tokens
from pensieve.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------


@dataclass
class Chunk:
    """A single embeddable unit, either a narrative window or a whole table."""

    chunk_id: str
    doc_id: str
    source_filename: str
    company_name: str | None
    fiscal_year: str | None
    reporting_period_type: str
    section_type: str          # "narrative" | "table"
    page_start: int
    page_end: int

    # Full content — always stored, even if embed_text differs due to truncation.
    text: str
    # The text that was actually passed to the embedder (may be truncated).
    embed_text: str
    truncated_for_embedding: bool

    # Table-only fields (None for narrative chunks).
    table_id: str | None = None
    risk_flag: bool = False
    risk_reasons: list[str] = field(default_factory=list)
    rows: int | None = None
    cols: int | None = None


# ---------------------------------------------------------------------------
# Chunk ID derivation (deterministic)
# ---------------------------------------------------------------------------


def _narrative_chunk_id(doc_id: str, page_start: int, page_end: int, text_prefix: str) -> str:
    raw = f"{doc_id}:narrative:{page_start}:{page_end}:{text_prefix[:64]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _table_chunk_id(doc_id: str, table_id: str) -> str:
    raw = f"{doc_id}:{table_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Narrative chunking helpers
# ---------------------------------------------------------------------------


def _is_trivial(text: str) -> bool:
    """Return True if text is too short to be meaningful (page numbers, etc.)."""
    return len(text.strip()) < CHUNK_MIN_CHARS


def _last_sentence_boundary(text: str, max_chars: int) -> int:
    """Find the last sentence-ending position at or before max_chars.

    Returns the character index just after the boundary punctuation (so the
    split includes the sentence-ending character in the left part).
    Falls back to max_chars if no boundary found.
    """
    # Look for '. ', '! ', '? ' — sentence endings followed by whitespace.
    window = text[:max_chars]
    # Search backwards for last boundary.
    for m in reversed(list(re.finditer(r"[.!?]\s", window))):
        end = m.end()
        if end > 0:
            return end
    return max_chars


def _recover_overlap_text(text: str, overlap_tokens: int) -> str:
    """Extract the last ~overlap_tokens tokens from text as a string seed."""
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    if len(tokens) <= overlap_tokens:
        return text
    return enc.decode(tokens[-overlap_tokens:])


def _commit_buffer(
    buffer_texts: list[str],
    buffer_pages: list[int],
    doc_id: str,
    source_filename: str,
    company_name: str | None,
    fiscal_year: str | None,
    reporting_period_type: str,
    token_limit: int,
) -> Chunk:
    """Assemble a narrative Chunk from accumulated buffer state."""
    full_text = "\n".join(buffer_texts).strip()
    page_start = buffer_pages[0] if buffer_pages else 0
    page_end = buffer_pages[-1] if buffer_pages else 0

    truncated = False
    if count_tokens(full_text) > token_limit:
        embed_text = truncate_to_tokens(full_text, token_limit)
        truncated = True
    else:
        embed_text = full_text

    chunk_id = _narrative_chunk_id(doc_id, page_start, page_end, full_text)

    return Chunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        source_filename=source_filename,
        company_name=company_name,
        fiscal_year=fiscal_year,
        reporting_period_type=reporting_period_type,
        section_type="narrative",
        page_start=page_start,
        page_end=page_end,
        text=full_text,
        embed_text=embed_text,
        truncated_for_embedding=truncated,
    )


def _chunk_narrative(
    text_blocks: list[dict],
    doc_id: str,
    source_filename: str,
    company_name: str | None,
    fiscal_year: str | None,
    reporting_period_type: str,
    token_limit: int,
) -> list[Chunk]:
    """Produce narrative Chunk objects from a document's text_blocks list."""
    chunks: list[Chunk] = []

    buffer_texts: list[str] = []  # Text segments in current buffer
    buffer_pages: list[int] = []  # Page numbers for each segment
    pending_heading: str | None = None  # Heading deferred until next content block
    buffer_tokens: int = 0

    def flush() -> None:
        nonlocal buffer_texts, buffer_pages, buffer_tokens
        if not buffer_texts:
            return
        chunk = _commit_buffer(
            buffer_texts, buffer_pages, doc_id, source_filename,
            company_name, fiscal_year, reporting_period_type, token_limit
        )
        chunks.append(chunk)
        # Seed next buffer with overlap from this chunk's tail.
        overlap_text = _recover_overlap_text(chunk.text, CHUNK_OVERLAP_TOKENS)
        overlap_page = buffer_pages[-1] if buffer_pages else 0
        buffer_texts.clear()
        buffer_pages.clear()
        buffer_tokens = 0
        if overlap_text.strip():
            buffer_texts.append(overlap_text)
            buffer_pages.append(overlap_page)
            buffer_tokens = count_tokens(overlap_text)

    for block in text_blocks:
        hint = block.get("section_hint", "unknown")
        raw_text = (block.get("text") or "").strip()
        page = block.get("page", 0)

        if not raw_text:
            continue

        # Heading blocks: defer and prepend to the next content block.
        # Must be checked BEFORE the trivial check so short headings (e.g.
        # "Introduction", "Overview") are preserved rather than dropped as noise.
        if hint == "heading":
            # If we already have a pending heading, flush it with current buffer
            # (two headings in a row — edge case; attach first to prior content).
            if pending_heading is not None and buffer_texts:
                flush()
            pending_heading = raw_text
            continue

        # Trivial blocks (page numbers, single tokens) — merge into buffer
        # rather than starting a new chunk, unless buffer is empty.
        if _is_trivial(raw_text):
            if buffer_texts:
                # Append to current buffer silently.
                buffer_texts.append(raw_text)
                buffer_pages.append(page)
                buffer_tokens += count_tokens(raw_text)
            # If buffer is empty, just drop — don't start a chunk with noise.
            continue

        # Content block — attach any pending heading first.
        if pending_heading is not None:
            block_text = f"{pending_heading}\n{raw_text}"
            pending_heading = None
        else:
            block_text = raw_text

        block_tokens = count_tokens(block_text)

        if buffer_tokens + block_tokens > CHUNK_MAX_TOKENS and buffer_texts:
            # Buffer would overflow. Try to split at a sentence boundary.
            combined = "\n".join(buffer_texts) + "\n" + block_text
            # Find where to split (within the committed portion).
            committed_text = "\n".join(buffer_texts)
            committed_chars = len(committed_text)
            split_pos = _last_sentence_boundary(committed_text, committed_chars)
            if split_pos < committed_chars:
                # Split within existing buffer.
                left = committed_text[:split_pos].strip()
                right = committed_text[split_pos:].strip()
                # Temporarily replace buffer with left part, flush.
                buffer_texts = [left]
                buffer_pages = buffer_pages[:1]  # approximate — use first page
                buffer_tokens = count_tokens(left)
                flush()
                # Seed buffer with right fragment + incoming block.
                if right:
                    buffer_texts.append(right)
                    buffer_pages.append(page)
                    buffer_tokens += count_tokens(right)
            else:
                # No good sentence boundary — just flush the buffer as-is.
                flush()

        buffer_texts.append(block_text)
        buffer_pages.append(page)
        buffer_tokens += block_tokens

        # Check if buffer has reached target size and flush if so.
        if buffer_tokens >= CHUNK_TARGET_TOKENS:
            flush()

    # Flush any pending heading at the end of document (attach backward).
    if pending_heading is not None:
        buffer_texts.append(pending_heading)
        buffer_pages.append(0)
        buffer_tokens += count_tokens(pending_heading)

    # Flush remaining buffer.
    flush()

    # Clean up: if the last "chunk" is only overlap text with no real content,
    # discard it (can happen at end of document).
    if chunks and _is_trivial(chunks[-1].text):
        chunks.pop()

    log.debug("Narrative chunking: %d text_blocks → %d chunks", len(text_blocks), len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# Table rendering helpers
# ---------------------------------------------------------------------------


def _render_grid_as_markdown(grid: list[list[str]]) -> str:
    """Render a 2D grid as a GitHub-flavoured markdown table.

    Row 0 is treated as the header row.  An alignment row (|---|---|) is
    inserted after it.  Remaining rows are data rows.

    If the grid has 0 rows, returns an empty string.
    If the grid has exactly 1 row, that row is treated as header and a
    separator is appended (no data rows).
    """
    if not grid:
        return ""

    def _row(cells: list[str]) -> str:
        escaped = [c.replace("|", "\\|").replace("\n", " ") for c in cells]
        return "| " + " | ".join(escaped) + " |"

    lines: list[str] = []
    num_cols = max(len(row) for row in grid) if grid else 0

    # Header row (row 0)
    header_cells = grid[0] + [""] * (num_cols - len(grid[0]))
    lines.append(_row(header_cells))
    lines.append("| " + " | ".join(["---"] * num_cols) + " |")

    # Data rows
    for row in grid[1:]:
        padded = row + [""] * (num_cols - len(row))
        lines.append(_row(padded))

    return "\n".join(lines)


def _build_table_text(
    table: dict,
    company_name: str | None,
    fiscal_year: str | None,
    reporting_period_type: str,
) -> str:
    """Build the full text string for a table chunk."""
    page = table.get("page", 0)
    caption = table.get("caption")

    # Context header — makes the chunk retrievable from natural-language queries
    # even without literal overlap with cell content.
    co = company_name or "Unknown Company"
    fy = fiscal_year or "Unknown FY"
    rt = reporting_period_type or "report"
    header = f"Table from {co} {rt} (FY{fy}), page {page}"
    if caption:
        header += f"\nCaption: {caption}"

    markdown = _render_grid_as_markdown(table.get("grid", []))

    return f"{header}\n\n{markdown}"


def _truncate_table_markdown(
    header: str,
    grid: list[list[str]],
    token_limit: int,
) -> tuple[str, bool]:
    """Return (embed_text, truncated) with the table truncated row-by-row.

    We keep the header and the first N rows of the markdown table such that
    the total stays within token_limit.  The full text is built separately
    by the caller and stored regardless.
    """
    if not grid:
        return header, False

    num_cols = max(len(r) for r in grid) if grid else 0

    def _row_md(cells: list[str]) -> str:
        escaped = [c.replace("|", "\\|").replace("\n", " ") for c in cells]
        return "| " + " | ".join(escaped) + " |"

    sep = "| " + " | ".join(["---"] * num_cols) + " |"

    # Start with header text + table header row + separator.
    header_cells = grid[0] + [""] * (num_cols - len(grid[0]))
    base = f"{header}\n\n{_row_md(header_cells)}\n{sep}"

    if count_tokens(base) >= token_limit:
        # Even the header alone is too big — truncate the header text itself.
        return truncate_to_tokens(base, token_limit), True

    lines = [base]
    for row in grid[1:]:
        padded = row + [""] * (num_cols - len(row))
        row_line = _row_md(padded)
        candidate = "\n".join(lines + [row_line])
        if count_tokens(candidate) > token_limit:
            return "\n".join(lines), True
        lines.append(row_line)

    return "\n".join(lines), False


def _chunk_tables(
    tables: list[dict],
    doc_id: str,
    source_filename: str,
    company_name: str | None,
    fiscal_year: str | None,
    reporting_period_type: str,
    token_limit: int,
) -> list[Chunk]:
    """Produce exactly one Chunk per table entry."""
    chunks: list[Chunk] = []

    co = company_name or "Unknown Company"
    fy = fiscal_year or "Unknown FY"
    rt = reporting_period_type or "report"

    for table in tables:
        table_id = table["table_id"]
        page = table.get("page", 0)
        grid = table.get("grid", [])
        caption = table.get("caption")

        # Context header
        header = f"Table from {co} {rt} (FY{fy}), page {page}"
        if caption:
            header += f"\nCaption: {caption}"

        full_markdown = _render_grid_as_markdown(grid)
        full_text = f"{header}\n\n{full_markdown}" if full_markdown else header

        full_tokens = count_tokens(full_text)
        if full_tokens > token_limit:
            embed_text, truncated = _truncate_table_markdown(header, grid, token_limit)
            log.info(
                "Table %s (page %d): %d tokens exceeds limit %d — truncated for embedding.",
                table_id, page, full_tokens, token_limit,
            )
        else:
            embed_text = full_text
            truncated = False

        chunk_id = _table_chunk_id(doc_id, table_id)
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                source_filename=source_filename,
                company_name=company_name,
                fiscal_year=fiscal_year,
                reporting_period_type=reporting_period_type,
                section_type="table",
                page_start=page,
                page_end=page,
                text=full_text,          # always the full untruncated content
                embed_text=embed_text,   # may be truncated
                truncated_for_embedding=truncated,
                table_id=table_id,
                risk_flag=table.get("risk_flag", False),
                risk_reasons=list(table.get("risk_reasons", [])),
                rows=table.get("rows"),
                cols=table.get("cols"),
            )
        )

    log.debug("Table chunking: %d tables → %d chunks", len(tables), len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chunk_document(
    doc: dict,
    provider: str = EMBEDDING_PROVIDER,
) -> list[Chunk]:
    """Convert a Phase 1 document JSON dict into a list of Chunk objects.

    Parameters
    ----------
    doc:
        The parsed Phase 1 JSON dict (as produced by pensieve.structurer).
    provider:
        Embedding provider name — used to determine the token limit for
        truncation checks.

    Returns
    -------
    List of Chunk objects (narrative chunks first, then table chunks).
    The order within each type follows the original document order.
    """
    doc_id = doc["doc_id"]
    source_filename = doc["source_filename"]
    company_name = doc.get("company_name")
    fiscal_year = doc.get("fiscal_year")
    reporting_period_type = doc.get("reporting_period_type", "other")

    token_limit = get_token_limit(provider)

    narrative_chunks = _chunk_narrative(
        text_blocks=doc.get("text_blocks", []),
        doc_id=doc_id,
        source_filename=source_filename,
        company_name=company_name,
        fiscal_year=fiscal_year,
        reporting_period_type=reporting_period_type,
        token_limit=token_limit,
    )

    table_chunks = _chunk_tables(
        tables=doc.get("tables", []),
        doc_id=doc_id,
        source_filename=source_filename,
        company_name=company_name,
        fiscal_year=fiscal_year,
        reporting_period_type=reporting_period_type,
        token_limit=token_limit,
    )

    total = len(narrative_chunks) + len(table_chunks)
    flagged = sum(1 for c in table_chunks if c.risk_flag)
    truncated = sum(1 for c in narrative_chunks + table_chunks if c.truncated_for_embedding)
    log.info(
        "%s — chunked: %d narrative + %d table chunks (%d flagged, %d truncated)",
        source_filename,
        len(narrative_chunks),
        len(table_chunks),
        flagged,
        truncated,
    )

    return narrative_chunks + table_chunks
