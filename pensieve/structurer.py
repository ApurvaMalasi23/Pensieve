"""
pensieve/structurer.py
----------------------
Task 3 — Output JSON Schema Builder

Transforms a Docling ConversionResult + extracted metadata into the
canonical Pensieve document JSON schema.

Schema shape (see README for full field descriptions):
    doc_id, source_filename, company_name, fiscal_year,
    reporting_period_type, num_pages, extraction_metadata,
    text_blocks[], tables[]

Public API
----------
    build_document_json(source_path, result, metadata) -> dict
"""

from __future__ import annotations

import hashlib
import importlib.metadata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pensieve.config import JSON_INDENT  # noqa: F401 (re-exported for callers)
from pensieve.logger import get_logger
from pensieve.risk_flagger import assess_table_risk

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# DocItemLabel → section_hint mapping
# ---------------------------------------------------------------------------

# Import the label enum from docling.  We do this here rather than at
# the top of the module so that import errors surface with a clear message
# rather than at package import time when docling might not yet be installed.
try:
    from docling.datamodel.document import DocItemLabel  # type: ignore[attr-defined]
    _LABEL_TO_HINT: dict[str, str] = {
        DocItemLabel.SECTION_HEADER.value: "heading",
        DocItemLabel.FOOTNOTE.value: "footnote",
        DocItemLabel.TEXT.value: "narrative",
        DocItemLabel.LIST_ITEM.value: "narrative",
        DocItemLabel.CODE.value: "narrative",
        DocItemLabel.FORMULA.value: "narrative",
    }
except (ImportError, AttributeError):
    # Fallback: use raw string values known from Docling v2 schema.
    _LABEL_TO_HINT = {
        "section_header": "heading",
        "footnote": "footnote",
        "text": "narrative",
        "list_item": "narrative",
        "code": "narrative",
        "formula": "narrative",
    }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc_id(source_path: Path) -> str:
    """Return a stable, content-based document ID.

    Uses the first 16 hex characters of the SHA-256 digest of the file
    bytes.  This is deterministic across re-runs: re-ingesting the same
    file produces the same doc_id, which makes Phase 2 re-runs cheap.
    """
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    return digest[:16]


def _docling_version() -> str:
    try:
        return importlib.metadata.version("docling")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _label_to_hint(label_value: str) -> str:
    """Map a Docling DocItemLabel value string to a section_hint."""
    return _LABEL_TO_HINT.get(label_value, "unknown")


def _get_page_no(item) -> int:
    """Safely get the first page number from a document item's provenance."""
    try:
        if item.prov:
            return item.prov[0].page_no
    except (AttributeError, IndexError):
        pass
    return 0


# ---------------------------------------------------------------------------
# Table grid extraction
# ---------------------------------------------------------------------------

def _build_grid(table) -> list[list[str]]:
    """Reconstruct a 2-D grid from a Docling TableItem.

    Docling represents tables as a flat list of cells with
    (start_row_offset_idx, start_col_offset_idx) coordinates.
    We rebuild the rectangular grid manually here to handle merged
    cells gracefully (merged cell text appears at the top-left
    coordinate; other positions remain empty).
    """
    num_rows = table.data.num_rows
    num_cols = table.data.num_cols

    if num_rows == 0 or num_cols == 0:
        return []

    # Initialise with empty strings.
    grid: list[list[str]] = [[""] * num_cols for _ in range(num_rows)]

    for cell in table.data.table_cells:
        r = cell.start_row_offset_idx
        c = cell.start_col_offset_idx
        if 0 <= r < num_rows and 0 <= c < num_cols:
            grid[r][c] = (cell.text or "").strip()

    return grid


# ---------------------------------------------------------------------------
# Caption lookup
# ---------------------------------------------------------------------------

def _find_caption(doc, table_self_ref: str) -> str | None:
    """Find the caption Docling associated with a table, if any.

    Docling attaches captions via the table's captions list (which
    contains references to TextItem/caption items).
    """
    try:
        # Docling ≥2.x: table.captions is a list of RefItem pointing to
        # caption text items in doc.
        from docling.datamodel.document import TableItem  # noqa: F401
    except ImportError:
        return None

    # Walk caption references from the table object.
    # The table is already the object, but we need the doc to resolve refs.
    # We'll just return None if the structure isn't as expected.
    return None  # Will be populated below by the caller which has the table obj


