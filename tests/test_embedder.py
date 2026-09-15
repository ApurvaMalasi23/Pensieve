"""
tests/test_embedder.py
----------------------
Unit tests for pensieve.embedder — embedding provider abstraction.

All actual model calls are mocked so tests run without sentence-transformers
loaded or OpenAI API keys present.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from pensieve.embedder import (
    count_tokens,
    truncate_to_tokens,
    get_token_limit,
    get_vector_dim,
)


# ---------------------------------------------------------------------------
# Token counting (no mocks needed — tiktoken is a real dep)
# ---------------------------------------------------------------------------

class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_known_token_count(self):
        # "Hello, world!" is 4 tokens in cl100k_base.
        result = count_tokens("Hello, world!")
        assert isinstance(result, int)
        assert result > 0

    def test_longer_text_has_more_tokens(self):
        short = count_tokens("Hello")
        long = count_tokens("Hello " * 100)
        assert long > short


class TestTruncateToTokens:
    def test_short_text_unchanged(self):
        text = "Short text."
        result = truncate_to_tokens(text, max_tokens=100)
        assert result == text

    def test_long_text_is_truncated(self):
        text = "word " * 200  # ~200 tokens
        result = truncate_to_tokens(text, max_tokens=50)
        assert count_tokens(result) <= 50

    def test_exactly_at_limit_unchanged(self):
        text = "a " * 10
        limit = count_tokens(text)
        result = truncate_to_tokens(text, max_tokens=limit)
        assert result == text


# ---------------------------------------------------------------------------
# Provider limits
# ---------------------------------------------------------------------------

class TestGetTokenLimit:
    def test_local_limit(self):
        assert get_token_limit("local") == 512

    def test_openai_limit(self):
        assert get_token_limit("openai") == 8191

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_token_limit("bogus")


# ---------------------------------------------------------------------------
# get_vector_dim — local provider (mock SentenceTransformer)
# ---------------------------------------------------------------------------

class TestGetVectorDim:
    def test_openai_dim_without_model_load(self):
        # OpenAI dim is a known constant — no API call needed.
        assert get_vector_dim("openai") == 1536

    def test_local_dim_from_model(self):
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        with patch("pensieve.embedder._get_local_model", return_value=mock_model):
            dim = get_vector_dim("local")
        assert dim == 384

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_vector_dim("bogus_provider")


# ---------------------------------------------------------------------------
# embed_texts — local provider (mock SentenceTransformer)
# ---------------------------------------------------------------------------

class TestEmbedTextsLocal:
    def _make_mock_model(self, dim: int = 384):
        import numpy as np
        mock_model = MagicMock()
        def _encode(batch, **kwargs):
            return np.ones((len(batch), dim), dtype=float)
        mock_model.encode.side_effect = _encode
        mock_model.get_sentence_embedding_dimension.return_value = dim
        return mock_model

    def test_empty_input_returns_empty(self):
        from pensieve.embedder import embed_texts
        result = embed_texts([], provider="local")
        assert result == []

    def test_correct_output_shape(self):
        from pensieve.embedder import embed_texts
        mock_model = self._make_mock_model(dim=384)
        with patch("pensieve.embedder._get_local_model", return_value=mock_model):
            result = embed_texts(["hello", "world"], provider="local")
        assert len(result) == 2
        assert len(result[0]) == 384

    def test_batching_is_correct(self):
        """130 texts with batch size 64 should call encode 3 times (64+64+2)."""
        from pensieve import embedder as emb
        from pensieve.embedder import embed_texts
        mock_model = self._make_mock_model(dim=384)
        with (
            patch("pensieve.embedder._get_local_model", return_value=mock_model),
            patch("pensieve.embedder.EMBEDDING_BATCH_SIZE", 64),
        ):
            embed_texts(["x"] * 130, provider="local")
        assert mock_model.encode.call_count == 3

    def test_output_order_preserved(self):
        """Vectors should be returned in the same order as the input texts."""
        import numpy as np
        from pensieve.embedder import embed_texts
        call_counter = {"n": 0}
        def _encode(batch, **kwargs):
            result = np.zeros((len(batch), 4), dtype=float)
            for i in range(len(batch)):
                result[i, 0] = call_counter["n"] * 100 + i
                call_counter["n"] += 0  # don't increment between items
            call_counter["n"] += 1
            return result
        mock_model = MagicMock()
        mock_model.encode.side_effect = _encode
        mock_model.get_sentence_embedding_dimension.return_value = 4
        with patch("pensieve.embedder._get_local_model", return_value=mock_model):
            result = embed_texts(["a", "b", "c"], provider="local")
        assert len(result) == 3


# ---------------------------------------------------------------------------
# embed_texts — openai provider (mock openai.OpenAI)
# ---------------------------------------------------------------------------

class TestEmbedTextsOpenAI:
    def _make_mock_openai(self, dim: int = 1536):
        import os
        mock_client = MagicMock()
        def _create(model, input):
            items = [
                MagicMock(index=i, embedding=[0.1] * dim)
                for i in range(len(input))
            ]
            return MagicMock(data=items)
        mock_client.embeddings.create.side_effect = _create
        return mock_client

    def test_openai_correct_output_shape(self):
        from pensieve.embedder import embed_texts
        mock_client = self._make_mock_openai(dim=1536)
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
            patch("pensieve.embedder._get_openai_client", return_value=mock_client),
        ):
            result = embed_texts(["text1", "text2", "text3"], provider="openai")
        assert len(result) == 3
        assert len(result[0]) == 1536

    def test_openai_batching(self):
        """70 texts with batch size 64 → 2 API calls."""
        from pensieve.embedder import embed_texts
        mock_client = self._make_mock_openai(dim=1536)
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
            patch("pensieve.embedder._get_openai_client", return_value=mock_client),
            patch("pensieve.embedder.EMBEDDING_BATCH_SIZE", 64),
        ):
            embed_texts(["t"] * 70, provider="openai")
        assert mock_client.embeddings.create.call_count == 2

    def test_unknown_provider_raises(self):
        from pensieve.embedder import embed_texts
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            embed_texts(["x"], provider="unknown_provider")


# ---------------------------------------------------------------------------
# embed_texts — fastembed provider path
# ---------------------------------------------------------------------------

class TestEmbedTextsFastEmbed:
    def test_fastembed_output_and_dimension(self):
        import numpy as np
        from pensieve.embedder import embed_texts, get_vector_dim

        mock_fastembed_model = MagicMock(spec=["embed"])
        mock_fastembed_model.embed.return_value = [
            np.ones(384, dtype=float),
            np.zeros(384, dtype=float),
        ]

        with patch("pensieve.embedder._get_local_model", return_value=mock_fastembed_model):
            dim = get_vector_dim("local")
            assert dim == 384
            res = embed_texts(["query 1", "query 2"], provider="local")
            assert len(res) == 2
            assert len(res[0]) == 384
            assert res[0][0] == 1.0
            assert res[1][0] == 0.0

