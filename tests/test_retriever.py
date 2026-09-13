"""
tests/test_retriever.py
-----------------------
Unit tests for pensieve.retriever — narrative-only retrieval.

All Qdrant and embedder calls are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from qdrant_client.http import models as qmodels

from pensieve.retriever import RetrievedChunk, retrieve_narrative_chunks


def _make_scored_point(
    chunk_id: str = "chunk_1",
    score: float = 0.85,
    company_name: str = "Republic Bancorp",
    fiscal_year: str = "2024",
    section_type: str = "narrative",
    page_start: int = 10,
    page_end: int = 12,
    text: str = "Lending operations overview text.",
):
    pt = MagicMock()
    pt.score = score
    pt.payload = {
        "chunk_id": chunk_id,
        "doc_id": "doc_123",
        "source_filename": "report.pdf",
        "company_name": company_name,
        "fiscal_year": fiscal_year,
        "section_type": section_type,
        "page_start": page_start,
        "page_end": page_end,
        "text": text,
    }
    return pt


class TestRetrieveNarrativeChunks:
    def test_empty_query_returns_empty(self):
        chunks = retrieve_narrative_chunks("   ")
        assert chunks == []

    @patch("pensieve.retriever.embed_texts", return_value=[[0.1] * 384])
    def test_narrative_filter_always_applied(self, mock_embed):
        mock_client = MagicMock()
        mock_client.query_points.return_value = MagicMock(points=[_make_scored_point(score=0.8)])

        chunks = retrieve_narrative_chunks(
            query="test question",
            top_k=5,
            client=mock_client,
        )

        assert len(chunks) == 1
        assert chunks[0].chunk_id == "chunk_1"
        assert chunks[0].score == 0.8

        # Check call arguments to query_points
        _, kwargs = mock_client.query_points.call_args
        query_filter = kwargs["query_filter"]
        assert isinstance(query_filter, qmodels.Filter)
        # Verify section_type="narrative" condition is present
        narrative_cond = [
            c for c in query_filter.must
            if getattr(c, "key", None) == "section_type"
            and getattr(getattr(c, "match", None), "value", None) == "narrative"
        ]
        assert len(narrative_cond) == 1

    @patch("pensieve.retriever.embed_texts", return_value=[[0.1] * 384])
    def test_optional_filters_applied(self, mock_embed):
        mock_client = MagicMock()
        mock_client.query_points.return_value = MagicMock(points=[])

        retrieve_narrative_chunks(
            query="test question",
            company_name="Republic Bancorp",
            fiscal_year="2024",
            client=mock_client,
        )

        _, kwargs = mock_client.query_points.call_args
        query_filter = kwargs["query_filter"]
        field_keys = [getattr(c, "key", None) for c in query_filter.must]
        assert "section_type" in field_keys
        assert "company_name" in field_keys
        assert "fiscal_year" in field_keys

    @patch("pensieve.retriever.embed_texts", return_value=[[0.1] * 384])
    def test_score_threshold_filtering(self, mock_embed):
        mock_client = MagicMock()
        high_score = _make_scored_point("chunk_high", score=0.75)
        low_score = _make_scored_point("chunk_low", score=0.30)
        mock_client.query_points.return_value = MagicMock(points=[high_score, low_score])

        chunks = retrieve_narrative_chunks(
            query="test question",
            threshold=0.50,
            client=mock_client,
        )

        assert len(chunks) == 1
        assert chunks[0].chunk_id == "chunk_high"
        assert chunks[0].score == 0.75

    @patch("pensieve.retriever.embed_texts", return_value=[[0.1] * 384])
    def test_all_below_threshold_returns_empty(self, mock_embed):
        mock_client = MagicMock()
        low_score1 = _make_scored_point("chunk_low1", score=0.35)
        low_score2 = _make_scored_point("chunk_low2", score=0.25)
        mock_client.query_points.return_value = MagicMock(points=[low_score1, low_score2])

        chunks = retrieve_narrative_chunks(
            query="test question",
            threshold=0.50,
            client=mock_client,
        )

        assert chunks == []
