"""
tests/test_classifier.py
------------------------
Unit tests for pensieve.classifier.classify_intent (Phase 4).

All tests mock the OpenAI / NIM LLM call so no network access is needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pensieve.classifier import classify_intent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_openai_response(content: str) -> MagicMock:
    """Build a minimal mock that looks like an OpenAI ChatCompletion response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


def _mock_client(content: str) -> MagicMock:
    """Return a mock OpenAI client whose .chat.completions.create() returns content."""
    client = MagicMock()
    client.chat.completions.create.return_value = _make_openai_response(content)
    return client


# ---------------------------------------------------------------------------
# Classification correctness
# ---------------------------------------------------------------------------


class TestClassifyIntentRouting:
    """Verify that LLM responses are correctly mapped to 'narrative' or 'numeric'."""

    def test_returns_narrative_for_narrative_response(self):
        client = _mock_client("narrative")
        result = classify_intent("What are Republic Bancorp's primary lending activities?", client=client)
        assert result == "narrative"

    def test_returns_numeric_for_numeric_response(self):
        client = _mock_client("numeric")
        result = classify_intent("What were total deposits as of December 31, 2024?", client=client)
        assert result == "numeric"

    def test_narrative_with_leading_whitespace_still_classified(self):
        """Model may return '  narrative\n' — strip + startswith must handle it."""
        client = _mock_client("  narrative\n")
        result = classify_intent("Who is the CEO?", client=client)
        assert result == "narrative"

    def test_ambiguous_response_defaults_to_numeric(self):
        """Any response that is not exactly 'narrative' should produce 'numeric'."""
        client = _mock_client("I am not sure.")
        result = classify_intent("Tell me about deposits", client=client)
        assert result == "numeric"

    def test_empty_model_response_defaults_to_numeric(self):
        """Empty LLM response should default to 'numeric'."""
        client = _mock_client("")
        result = classify_intent("What was net income?", client=client)
        assert result == "numeric"

    def test_partial_match_numeric(self):
        """'numeric answer' starts with 'numeric' but should still be 'numeric'."""
        client = _mock_client("numeric answer")
        result = classify_intent("What was EPS?", client=client)
        assert result == "numeric"

    def test_partial_match_narrative(self):
        """'narrative description' starts with 'narrative' — should be 'narrative'."""
        client = _mock_client("narrative description")
        result = classify_intent("Describe the risk management strategy", client=client)
        assert result == "narrative"


# ---------------------------------------------------------------------------
# Failure / error handling
# ---------------------------------------------------------------------------


class TestClassifyIntentFailure:
    """Verify that failures default to 'numeric' without crashing."""

    def test_llm_exception_defaults_to_numeric(self):
        """If the LLM call raises any exception, default to 'numeric' (safer path)."""
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("Connection error")
        result = classify_intent("What was revenue?", client=client)
        assert result == "numeric"

    def test_empty_query_defaults_to_numeric(self):
        """Empty query should immediately default to 'numeric' without calling the LLM."""
        client = MagicMock()
        result = classify_intent("", client=client)
        assert result == "numeric"
        # LLM should not be called for empty queries
        client.chat.completions.create.assert_not_called()

    def test_whitespace_only_query_defaults_to_numeric(self):
        """Whitespace-only query behaves like empty query."""
        client = MagicMock()
        result = classify_intent("   ", client=client)
        assert result == "numeric"
        client.chat.completions.create.assert_not_called()


# ---------------------------------------------------------------------------
# Numeric bias: when in doubt, default to numeric
# ---------------------------------------------------------------------------


class TestNumericBias:
    """Verify the design principle: bias toward 'numeric' when ambiguous."""

    @pytest.mark.parametrize("response", [
        "NARRATIVE",   # upper-case — doesn't start with 'narrative'
        "Narrative",   # Title-case — doesn't start with 'narrative' after lower()... wait, it does
    ])
    def test_case_insensitive_narrative(self, response):
        """After lowercasing, 'NARRATIVE' and 'Narrative' both start with 'narrative'."""
        client = _mock_client(response)
        result = classify_intent("Describe the business model", client=client)
        assert result == "narrative"

    @pytest.mark.parametrize("response", [
        "NUMERIC",
        "Numeric",
        "Number",
        "0",
        "Yes, numeric.",
    ])
    def test_non_narrative_responses_are_numeric(self, response):
        """Any response that doesn't start with 'narrative' → 'numeric'."""
        client = _mock_client(response)
        result = classify_intent("test query", client=client)
        assert result == "numeric"
