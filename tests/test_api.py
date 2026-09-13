"""
tests/test_api.py
-----------------
Unit tests for pensieve.api — FastAPI endpoints (/query, /health).

Uses FastAPI TestClient with mocked retrieval and generation services.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from pensieve.api import app
from pensieve.generator import GenerationResult
from pensieve.retriever import RetrievedChunk

client = TestClient(app)


class TestHealthEndpoint:
    @patch("pensieve.api.get_client")
    def test_health_ok(self, mock_get_client):
        mock_qdrant = MagicMock()
        mock_col = MagicMock()
        mock_col.name = "pensieve_chunks"
        mock_qdrant.get_collections.return_value = MagicMock(collections=[mock_col])
        mock_qdrant.get_collection.return_value = MagicMock(points_count=484)
        mock_get_client.return_value = mock_qdrant

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["qdrant_connected"] is True
        assert data["points_count"] == 484

    @patch("pensieve.api.get_client")
    def test_health_degraded_when_collection_missing(self, mock_get_client):
        mock_qdrant = MagicMock()
        mock_qdrant.get_collections.return_value = MagicMock(collections=[])
        mock_get_client.return_value = mock_qdrant

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["qdrant_connected"] is True
        assert data["points_count"] == 0

    @patch("pensieve.api.get_client", side_effect=ConnectionError("Cannot connect to Qdrant"))
    def test_health_unhealthy_when_connection_fails(self, mock_get_client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["qdrant_connected"] is False


class TestQueryEndpoint:
    def test_query_validation_empty_string(self):
        response = client.post("/query", json={"query": "   "})
        assert response.status_code == 422

    def test_query_validation_missing_field(self):
        response = client.post("/query", json={})
        assert response.status_code == 422

    @patch("pensieve.api.generate_answer")
    @patch("pensieve.api.retrieve_narrative_chunks")
    def test_query_success_path(self, mock_retrieve, mock_generate):
        mock_chunk = RetrievedChunk(
            chunk_id="chunk_1",
            doc_id="doc_1",
            source_filename="report.pdf",
            company_name="Republic Bancorp",
            fiscal_year="2024",
            section_type="narrative",
            page_start=12,
            page_end=12,
            text="Republic Bancorp engages in commercial lending.",
            score=0.89,
        )
        mock_retrieve.return_value = [mock_chunk]

        mock_generate.return_value = GenerationResult(
            query="What is their lending activity?",
            answer="Republic Bancorp engages in commercial lending [1].",
            citations=[
                {
                    "marker": "[1]",
                    "doc_id": "doc_1",
                    "source_filename": "report.pdf",
                    "company_name": "Republic Bancorp",
                    "fiscal_year": "2024",
                    "page_start": 12,
                    "page_end": 12,
                    "excerpt": "Republic Bancorp engages in commercial lending.",
                }
            ],
            no_context_found=False,
        )

        response = client.post(
            "/query",
            json={
                "query": "What is their lending activity?",
                "company_name": "Republic Bancorp",
                "fiscal_year": "2024",
                "top_k": 5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "What is their lending activity?"
        assert "[1]" in data["answer"]
        assert len(data["citations"]) == 1
        assert data["citations"][0]["marker"] == "[1]"
        assert data["citations"][0]["page_start"] == 12
        assert data["no_context_found"] is False

    @patch("pensieve.api.retrieve_narrative_chunks", side_effect=RuntimeError("Qdrant failure"))
    def test_query_retrieval_error_returns_503(self, mock_retrieve):
        response = client.post("/query", json={"query": "Any question?"})
        assert response.status_code == 503
        data = response.json()
        assert "Retrieval service failure" in data["detail"]

    @patch("pensieve.api.retrieve_narrative_chunks", return_value=[])
    @patch("pensieve.api.generate_answer", side_effect=RuntimeError("NIM API timeout"))
    def test_query_generation_error_returns_500(self, mock_generate, mock_retrieve):
        response = client.post("/query", json={"query": "Any question?"})
        assert response.status_code == 500
        data = response.json()
        assert "LLM generation service failure" in data["detail"]


class TestAskEndpoint:
    def test_ask_validation_empty_string(self):
        response = client.post("/ask", json={"query": "   "})
        assert response.status_code == 422

    def test_ask_validation_missing_field(self):
        response = client.post("/ask", json={})
        assert response.status_code == 422

    @patch("pensieve.api.generate_answer")
    @patch("pensieve.api.retrieve_narrative_chunks")
    @patch("pensieve.api.classify_intent", return_value="narrative")
    def test_ask_routes_to_narrative(self, mock_classify, mock_retrieve, mock_generate):
        mock_chunk = RetrievedChunk(
            chunk_id="chk_narr_1",
            doc_id="doc_1",
            source_filename="rep.pdf",
            company_name="Republic Bancorp",
            fiscal_year="2024",
            section_type="narrative",
            page_start=5,
            page_end=5,
            text="Executive overview narrative.",
            score=0.91,
        )
        mock_retrieve.return_value = [mock_chunk]
        mock_generate.return_value = GenerationResult(
            query="What is the overview?",
            answer="The overview is positive [1].",
            citations=[
                {
                    "marker": "[1]",
                    "chunk_id": "chk_narr_1",
                    "doc_id": "doc_1",
                    "source_filename": "rep.pdf",
                    "company_name": "Republic Bancorp",
                    "fiscal_year": "2024",
                    "page_start": 5,
                    "page_end": 5,
                    "excerpt": "Executive overview narrative.",
                }
            ],
            no_context_found=False,
        )

        resp = client.post("/ask", json={"query": "What is the overview?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "narrative"
        assert data["verification"]["status"] == "not_applicable"
        assert len(data["citations"]) == 1
        assert data["citations"][0]["marker"] == "[1]"

    @patch("pensieve.api.verify_numbers_against_grid")
    @patch("pensieve.api.extract_numbers_from_text", return_value=["4,572,044"])
    @patch("pensieve.api.generate_numeric_answer")
    @patch("pensieve.api.fit_tables_to_context")
    @patch("pensieve.api.retrieve_table_chunks")
    @patch("pensieve.api.classify_intent", return_value="numeric")
    def test_ask_routes_to_numeric_verified(
        self, mock_classify, mock_retrieve, mock_fit, mock_gen, mock_extract, mock_verify
    ):
        from pensieve.numeric_grounding import VerificationResult

        mock_table_chunk = RetrievedChunk(
            chunk_id="chk_tbl_1",
            doc_id="doc_1",
            source_filename="rep.pdf",
            company_name="Republic Bancorp",
            fiscal_year="2024",
            section_type="table",
            page_start=4,
            page_end=4,
            text="| Deposits | 4,572,044 |",
            score=0.95,
            table_id="table_0000",
            risk_flag=False,
        )
        mock_retrieve.return_value = [mock_table_chunk]
        mock_fit.return_value = [mock_table_chunk]
        mock_gen.return_value = GenerationResult(
            query="What were total deposits?",
            answer="Deposits were 4,572,044 thousand dollars [1].",
            citations=[
                {
                    "marker": "[1]",
                    "chunk_id": "chk_tbl_1",
                    "doc_id": "doc_1",
                    "source_filename": "rep.pdf",
                    "company_name": "Republic Bancorp",
                    "fiscal_year": "2024",
                    "page_start": 4,
                    "page_end": 4,
                    "excerpt": "| Deposits | 4,572,044 |",
                }
            ],
            no_context_found=False,
        )
        mock_verify.return_value = VerificationResult(
            status="verified",
            reason="Found in clean table",
            matched_figures=["4,572,044"],
            unmatched_figures=[],
        )

        resp = client.post("/ask", json={"query": "What were total deposits?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "numeric"
        assert data["verification"]["status"] == "verified"
        assert "Found in clean table" in data["verification"]["reason"]
        assert len(data["citations"]) == 1
        assert data["citations"][0]["table_id"] == "table_0000"
        assert data["citations"][0]["risk_flag"] is False
        assert data["comparison"] is False
        assert data["entities_compared"] == []

    @patch("pensieve.api.execute_comparison")
    @patch("pensieve.api.detect_comparison_intent")
    def test_ask_routes_to_comparison(self, mock_detect, mock_execute):
        from pensieve.comparator import ComparisonEntity, ComparisonResponse

        ent_a = ComparisonEntity(company_name="Republic Bancorp", fiscal_year="2024")
        ent_b = ComparisonEntity(company_name="LUX INDUSTRIES LIMITED", fiscal_year="2025-26")
        mock_detect.return_value = (True, [ent_a, ent_b])

        mock_execute.return_value = ComparisonResponse(
            query="Compare revenue of Republic Bancorp and Lux",
            intent="numeric",
            comparison_answer="Comparative answer with delta [1][2].",
            verification_status="verified",
            verification_reason="All figures verified in tables.",
            per_entity_results=[
                {
                    "entity": ent_a.to_dict(),
                    "intent": "numeric",
                    "answer": "Revenue was 100",
                    "verification_status": "verified",
                    "verification_reason": "ok",
                    "citations": [{"marker": "[1]", "chunk_id": "c1", "doc_id": "d1"}],
                    "numbers_extracted": ["100"],
                    "risk_flag": False,
                    "risk_reasons": [],
                },
                {
                    "entity": ent_b.to_dict(),
                    "intent": "numeric",
                    "answer": "Revenue was 150",
                    "verification_status": "verified",
                    "verification_reason": "ok",
                    "citations": [{"marker": "[2]", "chunk_id": "c2", "doc_id": "d2"}],
                    "numbers_extracted": ["150"],
                    "risk_flag": False,
                    "risk_reasons": [],
                },
            ],
            deltas={
                "absolute_delta": 50.0,
                "percentage_delta": 50.0,
                "direction": "increase",
            },
            citations=[
                {"marker": "[1]", "chunk_id": "c1", "doc_id": "d1", "page_start": 1, "page_end": 1, "excerpt": "100"},
                {"marker": "[2]", "chunk_id": "c2", "doc_id": "d2", "page_start": 2, "page_end": 2, "excerpt": "150"},
            ],
            no_context_found=False,
        )

        resp = client.post("/ask", json={"query": "Compare revenue of Republic Bancorp and Lux"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["comparison"] is True
        assert len(data["entities_compared"]) == 2
        assert len(data["per_entity_results"]) == 2
        assert data["deltas"]["absolute_delta"] == 50.0
        assert data["verification"]["status"] == "verified"
        assert len(data["citations"]) == 2

    @patch("pensieve.api.retrieve_narrative_chunks", return_value=[])
    @patch("pensieve.api.detect_comparison_intent")
    @patch("pensieve.api.classify_intent", return_value="narrative")
    def test_ask_pinned_company_bypasses_comparison(self, mock_classify, mock_detect, mock_retrieve):
        # Even if query says "compare", passing explicit company_name in request pins single-doc path
        resp = client.post(
            "/ask",
            json={
                "query": "Compare Republic Bancorp and Lux",
                "company_name": "Republic Bancorp",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["comparison"] is False
        mock_detect.assert_not_called()


