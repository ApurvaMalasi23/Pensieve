"""
tests/test_generator.py
-----------------------
Unit tests for pensieve.generator — grounded generation and citation mapping.

All LLM calls are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pensieve.generator import (
    format_context_blocks,
    generate_answer,
    parse_citations,
    _is_refusal_answer,
)
from pensieve.retriever import RetrievedChunk


def _make_chunk(idx: int, page_start: int = 10, page_end: int = 10, text: str = "Some content") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"chunk_{idx}",
        doc_id="doc_abc",
        source_filename="annual_report.pdf",
        company_name="Republic Bancorp",
        fiscal_year="2024",
        section_type="narrative",
        page_start=page_start,
        page_end=page_end,
        text=text,
        score=0.88,
    )


class TestFormatContextBlocks:
    def test_single_page_format(self):
        chunks = [_make_chunk(1, page_start=15, page_end=15, text="First passage.")]
        res = format_context_blocks(chunks)
        assert "[1] Source: Republic Bancorp, FY2024, page 15" in res
        assert "First passage." in res

    def test_multi_page_format(self):
        chunks = [_make_chunk(1, page_start=15, page_end=17, text="Spanning passage.")]
        res = format_context_blocks(chunks)
        assert "[1] Source: Republic Bancorp, FY2024, pages 15-17" in res

    def test_multiple_chunks_numbered_sequentially(self):
        chunks = [
            _make_chunk(1, text="First passage."),
            _make_chunk(2, text="Second passage."),
        ]
        res = format_context_blocks(chunks)
        assert "[1] Source:" in res
        assert "[2] Source:" in res


class TestParseCitations:
    def test_valid_citations_mapped(self):
        chunks = [
            _make_chunk(1, page_start=10, page_end=11, text="Text for chunk one."),
            _make_chunk(2, page_start=20, page_end=20, text="Text for chunk two."),
        ]
        answer = "Republic Bancorp operates primarily in lending [1] and wealth management [2]."
        citations = parse_citations(answer, chunks)

        assert len(citations) == 2
        assert citations[0]["marker"] == "[1]"
        assert citations[0]["page_start"] == 10
        assert citations[0]["page_end"] == 11
        assert citations[0]["company_name"] == "Republic Bancorp"
        assert citations[0]["fiscal_year"] == "2024"
        assert "Text for chunk one" in citations[0]["excerpt"]

        assert citations[1]["marker"] == "[2]"
        assert citations[1]["page_start"] == 20

    def test_hallucinated_citations_dropped(self):
        chunks = [_make_chunk(1, text="Only chunk.")]
        # The model hallucinates [2] and [9]
        answer = "Claim one [1], claim two [2], and claim three [9]."
        citations = parse_citations(answer, chunks)

        assert len(citations) == 1
        assert citations[0]["marker"] == "[1]"

    def test_citations_deduplicated_preserving_order(self):
        chunks = [
            _make_chunk(1, text="Chunk 1"),
            _make_chunk(2, text="Chunk 2"),
        ]
        answer = "First point [2]. Second point [1]. Another point [2]."
        citations = parse_citations(answer, chunks)

        assert len(citations) == 2
        assert [c["marker"] for c in citations] == ["[2]", "[1]"]


class TestRefusalDetection:
    def test_refusal_patterns(self):
        assert _is_refusal_answer("I cannot answer from the provided context.")
        assert _is_refusal_answer("The provided documents do not contain information about this.")
        assert _is_refusal_answer("There is no relevant information provided in the report.")
        assert not _is_refusal_answer("Republic Bancorp grew loans by 12% in FY2024 [1].")


class TestGenerateAnswer:
    def test_empty_chunks_skips_llm(self):
        result = generate_answer("What is the stock price?", [])
        assert result.no_context_found is True
        assert result.citations == []
        assert "No relevant information found" in result.answer

    def test_successful_generation(self):
        chunks = [
            _make_chunk(1, text="Republic Bancorp provides retail and commercial banking."),
        ]
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Republic Bancorp offers commercial banking services [1]."))
        ]
        mock_client.chat.completions.create.return_value = mock_completion

        result = generate_answer("What does the bank do?", chunks, client=mock_client)

        assert result.no_context_found is False
        assert len(result.citations) == 1
        assert result.citations[0]["marker"] == "[1]"
        assert result.citations[0]["page_start"] == 10
        assert "commercial banking services [1]" in result.answer

    def test_generation_refusal_sets_no_context(self):
        chunks = [
            _make_chunk(1, text="General discussion about macroeconomic trends."),
        ]
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="I cannot answer this question as the provided documents do not contain details on space exploration."))
        ]
        mock_client.chat.completions.create.return_value = mock_completion

        result = generate_answer("What are their space missions?", chunks, client=mock_client)

        assert result.no_context_found is True
        assert len(result.citations) == 0
