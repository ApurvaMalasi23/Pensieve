"""
pensieve/metadata_extractor.py
-------------------------------
Task 2 — Company + Fiscal Year Extraction

Extracts structured metadata (company name, fiscal year, reporting
period type) from the first few pages of a converted document using
an NVIDIA NIM LLM call (via OpenAI SDK) with a constrained JSON-only prompt.

Why LLM rather than regex?
    Cover-page formats vary enormously across annual reports and broker
    notes (date formats, line layouts, font sizes that become whitespace
    in plain text).  A direct LLM call is simpler and more robust than
    trying to cover every format with regex.  The text sent is small
    (capped at COVER_PAGE_MAX_CHARS), so this is cheap per document.

Public API
----------
    extract_document_metadata(result, source_filename) -> dict
        Returns a flat metadata dict ready to be merged into the output
        JSON.  Never raises — failures produce a needs_review=True dict.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pensieve.config import (
    COVER_PAGE_MAX_CHARS,
    COVER_PAGE_MAX_PAGES,
    FISCAL_YEAR_MAX,
    FISCAL_YEAR_MIN,
    LLM_MAX_RETRIES,
    LLM_RETRY_WAIT_BASE,
    METADATA_LLM_BASE_URL,
    METADATA_LLM_MODEL,
)
from pensieve.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# NVIDIA NIM OpenAI client (lazy singleton — avoids import-time key validation)
# ---------------------------------------------------------------------------

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "NVIDIA_API_KEY is not set. "
                "Copy .env.example → .env and add your key."
            )
        _client = openai.OpenAI(
            base_url=METADATA_LLM_BASE_URL,
            api_key=api_key,
        )
    return _client


# ---------------------------------------------------------------------------
# Cover-page text extraction
# ---------------------------------------------------------------------------

def _extract_cover_text(result) -> str:
    """Pull plain text from the first COVER_PAGE_MAX_PAGES pages.

    Filters text items by provenance page number, concatenates them,
    and caps the result at COVER_PAGE_MAX_CHARS so the LLM prompt stays
    small regardless of how verbose the cover pages are.
    """
    doc = result.document
    cover_pages = set(range(1, COVER_PAGE_MAX_PAGES + 1))

    fragments: list[str] = []
    for text_item in doc.texts:
        # prov is a list; an item may appear on multiple pages.
        if any(p.page_no in cover_pages for p in text_item.prov):
            text = text_item.text.strip()
            if text:
                fragments.append(text)

    combined = "\n".join(fragments)
    if len(combined) > COVER_PAGE_MAX_CHARS:
        combined = combined[:COVER_PAGE_MAX_CHARS]
        log.debug("Cover-page text truncated to %d chars.", COVER_PAGE_MAX_CHARS)

    return combined


# ---------------------------------------------------------------------------
# LLM extraction with retry
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a precise financial-document metadata extractor.
Your only job is to read a passage of text from the cover page of an Indian \
company annual report or broker research note and return a single JSON object.

Return ONLY valid JSON — no explanation, no markdown fences, no extra keys.

Required keys:
  "company_name"          : string  — the name of the company being reported on.
                                      If a broker note covers multiple companies,
                                      use the primary subject company.
  "fiscal_year"           : string  — the fiscal year or reporting period, e.g.
                                      "FY2024", "FY2023-24", "Q2 FY2025", "2023".
                                      Prefer the format used in the document itself.
  "reporting_period_type" : string  — exactly one of: "annual", "quarterly", "other".

If you cannot determine a field with reasonable confidence, set it to null.
Do not invent values."""

_USER_PROMPT_TEMPLATE = """\
Extract metadata from the following cover-page text:

---
{cover_text}
---

Return ONLY the JSON object."""


@retry(
    retry=retry_if_exception_type(
        (openai.RateLimitError, openai.APIConnectionError, openai.APIStatusError)
    ),
    stop=stop_after_attempt(LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=LLM_RETRY_WAIT_BASE, min=LLM_RETRY_WAIT_BASE, max=60),
    reraise=True,
)
def _call_llm(cover_text: str) -> str:
    """Call NVIDIA NIM and return raw response text. Retried on 429 and transient errors."""
    client = _get_client()
    response = client.chat.completions.create(
        model=METADATA_LLM_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(cover_text=cover_text)},
        ],
        temperature=0.1,
        max_tokens=256,
    )
    content = response.choices[0].message.content or ""
    return content.strip()


# ---------------------------------------------------------------------------
# Response parsing and validation
# ---------------------------------------------------------------------------

_YEAR_PATTERN = re.compile(r"(?<!\d)(\d{4})(?!\d)")


