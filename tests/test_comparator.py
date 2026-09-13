"""
tests/test_comparator.py
-------------------------
Unit tests for pensieve.comparator (Phase 5: Multi-Document Comparison).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pensieve.comparator import (
    ComparisonEntity,
    PerEntityResult,
    compute_numeric_delta,
    detect_comparison_intent,
    execute_comparison,
    execute_per_entity_pipeline,
    extract_comparison_entities,
    resolve_entity,
    rollup_verification,
    synthesize_comparative_answer,
)
from pensieve.generator import GenerationResult
from pensieve.numeric_grounding import VerificationResult
from pensieve.retriever import RetrievedChunk


# ---------------------------------------------------------------------------
# Test Entity Resolution & Intent Detection
# ---------------------------------------------------------------------------

class TestEntityResolution:
    def test_resolve_entity_fuzzy_and_case_insensitive(self):
        known_docs = [
            {"company_name": "Republic Bancorp", "fiscal_year": "2024"},
            {"company_name": "LUX INDUSTRIES LIMITED", "fiscal_year": "2025-26"},
        ]

        # Case 1: Substring company name "lux" -> "LUX INDUSTRIES LIMITED"
        ent1 = ComparisonEntity(company_name="lux", fiscal_year="2025")
        res1 = resolve_entity(ent1, known_docs)
        assert res1.company_name == "LUX INDUSTRIES LIMITED"
        assert res1.fiscal_year == "2025-26"

        # Case 2: Substring "republic" and "FY24" -> "Republic Bancorp", "2024"
        ent2 = ComparisonEntity(company_name="republic", fiscal_year="FY24")
        res2 = resolve_entity(ent2, known_docs)
        assert res2.company_name == "Republic Bancorp"
        assert res2.fiscal_year == "2024"

    def test_detect_comparison_intent(self):
        # 0 entities -> False
        is_comp, _ = detect_comparison_intent("What is the business model?", entities=[])
        assert is_comp is False

        # 1 entity -> False
        is_comp, _ = detect_comparison_intent(
            "What was Republic Bancorp's revenue in 2024?",
            entities=[ComparisonEntity(company_name="Republic Bancorp", fiscal_year="2024")],
        )
        assert is_comp is False

        # 2 identical entities -> False
        is_comp, _ = detect_comparison_intent(
            "Tell me about Republic Bancorp",
            entities=[
                ComparisonEntity(company_name="Republic Bancorp", fiscal_year="2024"),
                ComparisonEntity(company_name="Republic Bancorp", fiscal_year="2024"),
            ],
        )
        assert is_comp is False

        # 2 distinct entities (different companies) -> True
        is_comp, _ = detect_comparison_intent(
            "Compare Lux Industries and Republic Bancorp",
            entities=[
                ComparisonEntity(company_name="LUX INDUSTRIES LIMITED", fiscal_year="2025-26"),
                ComparisonEntity(company_name="Republic Bancorp", fiscal_year="2024"),
            ],
        )
        assert is_comp is True

        # 2 distinct entities (same company, different years) -> True
        is_comp, _ = detect_comparison_intent(
            "Compare Republic Bancorp 2023 vs 2024",
            entities=[
                ComparisonEntity(company_name="Republic Bancorp", fiscal_year="2023"),
                ComparisonEntity(company_name="Republic Bancorp", fiscal_year="2024"),
            ],
        )
        assert is_comp is True


# ---------------------------------------------------------------------------
# Test Numeric Delta Computation (Deterministic Python math)
# ---------------------------------------------------------------------------

class TestNumericDeltaComputation:
    def test_compute_numeric_delta_increase(self):
        r1 = PerEntityResult(
            entity={"company_name": "Entity A"},
            intent="numeric",
            answer="Revenue was $100.0M",
            verification_status="verified",
            verification_reason="Found in cell",
            citations=[],
            numbers_extracted=["$100.0"],
        )
        r2 = PerEntityResult(
            entity={"company_name": "Entity B"},
            intent="numeric",
            answer="Revenue was $150.0M",
            verification_status="verified",
            verification_reason="Found in cell",
            citations=[],
            numbers_extracted=["$150.0"],
        )
        delta = compute_numeric_delta([r1, r2])
        assert delta is not None
        assert delta["absolute_delta"] == 50.0
        assert delta["percentage_delta"] == 50.0
        assert delta["direction"] == "increase"

    def test_compute_numeric_delta_decrease_and_negative(self):
        r1 = PerEntityResult(
            entity={"company_name": "Entity A"},
            intent="numeric",
            answer="Net income was $200",
            verification_status="verified",
            verification_reason="Found in cell",
            citations=[],
            numbers_extracted=["200"],
        )
        r2 = PerEntityResult(
            entity={"company_name": "Entity B"},
            intent="numeric",
            answer="Net income was -$50",
            verification_status="verified",
            verification_reason="Found in cell",
            citations=[],
            numbers_extracted=["-50"],
        )
        delta = compute_numeric_delta([r1, r2])
        assert delta is not None
        assert delta["absolute_delta"] == -250.0
        assert delta["percentage_delta"] == -125.0
        assert delta["direction"] == "decrease"

    def test_compute_numeric_delta_missing_numbers_returns_none(self):
        r1 = PerEntityResult(
            entity={"company_name": "Entity A"},
            intent="numeric",
            answer="Revenue not found",
            verification_status="no_context_found",
            verification_reason="None",
            citations=[],
            numbers_extracted=[],
        )
        r2 = PerEntityResult(
            entity={"company_name": "Entity B"},
            intent="numeric",
            answer="Revenue was $150.0M",
            verification_status="verified",
            verification_reason="Found in cell",
            citations=[],
            numbers_extracted=["150"],
        )
        delta = compute_numeric_delta([r1, r2])
        assert delta is None


# ---------------------------------------------------------------------------
# Test Rollup Verification (Weakest Link Rule)
# ---------------------------------------------------------------------------

class TestRollupVerification:
    def _make_res(self, status: str, comp: str = "Company") -> PerEntityResult:
        return PerEntityResult(
            entity={"company_name": comp},
            intent="numeric",
            answer="test answer",
            verification_status=status,
            verification_reason="test reason",
            citations=[],
        )

    def test_all_verified_yields_verified(self):
        res = [self._make_res("verified", "A"), self._make_res("verified", "B")]
        status, reason = rollup_verification(res)
        assert status == "verified"

    def test_unverified_trumps_all(self):
        res = [
            self._make_res("verified", "A"),
            self._make_res("verified_low_confidence", "B"),
            self._make_res("unverified", "C"),
        ]
        status, reason = rollup_verification(res)
        assert status == "unverified"
        assert "C" in reason

    def test_low_confidence_trumps_verified(self):
        res = [
            self._make_res("verified", "A"),
            self._make_res("verified_low_confidence", "B"),
        ]
        status, reason = rollup_verification(res)
        assert status == "verified_low_confidence"
        assert "B" in reason

    def test_mixed_coverage_when_one_has_no_context(self):
        res = [
            self._make_res("verified", "A"),
            self._make_res("no_context_found", "B"),
        ]
        status, reason = rollup_verification(res)
        assert status == "mixed_coverage"
        assert "B" in reason

    def test_all_no_context_found(self):
        res = [
            self._make_res("no_context_found", "A"),
            self._make_res("no_context_found", "B"),
        ]
        status, reason = rollup_verification(res)
        assert status == "no_context_found"

    def test_narrative_not_applicable(self):
        res = [
            self._make_res("not_applicable", "A"),
            self._make_res("not_applicable", "B"),
        ]
        status, reason = rollup_verification(res)
        assert status == "not_applicable"


# ---------------------------------------------------------------------------
# Test Per-Entity Execution Pipeline (Mocked)
# ---------------------------------------------------------------------------

class TestPerEntityPipeline:
    @patch("pensieve.comparator.generate_numeric_answer")
    @patch("pensieve.comparator.retrieve_table_chunks")
    def test_execute_per_entity_pipeline_numeric_verified(
        self, mock_retrieve, mock_gen
    ):
        mock_chunk = RetrievedChunk(
            chunk_id="chk_tbl_1",
            doc_id="doc_1",
            source_filename="doc1.pdf",
            company_name="Republic Bancorp",
            fiscal_year="2024",
            section_type="table",
            page_start=10,
            page_end=10,
            text="| Metric | 2024 |\n| Revenue | $500,000 |",
            score=0.92,
            table_id="tbl_1",
            risk_flag=False,
            risk_reasons=[],
        )
        mock_retrieve.return_value = [mock_chunk]

        mock_gen.return_value = GenerationResult(
            query="What was revenue?",
            answer="Revenue was $500,000 [1].",
            citations=[{
                "marker": "[1]",
                "chunk_id": "chk_tbl_1",
                "doc_id": "doc_1",
                "source_filename": "doc1.pdf",
                "company_name": "Republic Bancorp",
                "fiscal_year": "2024",
                "page_start": 10,
                "page_end": 10,
                "excerpt": "| Revenue | $500,000 |",
            }],
            no_context_found=False,
        )

        ent = ComparisonEntity(company_name="Republic Bancorp", fiscal_year="2024")
        res = execute_per_entity_pipeline("What was revenue?", ent, intent="numeric")

        assert res.intent == "numeric"
        assert res.verification_status == "verified"
        assert any("500,000" in n or "500000" in n for n in res.numbers_extracted)
        assert len(res.citations) == 1
        assert res.citations[0]["table_id"] == "tbl_1"

    @patch("pensieve.comparator.retrieve_narrative_chunks")
    def test_execute_per_entity_pipeline_no_context(self, mock_retrieve):
        mock_retrieve.return_value = []
        ent = ComparisonEntity(company_name="Unknown Corp", fiscal_year="2020")
        res = execute_per_entity_pipeline("Tell me about strategy", ent, intent="narrative")
        assert res.verification_status == "no_context_found"
        assert len(res.citations) == 0


# ---------------------------------------------------------------------------
# Test End-to-End Comparison Orchestration (Mocked)
# ---------------------------------------------------------------------------

class TestComparisonOrchestration:
    @patch("pensieve.comparator.execute_per_entity_pipeline")
    @patch("pensieve.comparator.classify_intent", return_value="numeric")
    @patch("pensieve.comparator._call_llm_with_retry", return_value="Comparison summary text [1][2].")
    def test_execute_comparison_success(self, mock_call_llm, mock_classify, mock_pipeline):
        r1 = PerEntityResult(
            entity={"company_name": "Comp A", "fiscal_year": "2024"},
            intent="numeric",
            answer="Comp A reported $100M revenue [1].",
            verification_status="verified",
            verification_reason="Cell match",
            citations=[{"marker": "[1]", "chunk_id": "chk_a", "table_id": "tbl_a"}],
            numbers_extracted=["100"],
        )
        r2 = PerEntityResult(
            entity={"company_name": "Comp B", "fiscal_year": "2024"},
            intent="numeric",
            answer="Comp B reported $120M revenue [2].",
            verification_status="verified",
            verification_reason="Cell match",
            citations=[{"marker": "[2]", "chunk_id": "chk_b", "table_id": "tbl_b"}],
            numbers_extracted=["120"],
        )
        mock_pipeline.side_effect = [r1, r2]

        entities = [
            ComparisonEntity(company_name="Comp A", fiscal_year="2024"),
            ComparisonEntity(company_name="Comp B", fiscal_year="2024"),
        ]

        resp = execute_comparison("Compare revenue of Comp A and Comp B", entities)

        assert resp.intent == "numeric"
        assert resp.verification_status == "verified"
        assert resp.no_context_found is False
        assert resp.deltas is not None
        assert resp.deltas["absolute_delta"] == 20.0
        assert resp.deltas["percentage_delta"] == 20.0
        assert len(resp.per_entity_results) == 2
        assert len(resp.citations) == 2
