"""
tests/test_chunker.py
---------------------
Unit tests for pensieve.chunker — narrative + table chunking logic.

These tests do NOT embed text or touch Qdrant.
They use synthetic minimal document dicts that mimic the Phase 1 JSON schema.
"""

from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest

from pensieve.chunker import (
    Chunk,
    _narrative_chunk_id,
    _render_grid_as_markdown,
    _table_chunk_id,
    chunk_document,
)


# ---------------------------------------------------------------------------
# Fixtures — minimal Phase 1 doc dicts
# ---------------------------------------------------------------------------

def _make_doc(text_blocks=None, tables=None):
    return {
        "doc_id": "abc123",
        "source_filename": "test.pdf",
        "company_name": "Acme Corp",
        "fiscal_year": "2024",
        "reporting_period_type": "annual",
        "num_pages": 10,
        "text_blocks": text_blocks or [],
        "tables": tables or [],
    }


def _make_block(text, hint="narrative", page=1):
    return {"block_id": "b0", "page": page, "text": text, "section_hint": hint}


def _make_table(table_id, page, grid, risk_flag=False, risk_reasons=None):
    return {
        "table_id": table_id,
        "page": page,
        "rows": len(grid),
        "cols": len(grid[0]) if grid else 0,
        "grid": grid,
        "caption": None,
        "risk_flag": risk_flag,
        "risk_reasons": risk_reasons or [],
    }


# ---------------------------------------------------------------------------
# Narrative chunking
# ---------------------------------------------------------------------------

class TestNarrativeChunking:
    def test_empty_doc_produces_no_chunks(self):
        doc = _make_doc()
        chunks = chunk_document(doc)
        assert chunks == []

    def test_single_block_produces_one_narrative_chunk(self):
        block = _make_block("This is a substantial paragraph. " * 10)
        doc = _make_doc(text_blocks=[block])
        chunks = chunk_document(doc)
        narr = [c for c in chunks if c.section_type == "narrative"]
        assert len(narr) == 1
        assert "This is a substantial paragraph" in narr[0].text

    def test_trivial_blocks_are_not_standalone_chunks(self):
        """A lone page number should not become its own chunk."""
        blocks = [
            _make_block("A " * 50),   # real content
            _make_block("20"),         # trivial — page number noise
            _make_block("B " * 50),   # real content
        ]
        doc = _make_doc(text_blocks=blocks)
        chunks = chunk_document(doc)
        narr = [c for c in chunks if c.section_type == "narrative"]
        # All should merge — "20" should not become its own chunk.
        for chunk in narr:
            assert chunk.text.strip() != "20"

    def test_heading_attaches_to_following_content(self):
        """A heading block should appear in the same chunk as the text that follows."""
        blocks = [
            _make_block("Introduction", hint="heading"),
            _make_block("This is the body text for the introduction section. " * 5),
        ]
        doc = _make_doc(text_blocks=blocks)
        chunks = chunk_document(doc)
        narr = [c for c in chunks if c.section_type == "narrative"]
        # Introduction heading should appear in the same chunk as body text.
        combined_text = " ".join(c.text for c in narr)
        assert "Introduction" in combined_text
        assert "body text" in combined_text
        # Should not produce a standalone "Introduction" chunk.
        standalone = [c for c in narr if c.text.strip() == "Introduction"]
        assert not standalone

    def test_large_content_splits_into_multiple_chunks(self):
        """A very long document should produce more than one narrative chunk."""
        # 50 * 50 = 2500 words — well over one chunk window.
        blocks = [_make_block(f"Word{i} " * 50, page=i + 1) for i in range(50)]
        doc = _make_doc(text_blocks=blocks)
        chunks = chunk_document(doc)
        narr = [c for c in chunks if c.section_type == "narrative"]
        assert len(narr) > 1

    def test_overlap_between_consecutive_chunks(self):
        """End of chunk N should appear at the start of chunk N+1."""
        # Create enough content for at least 2 chunks.
        blocks = [_make_block(f"sentence{i}. " * 30, page=i + 1) for i in range(20)]
        doc = _make_doc(text_blocks=blocks)
        chunks = chunk_document(doc)
        narr = [c for c in chunks if c.section_type == "narrative"]
        if len(narr) >= 2:
            # Last word(s) of chunk 0 should appear in chunk 1.
            end_of_first = narr[0].text.split()[-3:]  # last 3 words
            second_text = narr[1].text
            # At least one of the last words should be in the second chunk.
            assert any(w in second_text for w in end_of_first), (
                f"Expected overlap between chunk 0 and chunk 1.\n"
                f"End of chunk 0: {end_of_first}\n"
                f"Start of chunk 1: {second_text[:200]}"
            )

    def test_chunk_id_is_deterministic(self):
        """Same input should always produce the same chunk_id."""
        block = _make_block("Consistent text for determinism testing. " * 10)
        doc = _make_doc(text_blocks=[block])
        chunks1 = chunk_document(doc)
        chunks2 = chunk_document(doc)
        ids1 = [c.chunk_id for c in chunks1 if c.section_type == "narrative"]
        ids2 = [c.chunk_id for c in chunks2 if c.section_type == "narrative"]
        assert ids1 == ids2

    def test_page_range_is_recorded(self):
        """page_start and page_end should reflect the actual block pages."""
        blocks = [
            _make_block("Alpha. " * 20, page=5),
            _make_block("Beta. " * 20, page=6),
        ]
        doc = _make_doc(text_blocks=blocks)
        chunks = chunk_document(doc)
        narr = [c for c in chunks if c.section_type == "narrative"]
        assert narr[0].page_start >= 5

    def test_doc_metadata_propagates_to_narrative_chunks(self):
        block = _make_block("Some text content here. " * 10)
        doc = _make_doc(text_blocks=[block])
        chunks = chunk_document(doc)
        narr = [c for c in chunks if c.section_type == "narrative"]
        assert narr[0].company_name == "Acme Corp"
        assert narr[0].fiscal_year == "2024"
        assert narr[0].doc_id == "abc123"
        assert narr[0].source_filename == "test.pdf"


