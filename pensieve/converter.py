"""
pensieve/converter.py
---------------------
Task 1 — Document Conversion

Wraps Docling's DocumentConverter with the standard PDF pipeline
(OCR on, TableFormer on, no VLM).  A single converter instance is
created at module level so the model weights are loaded only once per
process — reloading them for every document would be very slow.

Public API
----------
    get_converter() -> DocumentConverter
        Return the shared converter instance (lazy-initialised).

    convert_document(source_path) -> ConversionResult | None
        Convert a single document.  Returns None on failure so batch
        runs can skip bad files without crashing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import ConversionStatus, InputFormat

from pensieve.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Converter initialisation (lazy singleton)
# ---------------------------------------------------------------------------

_converter: Optional[DocumentConverter] = None


def get_converter() -> DocumentConverter:
    """Return the shared DocumentConverter, creating it on first call.

    Uses the standard PDF pipeline with:
    - OCR enabled  (do_ocr=True is the Docling default; we keep it
      explicit so the intent is clear in code review)
    - TableFormer table-structure model enabled
    - No VLM / GraniteDocling pipeline — rejected in Phase 0 validation
    """
    global _converter
    if _converter is not None:
        return _converter

    log.info("Initialising Docling DocumentConverter (OCR=on, TableFormer=on) …")

    from docling.datamodel.pipeline_options import AcceleratorOptions
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,               # Keep on: target set includes scanned filings
        do_table_structure=True,   # Enable TableFormer
        accelerator_options=AcceleratorOptions(num_threads=8),
    )

    _converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )

    log.info("DocumentConverter ready.")
    return _converter


# ---------------------------------------------------------------------------
# Public conversion function
# ---------------------------------------------------------------------------

def convert_document(source_path: Path):
    """Convert a document file and return the ConversionResult.

    On failure, logs the error and returns None so the caller (batch
    runner) can skip this document and continue processing others.

    Parameters
    ----------
    source_path:
        Path to the input document (PDF for this phase).

    Returns
    -------
    ConversionResult | None
        The result object on success, None on any conversion failure.
    """
    source_path = Path(source_path)

    if not source_path.exists():
        log.error("File not found: %s", source_path)
        return None

    log.info("Converting: %s", source_path.name)

    try:
        converter = get_converter()
        # raises_on_error=False: capture errors in result.errors rather
        # than propagating an exception — lets the batch runner decide
        # what to do rather than dying here.
        result = converter.convert(str(source_path), raises_on_error=False)
    except Exception as exc:  # noqa: BLE001
        log.error(
            "Unexpected exception converting %s: %s",
            source_path.name,
            exc,
            exc_info=True,
        )
        return None

    if result.status == ConversionStatus.FAILURE:
        errors = "; ".join(str(e) for e in result.errors) if result.errors else "unknown"
        log.error(
            "Conversion failed for %s — errors: %s",
            source_path.name,
            errors,
        )
        return None

    if result.status == ConversionStatus.PARTIAL_SUCCESS:
        # Partial success: some pages may have failed (e.g. encrypted
        # pages, corrupted image regions).  Log a warning but continue —
        # we'd rather have partial data with a visible warning than
        # silently skip the whole document.
        errors = "; ".join(str(e) for e in result.errors) if result.errors else ""
        log.warning(
            "Partial conversion for %s — some pages may be missing. Errors: %s",
            source_path.name,
            errors,
        )

    page_count = len(result.document.pages) if result.document else 0
    log.info(
        "Converted %s → %d page(s), status=%s",
        source_path.name,
        page_count,
        result.status.name,
    )

    return result
