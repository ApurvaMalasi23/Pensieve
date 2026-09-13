"""
pensieve/classifier.py
----------------------
Phase 4 — Query Intent Classification (Narrative vs. Numeric)

Classifies a user query as either "narrative" (answered from text passages)
or "numeric" (requires a table lookup and numeric verification).

Design principles:
- Uses a lightweight LLM call, not a keyword list.  Keyword lists miss phrasing
  like "how did the bank's deposit base change" which is clearly numeric intent.
- Biased toward "numeric" when ambiguous: misclassifying narrative-as-numeric is
  a safer failure than the reverse.  The numeric path's verification machinery
  is strictly more rigorous; a financial question is more useful answered with
  verified figures than a vague narrative summary.
- Every classification is logged (query + result) for empirical spot-checking.
- On any LLM failure, defaults to "numeric" (fail toward rigour).

Public API
----------
    classify_intent(query: str, client=None) -> Literal["narrative", "numeric"]
"""

from __future__ import annotations

import os
from typing import Literal

from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from pensieve.config import (
    CLASSIFICATION_LLM_MODEL,
    GENERATION_LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_RETRY_WAIT_BASE,
)
from pensieve.logger import get_logger

log = get_logger(__name__)

_CLASSIFICATION_SYSTEM_PROMPT = (
    "You are a query classifier for a financial-document search system.\n"
    "Classify the following user query as either 'narrative' or 'numeric'.\n\n"
    "'narrative': The query asks for qualitative information — descriptions, "
    "explanations, strategies, risks, business activities, management discussion, "
    "governance, or any other non-numerical content.\n\n"
    "'numeric': The query asks for a specific number, figure, amount, percentage, "
    "ratio, change, growth, metric, or any other quantitative information — "
    "even if the query doesn't contain an explicit number or formula.\n\n"
    "When in doubt, classify as 'numeric' — it is better to apply the numeric "
    "verification path unnecessarily than to miss a numeric query.\n\n"
    "Reply with EXACTLY ONE WORD — either 'narrative' or 'numeric'. "
    "No explanation, no punctuation, no other words."
)


def _get_classification_client() -> OpenAI:
    """Return an OpenAI client pointed at the NVIDIA NIM endpoint."""
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        log.warning("NVIDIA_API_KEY is not set — classification will fail.")
    return OpenAI(
        base_url=GENERATION_LLM_BASE_URL,
        api_key=api_key or "missing-key",
        timeout=30.0,
    )


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=LLM_RETRY_WAIT_BASE, min=2, max=10),
    reraise=True,
)
def _call_classifier(client: OpenAI, model: str, query: str) -> str:
    """Call the classification LLM and return its raw response string."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Query: {query}\nIntent:"},
        ],
        max_tokens=5,        # Only a single word needed
        temperature=0.0,     # Deterministic classification
    )
    content = response.choices[0].message.content
    return content.strip().lower() if content else ""


def classify_intent(
    query: str,
    client: OpenAI | None = None,
    model: str | None = None,
) -> Literal["narrative", "numeric"]:
    """Classify a user query as either 'narrative' or 'numeric' intent.

    Parameters
    ----------
    query:
        The user's natural-language question.
    client:
        Optional OpenAI client instance (for testing/mocking).
    model:
        LLM model identifier. Defaults to CLASSIFICATION_LLM_MODEL config constant.

    Returns
    -------
    "narrative" or "numeric".  Defaults to "numeric" on any error or ambiguity,
    per the design principle of biasing toward the more rigorous path.
    """
    clean_query = query.strip()
    if not clean_query:
        log.warning("classify_intent called with empty query — defaulting to 'numeric'.")
        return "numeric"

    target_model = model or CLASSIFICATION_LLM_MODEL
    llm_client = client or _get_classification_client()

    try:
        raw = _call_classifier(llm_client, target_model, clean_query)
        # Normalise — accept "narrative" exactly; everything else is "numeric".
        if raw.startswith("narrative"):
            result: Literal["narrative", "numeric"] = "narrative"
        else:
            result = "numeric"
    except Exception:
        log.exception(
            "classify_intent: LLM call failed for query %r — defaulting to 'numeric'", clean_query
        )
        result = "numeric"

    # Always log for empirical spot-checking (per spec requirement)
    log.info("classify_intent: %r -> %s", clean_query, result)
    return result

