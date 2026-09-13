"""
tests/test_metadata_extractor.py
---------------------------------
Unit tests for pensieve.metadata_extractor validation logic.

These tests do NOT make real LLM API calls.  They test the
_parse_and_validate() function directly, mocking out the LLM layer.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import openai
import pytest

from pensieve import metadata_extractor
from pensieve.metadata_extractor import (
    _call_llm,
    _get_client,
    _parse_and_validate,
)


# ---------------------------------------------------------------------------
# Happy-path cases
# ---------------------------------------------------------------------------

class TestParseAndValidateHappyPath:
    def test_clean_annual_report(self):
        raw = json.dumps({
            "company_name": "Infosys Limited",
            "fiscal_year": "FY2024",
            "reporting_period_type": "annual",
        })
        result = _parse_and_validate(raw, "test.pdf")
        assert result["company_name"] == "Infosys Limited"
        assert result["fiscal_year"] == "FY2024"
        assert result["reporting_period_type"] == "annual"
        assert result["needs_review"] is False
        assert result["review_reasons"] == []

    def test_quarterly_report(self):
        raw = json.dumps({
            "company_name": "TCS",
            "fiscal_year": "Q2 FY2025",
            "reporting_period_type": "quarterly",
        })
        result = _parse_and_validate(raw, "tcs_q2.pdf")
        assert result["needs_review"] is False
        assert result["reporting_period_type"] == "quarterly"

    def test_indian_fy_format(self):
        """FY2023-24 format should pass year validation."""
        raw = json.dumps({
            "company_name": "HDFC Bank",
            "fiscal_year": "FY2023-24",
            "reporting_period_type": "annual",
        })
        result = _parse_and_validate(raw, "hdfc.pdf")
        assert result["needs_review"] is False
        assert result["fiscal_year"] == "FY2023-24"

    def test_markdown_fence_stripped(self):
        """Model sometimes wraps output in markdown code fences."""
        raw = '```json\n{"company_name": "Wipro", "fiscal_year": "FY2024", "reporting_period_type": "annual"}\n```'
        result = _parse_and_validate(raw, "wipro.pdf")
        assert result["company_name"] == "Wipro"
        assert result["needs_review"] is False

    def test_conversational_preamble_and_postamble(self):
        """Llama models frequently include polite preamble and postamble."""
        raw = (
            "Here is the metadata extracted from the cover page:\n\n"
            "```json\n"
            '{"company_name": "Tata Motors", "fiscal_year": "FY2023-24", "reporting_period_type": "annual"}\n'
            "```\n\n"
            "Let me know if you need anything else!"
        )
        result = _parse_and_validate(raw, "tatamotors.pdf")
        assert result["company_name"] == "Tata Motors"
        assert result["fiscal_year"] == "FY2023-24"
        assert result["reporting_period_type"] == "annual"
        assert result["needs_review"] is False

    def test_preamble_without_fences(self):
        """Conversational text directly preceding raw JSON."""
        raw = (
            'Sure! {"company_name": "LTIMindtree", "fiscal_year": "FY2024", "reporting_period_type": "annual"}'
        )
        result = _parse_and_validate(raw, "lti.pdf")
        assert result["company_name"] == "LTIMindtree"
        assert result["needs_review"] is False


# ---------------------------------------------------------------------------
# Validation failure — needs_review = True
# ---------------------------------------------------------------------------

class TestParseAndValidateNeedsReview:
    def test_empty_company_name(self):
        raw = json.dumps({
            "company_name": "",
            "fiscal_year": "FY2024",
            "reporting_period_type": "annual",
        })
        result = _parse_and_validate(raw, "test.pdf")
        assert result["needs_review"] is True
        assert any("company_name" in r for r in result["review_reasons"])

    def test_null_company_name(self):
        raw = json.dumps({
            "company_name": None,
            "fiscal_year": "FY2024",
            "reporting_period_type": "annual",
        })
        result = _parse_and_validate(raw, "test.pdf")
        assert result["needs_review"] is True

    def test_null_fiscal_year(self):
        raw = json.dumps({
            "company_name": "ICICI Bank",
            "fiscal_year": None,
            "reporting_period_type": "annual",
        })
        result = _parse_and_validate(raw, "test.pdf")
        assert result["needs_review"] is True
        assert any("fiscal_year" in r for r in result["review_reasons"])

    def test_year_out_of_range_too_old(self):
        raw = json.dumps({
            "company_name": "Old Corp",
            "fiscal_year": "FY1850",
            "reporting_period_type": "annual",
        })
        result = _parse_and_validate(raw, "test.pdf")
        assert result["needs_review"] is True
        assert any("outside sane range" in r for r in result["review_reasons"])

    def test_year_out_of_range_future(self):
        raw = json.dumps({
            "company_name": "Future Corp",
            "fiscal_year": "FY2099",
            "reporting_period_type": "annual",
        })
        result = _parse_and_validate(raw, "test.pdf")
        assert result["needs_review"] is True

    def test_no_year_in_fiscal_year_string(self):
        raw = json.dumps({
            "company_name": "Reliance",
            "fiscal_year": "Annual Period",
            "reporting_period_type": "annual",
        })
        result = _parse_and_validate(raw, "test.pdf")
        assert result["needs_review"] is True
        assert any("no recognisable 4-digit year" in r for r in result["review_reasons"])

    def test_non_json_response(self):
        raw = "Sorry, I cannot extract metadata from this document."
        result = _parse_and_validate(raw, "test.pdf")
        assert result["needs_review"] is True
        assert result["company_name"] is None
        assert result["fiscal_year"] is None

    def test_both_fields_null(self):
        raw = json.dumps({
            "company_name": None,
            "fiscal_year": None,
            "reporting_period_type": "other",
        })
        result = _parse_and_validate(raw, "test.pdf")
        assert result["needs_review"] is True
        assert len(result["review_reasons"]) >= 2


# ---------------------------------------------------------------------------
# Reporting period type normalisation
# ---------------------------------------------------------------------------

class TestReportingPeriodType:
    def test_unknown_type_defaults_to_other(self):
        raw = json.dumps({
            "company_name": "Bajaj Finance",
            "fiscal_year": "FY2024",
            "reporting_period_type": "semi-annual",  # not a valid enum value
        })
        result = _parse_and_validate(raw, "test.pdf")
        # Should not crash; should default period_type to 'other'
        assert result["reporting_period_type"] == "other"
        # And it should NOT trigger needs_review just for this
        # (period_type normalisation is lenient)
        assert result["needs_review"] is False


# ---------------------------------------------------------------------------
# NVIDIA NIM Client & Retry logic
# ---------------------------------------------------------------------------

class TestNvidiaNIMClient:
    def test_missing_api_key_raises_error(self, monkeypatch):
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        monkeypatch.setattr(metadata_extractor, "_client", None)
        with pytest.raises(EnvironmentError, match="NVIDIA_API_KEY is not set"):
            _get_client()

    def test_client_initialization_with_api_key(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key-12345")
        monkeypatch.setattr(metadata_extractor, "_client", None)
        client = _get_client()
        assert isinstance(client, openai.OpenAI)
        assert client.api_key == "nvapi-test-key-12345"
        assert "https://integrate.api.nvidia.com/v1" in str(client.base_url)

    def test_call_llm_retries_on_rate_limit(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key-12345")
        mock_client = MagicMock()
        monkeypatch.setattr(metadata_extractor, "_client", mock_client)

        # Mock rate limit error (429) then success
        mock_response_fail = openai.RateLimitError(
            message="Rate limit exceeded (429)",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        mock_response_success = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"company_name": "TestCorp", "fiscal_year": "FY2024", "reporting_period_type": "annual"}'
        mock_response_success.choices = [mock_choice]

        mock_client.chat.completions.create.side_effect = [
            mock_response_fail,
            mock_response_success,
        ]

        result = _call_llm("sample cover text")
        assert "TestCorp" in result
        assert mock_client.chat.completions.create.call_count == 2
