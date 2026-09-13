"""
tests/test_vector_store.py
--------------------------
Unit tests for pensieve.vector_store — Qdrant collection + upsert logic.

All Qdrant client calls are mocked.  No real Qdrant instance is needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from pensieve.vector_store import (
    _chunk_id_to_point_id,
    ensure_collection,
    upsert_chunks,
    recreate_collection,
)
from pensieve.chunker import Chunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(
    chunk_id="abc123",
    doc_id="doc1",
    section_type="narrative",
    risk_flag=False,
    risk_reasons=None,
    table_id=None,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        source_filename="test.pdf",
        company_name="Acme Corp",
        fiscal_year="2024",
        reporting_period_type="annual",
        section_type=section_type,
        page_start=1,
        page_end=2,
        text="Sample text content.",
        embed_text="Sample text content.",
        truncated_for_embedding=False,
        table_id=table_id,
        risk_flag=risk_flag,
        risk_reasons=risk_reasons or [],
        rows=None if section_type == "narrative" else 3,
        cols=None if section_type == "narrative" else 2,
    )


def _make_mock_client(collection_exists: bool = False, existing_dim: int = 384):
    client = MagicMock()

    # get_collections — returns empty list or list with our collection.
    if collection_exists:
        col = MagicMock()
        col.name = "pensieve_chunks"
        client.get_collections.return_value = MagicMock(collections=[col])
        # get_collection returns info with the existing dim.
        dim_mock = MagicMock()
        dim_mock.size = existing_dim
        client.get_collection.return_value = MagicMock(
            config=MagicMock(params=MagicMock(vectors=dim_mock))
        )
    else:
        client.get_collections.return_value = MagicMock(collections=[])

    return client


# ---------------------------------------------------------------------------
# _chunk_id_to_point_id
# ---------------------------------------------------------------------------

class TestChunkIdToPointId:
    def test_returns_int(self):
        result = _chunk_id_to_point_id("abc123")
        assert isinstance(result, int)

    def test_deterministic(self):
        a = _chunk_id_to_point_id("same_id")
        b = _chunk_id_to_point_id("same_id")
        assert a == b

    def test_different_ids_produce_different_points(self):
        a = _chunk_id_to_point_id("id_one")
        b = _chunk_id_to_point_id("id_two")
        assert a != b

    def test_fits_in_64_bits(self):
        result = _chunk_id_to_point_id("test_chunk_id")
        assert 0 <= result < 2**64


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

class TestEnsureCollection:
    def test_creates_collection_when_absent(self):
        client = _make_mock_client(collection_exists=False)
        ensure_collection(client, vector_dim=384, collection="pensieve_chunks")
        client.create_collection.assert_called_once()
        call_kwargs = client.create_collection.call_args
        assert call_kwargs.kwargs["collection_name"] == "pensieve_chunks"

    def test_skips_creation_when_exists_same_dim(self):
        client = _make_mock_client(collection_exists=True, existing_dim=384)
        ensure_collection(client, vector_dim=384, collection="pensieve_chunks")
        client.create_collection.assert_not_called()

    def test_raises_on_dim_mismatch(self):
        client = _make_mock_client(collection_exists=True, existing_dim=384)
        with pytest.raises(ValueError, match="vector dimension"):
            ensure_collection(client, vector_dim=1536, collection="pensieve_chunks")

    def test_creates_payload_indexes_on_new_collection(self):
        client = _make_mock_client(collection_exists=False)
        ensure_collection(client, vector_dim=384, collection="pensieve_chunks")
        # Should have created indexes for company_name, fiscal_year, section_type, risk_flag.
        assert client.create_payload_index.call_count == 4
        field_names = {
            call_.kwargs.get("field_name") or call_.args[1]
            for call_ in client.create_payload_index.call_args_list
        }
        assert "company_name" in field_names
        assert "fiscal_year" in field_names
        assert "section_type" in field_names
        assert "risk_flag" in field_names


# ---------------------------------------------------------------------------
# upsert_chunks
# ---------------------------------------------------------------------------

class TestUpsertChunks:
    def test_upserts_correct_number_of_points(self):
        client = MagicMock()
        chunks = [_make_chunk(chunk_id=f"id{i}") for i in range(5)]
        vectors = [[0.1] * 384 for _ in range(5)]
        upsert_chunks(client, chunks, vectors, collection="pensieve_chunks")
        # All 5 points fit in one batch (EMBEDDING_BATCH_SIZE=64 by default).
        client.upsert.assert_called_once()

    def test_raises_on_length_mismatch(self):
        client = MagicMock()
        chunks = [_make_chunk()]
        vectors = [[0.1] * 384, [0.2] * 384]  # length mismatch
        with pytest.raises(ValueError, match="same length"):
            upsert_chunks(client, chunks, vectors)

    def test_payload_contains_required_fields(self):
        client = MagicMock()
        chunk = _make_chunk(
            chunk_id="c1",
            section_type="table",
            risk_flag=True,
            risk_reasons=["[repeated-header] test"],
            table_id="table_0042",
        )
        upsert_chunks(client, [chunk], [[0.5] * 384], collection="pensieve_chunks")
        call_args = client.upsert.call_args
        points = call_args.kwargs.get("points") or call_args.args[1] if call_args.args else call_args.kwargs["points"]
        # upsert is called with keyword args; extract from call.
        upsert_call = client.upsert.call_args
        # The points are a list of PointStruct — inspect payload.
        point = None
        for arg in list(upsert_call.args) + list(upsert_call.kwargs.values()):
            if isinstance(arg, list) and arg and hasattr(arg[0], "payload"):
                point = arg[0]
                break
        assert point is not None, "Could not find PointStruct in upsert call"
        payload = point.payload
        assert payload["chunk_id"] == "c1"
        assert payload["risk_flag"] is True
        assert payload["risk_reasons"] == ["[repeated-header] test"]
        assert payload["table_id"] == "table_0042"
        assert payload["section_type"] == "table"
        assert payload["company_name"] == "Acme Corp"
        assert payload["fiscal_year"] == "2024"

    def test_point_id_is_deterministic(self):
        """Same chunk_id always produces the same Qdrant point ID."""
        client1 = MagicMock()
        client2 = MagicMock()
        chunk = _make_chunk(chunk_id="fixed_id")
        upsert_chunks(client1, [chunk], [[0.1] * 384])
        upsert_chunks(client2, [chunk], [[0.1] * 384])

        def _extract_id(mock_client):
            upsert_call = mock_client.upsert.call_args
            for arg in list(upsert_call.args) + list(upsert_call.kwargs.values()):
                if isinstance(arg, list) and arg and hasattr(arg[0], "id"):
                    return arg[0].id
            return None

        id1 = _extract_id(client1)
        id2 = _extract_id(client2)
        assert id1 is not None
        assert id1 == id2

    def test_upsert_batches_large_input(self):
        """120 chunks with batch size 64 should result in 2 upsert calls."""
        client = MagicMock()
        chunks = [_make_chunk(chunk_id=f"id{i}") for i in range(120)]
        vectors = [[0.1] * 384 for _ in range(120)]
        with patch("pensieve.vector_store.EMBEDDING_BATCH_SIZE", 64):
            upsert_chunks(client, chunks, vectors, collection="pensieve_chunks")
        assert client.upsert.call_count == 2

    def test_full_text_in_payload_not_embed_text(self):
        """Payload text field should always be the full untruncated text."""
        client = MagicMock()
        chunk = _make_chunk()
        chunk.text = "FULL TEXT"
        chunk.embed_text = "TRUNCATED"
        chunk.truncated_for_embedding = True
        upsert_chunks(client, [chunk], [[0.1] * 384])
        upsert_call = client.upsert.call_args
        for arg in list(upsert_call.args) + list(upsert_call.kwargs.values()):
            if isinstance(arg, list) and arg and hasattr(arg[0], "payload"):
                assert arg[0].payload["text"] == "FULL TEXT"
                break


# ---------------------------------------------------------------------------
# recreate_collection
# ---------------------------------------------------------------------------

class TestRecreateCollection:
    def test_deletes_and_recreates_existing(self):
        client = _make_mock_client(collection_exists=True, existing_dim=384)
        # After delete_collection is called, simulate the collection being gone
        # so the subsequent ensure_collection call sees an empty list.
        empty_collections = MagicMock(collections=[])
        client.get_collections.side_effect = [
            client.get_collections.return_value,  # first call (in recreate: check existence)
            empty_collections,                     # second call (inside ensure_collection after delete)
        ]
        recreate_collection(client, vector_dim=384, collection="pensieve_chunks")
        client.delete_collection.assert_called_once_with(collection_name="pensieve_chunks")
        client.create_collection.assert_called_once()

    def test_creates_without_delete_if_absent(self):
        client = _make_mock_client(collection_exists=False)
        recreate_collection(client, vector_dim=384, collection="pensieve_chunks")
        client.delete_collection.assert_not_called()
        client.create_collection.assert_called_once()