def _extract_caption(doc, table) -> str | None:
    """Extract caption text from a TableItem's captions attribute."""
    try:
        captions = getattr(table, "captions", [])
        if not captions:
            return None
        # Each caption is a RefItem; resolve via doc
        for cap_ref in captions:
            resolved = cap_ref.resolve(doc)
            if resolved and hasattr(resolved, "text"):
                text = resolved.text.strip()
                if text:
                    return text
    except Exception:  # noqa: BLE001
        pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_document_json(
    source_path: Path,
    result,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Build the Pensieve output JSON dict for a single document.

    Parameters
    ----------
    source_path:
        Path to the original source file (used to compute doc_id and
        store source_filename).
    result:
        Docling ConversionResult with a populated .document attribute.
    metadata:
        Dict from extract_document_metadata(), containing:
        company_name, fiscal_year, reporting_period_type, needs_review,
        review_reasons.

    Returns
    -------
    dict — the complete document JSON object ready for json.dumps().
    """
    source_path = Path(source_path)
    doc = result.document

    doc_id = _doc_id(source_path)
    converted_at = datetime.now(tz=timezone.utc).isoformat()
    num_pages = len(doc.pages)

    # Collect any conversion errors from the result.
    conversion_errors: list[str] = []
    if result.errors:
        conversion_errors = [str(e) for e in result.errors]

    log.debug(
        "%s — building JSON: %d pages, %d text items, %d tables",
        source_path.name,
        num_pages,
        len(doc.texts),
        len(doc.tables),
    )

    # -----------------------------------------------------------------------
    # Text blocks
    # -----------------------------------------------------------------------
    text_blocks: list[dict] = []
    for idx, text_item in enumerate(doc.texts):
        label_value = (
            text_item.label.value
            if hasattr(text_item.label, "value")
            else str(text_item.label)
        )
        text_blocks.append(
            {
                "block_id": f"text_{idx:04d}",
                "page": _get_page_no(text_item),
                "text": (text_item.text or "").strip(),
                "section_hint": _label_to_hint(label_value),
            }
        )

    # -----------------------------------------------------------------------
    # Tables
    # -----------------------------------------------------------------------
    tables_out: list[dict] = []
    for idx, table in enumerate(doc.tables):
        num_rows = table.data.num_rows
        num_cols = table.data.num_cols
        grid = _build_grid(table)
        caption = _extract_caption(doc, table)
        risk_flag, risk_reasons = assess_table_risk(grid, num_rows, num_cols)

        tables_out.append(
            {
                "table_id": f"table_{idx:04d}",
                "page": _get_page_no(table),
                "rows": num_rows,
                "cols": num_cols,
                "grid": grid,
                "caption": caption,
                "risk_flag": risk_flag,
                "risk_reasons": risk_reasons,
            }
        )

    tables_flagged = sum(1 for t in tables_out if t["risk_flag"])
    if tables_flagged:
        log.info(
            "%s — %d/%d table(s) risk-flagged.",
            source_path.name,
            tables_flagged,
            len(tables_out),
        )

    # -----------------------------------------------------------------------
    # Assemble final document dict
    # -----------------------------------------------------------------------
    return {
        "doc_id": doc_id,
        "source_filename": source_path.name,
        "company_name": metadata.get("company_name"),
        "fiscal_year": metadata.get("fiscal_year"),
        "reporting_period_type": metadata.get("reporting_period_type", "other"),
        "num_pages": num_pages,
        "extraction_metadata": {
            "docling_version": _docling_version(),
            "converted_at": converted_at,
            "conversion_errors": conversion_errors,
            "needs_review": metadata.get("needs_review", False),
            "review_reasons": metadata.get("review_reasons", []),
        },
        "text_blocks": text_blocks,
        "tables": tables_out,
    }