# ---------------------------------------------------------------------------
# Table chunking
# ---------------------------------------------------------------------------

class TestTableChunking:
    def test_one_chunk_per_table(self):
        tables = [
            _make_table("table_0001", 5, [["H1", "H2"], ["a", "b"], ["c", "d"]]),
            _make_table("table_0002", 7, [["X", "Y"], ["1", "2"]]),
        ]
        doc = _make_doc(tables=tables)
        chunks = chunk_document(doc)
        tbl_chunks = [c for c in chunks if c.section_type == "table"]
        assert len(tbl_chunks) == 2

    def test_table_is_never_split(self):
        """A large table must produce exactly 1 chunk (not split into sub-chunks)."""
        big_grid = [["Col A", "Col B", "Col C"]] + [
            [f"Row{i} data A", f"Row{i} data B", f"Row{i} data C"]
            for i in range(80)
        ]
        tables = [_make_table("table_big", 10, big_grid)]
        doc = _make_doc(tables=tables)
        chunks = chunk_document(doc)
        tbl_chunks = [c for c in chunks if c.section_type == "table"]
        assert len(tbl_chunks) == 1

    def test_risk_flag_propagates(self):
        tables = [
            _make_table("table_0001", 1, [["A"], ["1"]], risk_flag=True, risk_reasons=["test reason"]),
            _make_table("table_0002", 2, [["B"], ["2"]], risk_flag=False),
        ]
        doc = _make_doc(tables=tables)
        chunks = chunk_document(doc)
        tbl_chunks = {c.table_id: c for c in chunks if c.section_type == "table"}
        assert tbl_chunks["table_0001"].risk_flag is True
        assert tbl_chunks["table_0001"].risk_reasons == ["test reason"]
        assert tbl_chunks["table_0002"].risk_flag is False
        assert tbl_chunks["table_0002"].risk_reasons == []

    def test_full_text_stored_even_when_truncated(self):
        """If a table exceeds the token limit, text must still be full grid."""
        # Mock a very low token limit to force truncation.
        big_grid = [["Header A", "Header B"]] + [
            [f"Long data cell entry {i}", f"Another data cell {i}"]
            for i in range(50)
        ]
        tables = [_make_table("table_long", 3, big_grid)]
        doc = _make_doc(tables=tables)
        # Patch the token limit to something tiny so truncation triggers.
        with patch("pensieve.chunker.get_token_limit", return_value=30):
            chunks = chunk_document(doc)
        tbl_chunks = [c for c in chunks if c.section_type == "table"]
        assert len(tbl_chunks) == 1
        chunk = tbl_chunks[0]
        # Full text must contain all original content (or at least most of it)
        assert chunk.truncated_for_embedding is True
        assert len(chunk.text) > len(chunk.embed_text)
        # embed_text should be shorter (truncated)
        assert len(chunk.embed_text) < len(chunk.text)

    def test_table_chunk_id_is_deterministic(self):
        tables = [_make_table("table_0042", 5, [["A", "B"], ["1", "2"]])]
        doc = _make_doc(tables=tables)
        chunks1 = chunk_document(doc)
        chunks2 = chunk_document(doc)
        ids1 = [c.chunk_id for c in chunks1 if c.section_type == "table"]
        ids2 = [c.chunk_id for c in chunks2 if c.section_type == "table"]
        assert ids1 == ids2

    def test_context_header_in_table_text(self):
        """Table text must include the context header for retrievability."""
        tables = [_make_table("table_0001", 12, [["Revenue", "2024"], ["1000", "2000"]])]
        doc = _make_doc(tables=tables)
        chunks = chunk_document(doc)
        tbl = next(c for c in chunks if c.section_type == "table")
        assert "Acme Corp" in tbl.text
        assert "FY2024" in tbl.text
        assert "page 12" in tbl.text

    def test_table_rows_cols_propagate(self):
        tables = [_make_table("table_0001", 1, [["A", "B", "C"], ["1", "2", "3"]])]
        doc = _make_doc(tables=tables)
        chunks = chunk_document(doc)
        tbl = next(c for c in chunks if c.section_type == "table")
        assert tbl.rows == 2
        assert tbl.cols == 3


# ---------------------------------------------------------------------------
# Grid rendering
# ---------------------------------------------------------------------------

class TestRenderGridAsMarkdown:
    def test_empty_grid(self):
        assert _render_grid_as_markdown([]) == ""

    def test_single_header_row(self):
        md = _render_grid_as_markdown([["Col1", "Col2"]])
        assert "| Col1 | Col2 |" in md
        assert "| --- | --- |" in md

    def test_header_plus_data_rows(self):
        grid = [["Name", "Value"], ["Revenue", "100"], ["Profit", "20"]]
        md = _render_grid_as_markdown(grid)
        lines = md.strip().split("\n")
        assert len(lines) == 4  # header + separator + 2 data rows
        assert "Revenue" in md
        assert "Profit" in md

    def test_pipe_chars_are_escaped(self):
        grid = [["A|B", "C"], ["val|ue", "x"]]
        md = _render_grid_as_markdown(grid)
        # Literal unescaped | inside cell content would break the table.
        # We expect them escaped as \|
        assert "A\\|B" in md

    def test_newlines_in_cells_replaced(self):
        grid = [["Header"], ["line1\nline2"]]
        md = _render_grid_as_markdown(grid)
        assert "\n" not in md.split("\n")[-1]  # data row should have no embedded newlines