def _parse_and_validate(raw_response: str, source_filename: str) -> dict[str, Any]:
    """Parse the LLM JSON response and validate key fields.

    Defensively parses output from meta/llama-3.1-70b-instruct:
      - Strips markdown code fences if present.
      - Handles conversational preamble/postamble by extracting the outer JSON object.
      - Wraps json.loads in try/except; if invalid, gracefully marks
        needs_review=True rather than crashing.

    Returns a metadata dict with needs_review set appropriately.
    Never raises — invalid responses return needs_review=True with
    fallback null values.
    """
    needs_review = False
    review_reasons: list[str] = []

    # --- Parse JSON defensively ---
    data: dict[str, Any] = {}
    parse_success = False

    # 1. Strip markdown fences if present
    cleaned = re.sub(r"```(?:json)?|```", "", raw_response).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            data = parsed
            parse_success = True
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. If direct load failed (e.g. conversational preamble/postamble),
    # try extracting the first outermost JSON object {...}
    if not parse_success:
        brace_match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if brace_match:
            try:
                parsed = json.loads(brace_match.group(0))
                if isinstance(parsed, dict):
                    data = parsed
                    parse_success = True
            except (json.JSONDecodeError, ValueError):
                pass

    if not parse_success:
        log.warning(
            "%s — LLM returned non-JSON response: %s …",
            source_filename,
            raw_response[:120],
        )
        return {
            "company_name": None,
            "fiscal_year": None,
            "reporting_period_type": "other",
            "needs_review": True,
            "review_reasons": ["LLM returned non-JSON response"],
        }

    company_name = data.get("company_name") or None
    fiscal_year = data.get("fiscal_year") or None
    period_type = data.get("reporting_period_type") or "other"

    # --- Validate company_name ---
    if not company_name or not str(company_name).strip():
        needs_review = True
        review_reasons.append("company_name is empty or null")
        company_name = None
    else:
        company_name = str(company_name).strip()

    # --- Validate fiscal_year ---
    if not fiscal_year:
        needs_review = True
        review_reasons.append("fiscal_year is empty or null")
        fiscal_year = None
    else:
        fiscal_year = str(fiscal_year).strip()
        year_match = _YEAR_PATTERN.search(fiscal_year)
        if not year_match:
            needs_review = True
            review_reasons.append(
                f"fiscal_year '{fiscal_year}' contains no recognisable 4-digit year"
            )
        else:
            year_int = int(year_match.group(1))
            if not (FISCAL_YEAR_MIN <= year_int <= FISCAL_YEAR_MAX):
                needs_review = True
                review_reasons.append(
                    f"fiscal_year '{fiscal_year}' is outside sane range "
                    f"{FISCAL_YEAR_MIN}–{FISCAL_YEAR_MAX}"
                )

    # --- Validate reporting_period_type ---
    valid_types = {"annual", "quarterly", "other"}
    if period_type not in valid_types:
        log.debug(
            "%s — unexpected reporting_period_type '%s'; defaulting to 'other'.",
            source_filename,
            period_type,
        )
        period_type = "other"

    if needs_review:
        log.warning(
            "%s — metadata needs review: %s",
            source_filename,
            "; ".join(review_reasons),
        )

    return {
        "company_name": company_name,
        "fiscal_year": fiscal_year,
        "reporting_period_type": period_type,
        "needs_review": needs_review,
        "review_reasons": review_reasons,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_document_metadata(result, source_filename: str) -> dict[str, Any]:
    """Extract company name, fiscal year, and period type from a ConversionResult.

    Sends the first-page text to the LLM (NVIDIA NIM) and validates the response.
    On any error, returns a safe fallback dict with needs_review=True.

    Parameters
    ----------
    result:
        Docling ConversionResult with a populated .document attribute.
    source_filename:
        Original filename string, used in log messages and review flags.

    Returns
    -------
    dict with keys:
        company_name, fiscal_year, reporting_period_type,
        needs_review (bool), review_reasons (list[str])
    """
    try:
        cover_text = _extract_cover_text(result)
    except Exception as exc:  # noqa: BLE001
        log.error("%s — failed to extract cover-page text: %s", source_filename, exc)
        return {
            "company_name": None,
            "fiscal_year": None,
            "reporting_period_type": "other",
            "needs_review": True,
            "review_reasons": [f"Cover-page text extraction error: {exc}"],
        }

    if not cover_text.strip():
        log.warning(
            "%s — cover-page text is empty; this may be a scanned or image-only document.",
            source_filename,
        )
        return {
            "company_name": None,
            "fiscal_year": None,
            "reporting_period_type": "other",
            "needs_review": True,
            "review_reasons": ["Cover-page text is empty — possible scan with no OCR output"],
        }

    log.debug(
        "%s — sending %d chars of cover-page text to %s …",
        source_filename,
        len(cover_text),
        METADATA_LLM_MODEL,
    )

    try:
        raw_response = _call_llm(cover_text)
    except Exception as exc:  # noqa: BLE001
        log.error(
            "%s — LLM call failed after %d retries: %s",
            source_filename,
            LLM_MAX_RETRIES,
            exc,
        )
        return {
            "company_name": None,
            "fiscal_year": None,
            "reporting_period_type": "other",
            "needs_review": True,
            "review_reasons": [f"LLM API error: {exc}"],
        }

    metadata = _parse_and_validate(raw_response, source_filename)

    log.info(
        "%s → company='%s'  fiscal_year='%s'  period='%s'  needs_review=%s",
        source_filename,
        metadata.get("company_name"),
        metadata.get("fiscal_year"),
        metadata.get("reporting_period_type"),
        metadata.get("needs_review"),
    )

    return metadata
