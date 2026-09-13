"""
tests/test_structurer.py
------------------------
Unit tests for pensieve.structurer.build_document_json().

Uses lightweight mock objects instead of running real Docling conversion.
Tests verify:
  - All required schema keys are present in output
  - doc_id is a 16-char hex string
  - extraction_metadata is populated correctly
  - text blocks and tables are structured correctly
  - needs_review propagates from metadata dict
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pensieve.structurer import build_document_json


# ---------------------------------------------------------------------------
# Mock Docling objects
# ---------------------------------------------------------------------------

def _make_text_item(text: str, page_no: int = 1, label_value: str = "text"):
    """Create a mock Docling TextItem."""
    item = MagicMock()
    item.text = text
    item.label = SimpleNamespace(value=label_value)
    prov = SimpleNamespace(page_no=page_no)
    item.prov = [prov]
    return item


def _make_table_cell(text: str, row: int, col: int):
    cell = MagicMock()
    cell.text = text
    cell.start_row_offset_idx = row
    cell.start_col_offset_idx = col
    return cell


def _make_table_item(cells: list, num_rows: int, num_cols: int, page_no: int = 2):
    """Create a mock Docling TableItem."""
    item = MagicMock()
    item.data = SimpleNamespace(
        num_rows=num_rows,
        num_cols=num_cols,
        table_cells=[
            _make_table_cell(text, r, c)
            for r, c, text in cells
        ],
    )
    prov = SimpleNamespace(page_no=page_no)
    item.prov = [prov]
    # No captions
    item.captions = []
    return item


def _make_result(text_items=None, table_items=None, errors=None):
    """Create a mock ConversionResult."""
    doc = MagicMock()
    doc.texts = text_items or []
    doc.tables = table_items or []
    doc.pages = [MagicMock()] * 5  # 5 pages

    result = MagicMock()
    result.document = doc
    result.errors = errors or []
    return result


def _make_metadata(
    company="Infosys Limited",
    fiscal_year="FY2024",
    period="annual",
    needs_review=False,
    reasons=None,
):
    return {
        "company_name": company,
        "fiscal_year": fiscal_year,
        "reporting_period_type": period,
        "needs_review": needs_review,
        "review_reasons": reasons or [],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSchemaCompleteness:
    """All required top-level keys must be present."""

    def test_all_top_level_keys_present(self, tmp_path):
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake content for hash")

        result = _make_result()
        metadata = _make_metadata()

        output = build_document_json(pdf, result, metadata)

        required_keys = {
            "doc_id", "source_filename", "company_name", "fiscal_year",
            "reporting_period_type", "num_pages", "extraction_metadata",
            "text_blocks", "tables",
        }
        assert required_keys.issubset(output.keys())

    def test_extraction_metadata_keys(self, tmp_path):
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake content")

        output = build_document_json(pdf, _make_result(), _make_metadata())

        em = output["extraction_metadata"]
        assert "docling_version" in em
        assert "converted_at" in em
        assert "conversion_errors" in em
        assert "needs_review" in em
        assert "review_reasons" in em

    def test_text_block_keys(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"fake pdf bytes")

        result = _make_result(
            text_items=[_make_text_item("Revenue grew 10%", page_no=3)]
        )
        output = build_document_json(pdf, result, _make_metadata())

        assert len(output["text_blocks"]) == 1
        block = output["text_blocks"][0]
        assert {"block_id", "page", "text", "section_hint"}.issubset(block.keys())

    def test_table_keys(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"fake pdf bytes")

        cells = [
            (0, 0, "Particulars"), (0, 1, "FY2024"), (0, 2, "FY2023"),
            (1, 0, "Revenue"), (1, 1, "1000"), (1, 2, "900"),
        ]
        result = _make_result(
            table_items=[_make_table_item(cells, num_rows=2, num_cols=3)]
        )
        output = build_document_json(pdf, result, _make_metadata())

        assert len(output["tables"]) == 1
        table = output["tables"][0]
        assert {"table_id", "page", "rows", "cols", "grid", "caption", "risk_flag", "risk_reasons"}.issubset(table.keys())


class TestDocId:
    def test_doc_id_is_16_char_hex(self, tmp_path):
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"Fake PDF bytes for hashing 12345")

        output = build_document_json(pdf, _make_result(), _make_metadata())

        doc_id = output["doc_id"]
        assert len(doc_id) == 16
        assert all(c in "0123456789abcdef" for c in doc_id)

    def test_doc_id_is_deterministic(self, tmp_path):
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"Same content every time")

        id1 = build_document_json(pdf, _make_result(), _make_metadata())["doc_id"]
        id2 = build_document_json(pdf, _make_result(), _make_metadata())["doc_id"]
        assert id1 == id2

    def test_different_content_gives_different_id(self, tmp_path):
        pdf1 = tmp_path / "doc1.pdf"
        pdf2 = tmp_path / "doc2.pdf"
        pdf1.write_bytes(b"Content A")
        pdf2.write_bytes(b"Content B")

        id1 = build_document_json(pdf1, _make_result(), _make_metadata())["doc_id"]
        id2 = build_document_json(pdf2, _make_result(), _make_metadata())["doc_id"]
        assert id1 != id2


class TestMetadataPropagation:
    def test_needs_review_propagates(self, tmp_path):
        pdf = tmp_path / "bad.pdf"
        pdf.write_bytes(b"bytes")

        metadata = _make_metadata(
            company=None,
            fiscal_year=None,
            needs_review=True,
            reasons=["company_name is empty"],
        )
        output = build_document_json(pdf, _make_result(), metadata)

        assert output["extraction_metadata"]["needs_review"] is True
        assert "company_name is empty" in output["extraction_metadata"]["review_reasons"]

    def test_company_and_fy_passed_through(self, tmp_path):
        pdf = tmp_path / "infosys.pdf"
        pdf.write_bytes(b"bytes")

        metadata = _make_metadata(company="Infosys Limited", fiscal_year="FY2024")
        output = build_document_json(pdf, _make_result(), metadata)

        assert output["company_name"] == "Infosys Limited"
        assert output["fiscal_year"] == "FY2024"


class TestTextBlocks:
    def test_section_hint_mapping(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"bytes")

        items = [
            _make_text_item("Introduction", label_value="section_header"),
            _make_text_item("Body text here", label_value="text"),
            _make_text_item("Note 1: ...", label_value="footnote"),
            _make_text_item("Some formula", label_value="formula"),
            _make_text_item("Unknown type", label_value="picture"),
        ]
        result = _make_result(text_items=items)
        output = build_document_json(pdf, result, _make_metadata())

        hints = [b["section_hint"] for b in output["text_blocks"]]
        assert hints[0] == "heading"
        assert hints[1] == "narrative"
        assert hints[2] == "footnote"
        assert hints[3] == "narrative"
        assert hints[4] == "unknown"

    def test_page_number_captured(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"bytes")

        items = [
            _make_text_item("Page 1 text", page_no=1),
            _make_text_item("Page 5 text", page_no=5),
        ]
        result = _make_result(text_items=items)
        output = build_document_json(pdf, result, _make_metadata())

        pages = [b["page"] for b in output["text_blocks"]]
        assert 1 in pages
        assert 5 in pages


class TestTables:
    def test_grid_reconstructed_correctly(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"bytes")

        # 2×3 table
        cells = [
            (0, 0, "Header A"), (0, 1, "Header B"), (0, 2, "Header C"),
            (1, 0, "Val 1"),    (1, 1, "Val 2"),    (1, 2, "Val 3"),
        ]
        result = _make_result(
            table_items=[_make_table_item(cells, num_rows=2, num_cols=3)]
        )
        output = build_document_json(pdf, result, _make_metadata())

        table = output["tables"][0]
        assert table["rows"] == 2
        assert table["cols"] == 3
        assert table["grid"][0] == ["Header A", "Header B", "Header C"]
        assert table["grid"][1] == ["Val 1", "Val 2", "Val 3"]

    def test_output_is_json_serialisable(self, tmp_path):
        """The output dict must round-trip through json.dumps without error."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"bytes")

        cells = [(0, 0, "₹ 1,00,000"), (0, 1, "FY2024")]
        result = _make_result(
            text_items=[_make_text_item("Some text with unicode: ₹")],
            table_items=[_make_table_item(cells, num_rows=1, num_cols=2)],
        )
        output = build_document_json(pdf, result, _make_metadata())

        # Should not raise
        serialised = json.dumps(output, ensure_ascii=False)
        restored = json.loads(serialised)
        assert restored["doc_id"] == output["doc_id"]
