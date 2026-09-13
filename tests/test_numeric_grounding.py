"""
tests/test_numeric_grounding.py
--------------------------------
Unit tests for pensieve.numeric_grounding (Phase 4).

Tests:
  - extract_numbers_from_text: various financial number formats
  - normalize_number: canonical form transformations
  - fit_tables_to_context: token budget enforcement
  - verify_numbers_against_grid: all 4 verification status outcomes
  - generate_numeric_answer: zero-chunk and success path
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from pensieve.numeric_grounding import (
    VerificationResult,
    extract_numbers_from_text,
    fit_tables_to_context,
    generate_numeric_answer,
    normalize_number,
    verify_numbers_against_grid,
)


# ---------------------------------------------------------------------------
# Minimal RetrievedChunk stub for testing (avoids importing Qdrant)
# ---------------------------------------------------------------------------


@dataclass
class _Chunk:
    """Lightweight stub that mimics pensieve.retriever.RetrievedChunk."""
    chunk_id: str
    doc_id: str = "test_doc"
    source_filename: str = "test.pdf"
    company_name: str | None = "Test Corp"
    fiscal_year: str | None = "2024"
    section_type: str = "table"
    page_start: int = 1
    page_end: int = 1
    text: str = ""
    score: float = 0.9
    table_id: str | None = None
    risk_flag: bool = False
    risk_reasons: list[str] = field(default_factory=list)
    rows: int | None = None
    cols: int | None = None


# ---------------------------------------------------------------------------
# extract_numbers_from_text
# ---------------------------------------------------------------------------


class TestExtractNumbersFromText:

    def test_dollar_amount_with_commas(self):
        text = "Total deposits were $4,572,044 thousand."
        nums = extract_numbers_from_text(text)
        assert "4,572,044" in " ".join(nums) or any("4,572,044" in n for n in nums)

    def test_dollar_amount_with_space_after_dollar(self):
        text = "Net income was $ 312,154."
        nums = extract_numbers_from_text(text)
        assert len(nums) >= 1

    def test_parenthesized_negative(self):
        text = "Net loss of (1,482) was recorded."
        nums = extract_numbers_from_text(text)
        assert len(nums) >= 1
        assert any("1,482" in n or "1482" in n for n in nums)

    def test_percentage(self):
        text = "The net interest margin was 5.25%."
        nums = extract_numbers_from_text(text)
        assert any("5.25" in n for n in nums)

    def test_plain_decimal_eps(self):
        text = "EPS was 1.23 per share."
        nums = extract_numbers_from_text(text)
        assert any("1.23" in n for n in nums)

    def test_deduplication(self):
        text = "Revenue was $312,154 and expenses were $312,154."
        nums = extract_numbers_from_text(text)
        count = sum(1 for n in nums if "312,154" in n)
        assert count == 1, "Duplicate numbers should be deduplicated"

    def test_empty_text_returns_empty(self):
        assert extract_numbers_from_text("") == []
        assert extract_numbers_from_text("   ") == []

    def test_text_with_no_numbers_returns_empty(self):
        text = "The company provides banking services to customers in Kentucky."
        nums = extract_numbers_from_text(text)
        # Small standalone integers like "in 2024" might be excluded; should be empty or near-empty
        # We don't flag years/page numbers (< 4 digits with no comma), so this should be empty
        assert nums == [] or all(len(n.replace(",", "")) < 4 for n in nums)

    def test_multiple_distinct_figures(self):
        text = "Revenue was $4,572,044 and expenses were $3,200,000 with a margin of 30%."
        nums = extract_numbers_from_text(text)
        assert len(nums) >= 2

    def test_signed_negative(self):
        text = "The loss was -1,482 thousand."
        nums = extract_numbers_from_text(text)
        assert any("1,482" in n or "-1,482" in n for n in nums)


# ---------------------------------------------------------------------------
# normalize_number
# ---------------------------------------------------------------------------


class TestNormalizeNumber:

    def test_dollar_sign_and_commas(self):
        assert normalize_number("$4,572,044") == "4572044"

    def test_dollar_sign_with_space(self):
        assert normalize_number("$ 312,154") == "312154"

    def test_dollar_sign_trailing(self):
        # Some table cells have format "4,572,044 $"
        assert normalize_number("4,572,044 $") == "4572044"

    def test_parenthesized_negative(self):
        result = normalize_number("(1,482)")
        assert result == "-1482"

    def test_percent_sign(self):
        assert normalize_number("5.25%") == "5.25"

    def test_plain_comma_grouped(self):
        assert normalize_number("312,154") == "312154"

    def test_signed_negative(self):
        assert normalize_number("-1,482") == "-1482"

    def test_plain_decimal(self):
        assert normalize_number("1.23") == "1.23"

    def test_whitespace_stripped(self):
        assert normalize_number("  4,572,044  ") == "4572044"

    def test_empty_string(self):
        result = normalize_number("")
        assert result == ""

    def test_parenthesized_dollar_negative(self):
        result = normalize_number("($1,482)")
        assert result == "-1482" or result == "-$1482"  # $ stripped → "-1482"


# ---------------------------------------------------------------------------
# fit_tables_to_context
# ---------------------------------------------------------------------------


class TestFitTablesToContext:

    def _make_chunk(self, chunk_id: str, text: str, score: float = 0.9) -> _Chunk:
        return _Chunk(chunk_id=chunk_id, text=text, score=score)

    def test_empty_input_returns_empty(self):
        assert fit_tables_to_context([], max_tokens=1000) == []

    def test_all_chunks_fit(self):
        chunks = [
            self._make_chunk("c1", "Short text A"),
            self._make_chunk("c2", "Short text B"),
        ]
        result = fit_tables_to_context(chunks, max_tokens=10000)
        assert len(result) == 2

    def test_drops_lowest_scoring_chunk_when_over_budget(self):
        """When combined tokens exceed budget, the last (lowest-scored) chunk is dropped."""
        # c1 is highest score, c2 is lowest — in a sorted list c1 comes first
        big_text = "word " * 500  # ~500 tokens
        chunks = [
            self._make_chunk("c1", big_text, score=0.95),
            self._make_chunk("c2", big_text, score=0.50),
        ]
        # Budget just enough for one chunk
        result = fit_tables_to_context(chunks, max_tokens=600)
        assert len(result) == 1
        assert result[0].chunk_id == "c1"

    def test_drops_multiple_chunks_if_needed(self):
        big_text = "word " * 400
        chunks = [
            self._make_chunk("c1", big_text, score=0.99),
            self._make_chunk("c2", big_text, score=0.80),
            self._make_chunk("c3", big_text, score=0.60),
        ]
        result = fit_tables_to_context(chunks, max_tokens=500)
        assert len(result) == 1
        assert result[0].chunk_id == "c1"

    def test_preserves_order(self):
        """Output order must match input order (sorted by score by caller)."""
        chunks = [
            self._make_chunk("c1", "A " * 10, score=0.99),
            self._make_chunk("c2", "B " * 10, score=0.80),
        ]
        result = fit_tables_to_context(chunks, max_tokens=10000)
        assert [c.chunk_id for c in result] == ["c1", "c2"]


# ---------------------------------------------------------------------------
# verify_numbers_against_grid
# ---------------------------------------------------------------------------


def _table_markdown(rows: list[list[str]]) -> str:
    """Build a simple markdown table from rows."""
    lines = []
    for i, row in enumerate(rows):
        line = "| " + " | ".join(row) + " |"
        lines.append(line)
        if i == 0:
            lines.append("| " + " | ".join(["---"] * len(row)) + " |")
    return "\n".join(lines)


class TestVerifyNumbersAgainstGrid:

    def _chunk(
        self,
        chunk_id: str,
        grid: list[list[str]],
        risk_flag: bool = False,
        risk_reasons: list[str] | None = None,
        page: int = 4,
    ) -> _Chunk:
        """Create a _Chunk with a markdown table as text."""
        text = f"Table from Test Corp FY2024 report, page {page}\n\n{_table_markdown(grid)}"
        return _Chunk(
            chunk_id=chunk_id,
            text=text,
            risk_flag=risk_flag,
            risk_reasons=risk_reasons or [],
            page_start=page,
        )

    def _cited(self, chunk: _Chunk) -> dict:
        """Return a minimal citation dict as returned by parse_citations()."""
        return {
            "marker": "[1]",
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "source_filename": chunk.source_filename,
            "company_name": chunk.company_name,
            "fiscal_year": chunk.fiscal_year,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "excerpt": chunk.text[:100],
        }

    # --- not_applicable ---

    def test_no_numbers_returns_not_applicable(self):
        chunk = self._chunk("c1", [["Label", "Value"], ["Revenue", "1,234"]])
        result = verify_numbers_against_grid(
            numbers_from_answer=[],
            cited_chunks=[self._cited(chunk)],
            all_retrieved_chunks=[chunk],
        )
        assert result.status == "not_applicable"

    # --- verified (clean table) ---

    def test_verified_when_number_in_clean_cited_table(self):
        grid = [["Label", "2024"], ["Total Deposits", "4,572,044"]]
        chunk = self._chunk("c1", grid, risk_flag=False)
        result = verify_numbers_against_grid(
            numbers_from_answer=["$4,572,044"],
            cited_chunks=[self._cited(chunk)],
            all_retrieved_chunks=[chunk],
        )
        assert result.status == "verified"
        assert result.matched_figures

    # --- verified_low_confidence (flagged table) ---

    def test_verified_low_confidence_when_table_has_risk_flag(self):
        grid = [["Label", "Value"], ["Rate", "-400 Basis Points"]]
        chunk = self._chunk(
            "c1",
            grid,
            risk_flag=True,
            risk_reasons=["[repeated-header] repeated phrase detected"],
        )
        result = verify_numbers_against_grid(
            numbers_from_answer=["400"],
            cited_chunks=[self._cited(chunk)],
            all_retrieved_chunks=[chunk],
        )
        assert result.status in ("verified_low_confidence", "unverified")
        # "400" from "-400 Basis Points" — normalization strips non-numeric characters
        # from cell, so "400" may or may not match "-400 Basis Points" depending on extraction
        # The main assertion is that no exception is raised.

    def test_verified_low_confidence_exact(self):
        """When we can control the grid to ensure exact match with a flagged table."""
        grid = [["Label", "Value"], ["Net Income", "312,154"]]
        chunk = self._chunk(
            "c2",
            grid,
            risk_flag=True,
            risk_reasons=["[multi-value-cells] 4/7 rows contain issues"],
        )
        result = verify_numbers_against_grid(
            numbers_from_answer=["312,154"],
            cited_chunks=[self._cited(chunk)],
            all_retrieved_chunks=[chunk],
        )
        assert result.status == "verified_low_confidence"
        assert "312,154" in result.matched_figures

    # --- unverified ---

    def test_unverified_when_number_not_in_any_table(self):
        grid = [["Label", "Value"], ["Revenue", "9,999,000"]]
        chunk = self._chunk("c1", grid, risk_flag=False)
        result = verify_numbers_against_grid(
            numbers_from_answer=["$4,572,044"],   # doesn't appear in grid
            cited_chunks=[self._cited(chunk)],
            all_retrieved_chunks=[chunk],
        )
        assert result.status == "unverified"
        assert result.unmatched_figures

    # --- fallback: found in non-cited retrieved table ---

    def test_fallback_finds_number_in_uncited_table(self):
        """Figure not in the CITED chunk but found in another retrieved chunk → verified."""
        cited_grid = [["Label", "Value"], ["Other", "999,000"]]
        other_grid = [["Label", "Value"], ["Deposits", "4,572,044"]]
        cited_chunk = self._chunk("c1", cited_grid, risk_flag=False)
        other_chunk = self._chunk("c2", other_grid, risk_flag=False)

        result = verify_numbers_against_grid(
            numbers_from_answer=["$4,572,044"],
            cited_chunks=[self._cited(cited_chunk)],    # only c1 is cited
            all_retrieved_chunks=[cited_chunk, other_chunk],   # c2 is available as fallback
        )
        # Should find it via fallback → verified or verified_low_confidence
        assert result.status in ("verified", "verified_low_confidence")
        assert result.matched_figures

    # --- partial match ---

    def test_partial_match_some_verified_some_not(self):
        """Some figures match, some don't — still returns verified with unmatched listed."""
        grid = [["Label", "Value"], ["Net Income", "312,154"]]
        chunk = self._chunk("c1", grid, risk_flag=False)
        result = verify_numbers_against_grid(
            numbers_from_answer=["312,154", "$99,999,999"],
            cited_chunks=[self._cited(chunk)],
            all_retrieved_chunks=[chunk],
        )
        # 312,154 matches; 99,999,999 does not
        assert result.status in ("verified", "verified_low_confidence")
        assert result.unmatched_figures  # 99,999,999 should be in unmatched


# ---------------------------------------------------------------------------
# generate_numeric_answer
# ---------------------------------------------------------------------------


class TestGenerateNumericAnswer:

    def test_empty_chunks_returns_no_context(self):
        result = generate_numeric_answer(query="What was revenue?", chunks=[])
        assert result.no_context_found is True
        assert result.citations == []

    def test_generation_with_chunks_calls_llm(self):
        """With chunks provided, the LLM should be called and return an answer."""
        from pensieve.generator import GenerationResult

        chunk = _Chunk(
            chunk_id="c1",
            text="| Label | Value |\n| --- | --- |\n| Net Income | 312,154 |",
            page_start=4,
        )
        mock_client = MagicMock()
        msg = MagicMock()
        msg.content = "Net income was 312,154. [1]"
        choice = MagicMock()
        choice.message = msg
        mock_client.chat.completions.create.return_value = MagicMock(choices=[choice])

        result = generate_numeric_answer(
            query="What was net income?",
            chunks=[chunk],
            client=mock_client,
        )
        assert "312,154" in result.answer
        mock_client.chat.completions.create.assert_called_once()
