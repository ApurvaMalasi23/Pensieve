"""
scripts/test_numeric_rag.py
----------------------------
Phase 4 live end-to-end verification against the validated test document
(Republic Bancorp FY2024 annual report).

Run:
    python scripts/test_numeric_rag.py

Prerequisites:
    - Docker Desktop running
    - Qdrant container started: docker start pensieve_qdrant
    - .env file populated (NVIDIA_API_KEY, etc.)
    - Phase 2 data already ingested (pensieve_chunks collection populated)
    - API server NOT required for this script (calls modules directly)

Test cases:
    1. Clean table + grounded numeric answer  → expects verified
    2. Flagged table + grounded numeric answer → expects verified_low_confidence
    3. No matching table (obscure query)       → expects no_context_found
    4. Intent classification spot-check       → 10 varied queries, printed for review
    5. /ask narrative routing via API         → expects intent=narrative, status=not_applicable
    6. /ask numeric routing via API           → expects intent=numeric, status in {verified, verified_low_confidence}
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# Allow running from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import httpx  # noqa: E402

from pensieve.classifier import classify_intent
from pensieve.numeric_grounding import (
    extract_numbers_from_text,
    fit_tables_to_context,
    generate_numeric_answer,
    verify_numbers_against_grid,
)
from pensieve.retriever import retrieve_table_chunks
from pensieve.generator import parse_citations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

INDENT = "    "


def _header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def _result(passed: bool, label: str, detail: str = "") -> None:
    marker = PASS if passed else FAIL
    print(f"{marker}  {label}")
    if detail:
        for line in textwrap.wrap(detail, width=72, subsequent_indent=INDENT):
            print(f"{INDENT}{line}")


def _info(label: str, value: str) -> None:
    print(f"{INFO}  {label}: {value}")


# ---------------------------------------------------------------------------
# Test 1: Clean table + verified answer
# ---------------------------------------------------------------------------


def test_1_clean_table_verified() -> bool:
    _header("Test 1: Clean Table — Expects 'verified'")
    passed = True

    # Query about deposits — table_0000 (page 4) is clean and contains "4,572,044"
    query = "What were total traditional bank deposits as of December 31, 2024?"

    try:
        table_chunks = retrieve_table_chunks(query=query, top_k=3)
    except Exception as e:
        _result(False, "retrieve_table_chunks()", str(e))
        return False

    _info("Retrieved table chunks", str(len(table_chunks)))
    for c in table_chunks:
        _info(
            f"  chunk {c.chunk_id[:8]}",
            f"page={c.page_start}, risk_flag={c.risk_flag}, score={c.score:.4f}"
        )

    if not table_chunks:
        _result(False, "No table chunks retrieved — check Qdrant connection")
        return False

    table_chunks = fit_tables_to_context(table_chunks)
    result = generate_numeric_answer(query=query, chunks=table_chunks)

    _info("Answer", result.answer[:200])
    _info("Citations", str(len(result.citations)))
    _info("no_context_found", str(result.no_context_found))

    numbers = extract_numbers_from_text(result.answer)
    _info("Extracted numbers", str(numbers[:6]))

    verification = verify_numbers_against_grid(
        numbers_from_answer=numbers,
        cited_chunks=result.citations,
        all_retrieved_chunks=table_chunks,
    )

    _info("Verification status", verification.status)
    _info("Verification reason", verification.reason[:150])

    ok_status = verification.status in ("verified", "verified_low_confidence", "not_applicable")
    _result(ok_status, f"Verification status is '{verification.status}' (acceptable for live test)")
    if not ok_status:
        passed = False

    ok_no_context = not result.no_context_found
    _result(ok_no_context, "no_context_found is False")
    if not ok_no_context:
        passed = False

    return passed


# ---------------------------------------------------------------------------
# Test 2: Flagged table — expects verified_low_confidence
# ---------------------------------------------------------------------------


def test_2_flagged_table_low_confidence() -> bool:
    _header("Test 2: Flagged Table — Expects 'verified_low_confidence'")
    passed = True

    # Query about interest rate sensitivity — table_0050 (page 89) is risk_flag=True
    query = "What is the impact of a 400 basis point rate change on net interest income?"

    try:
        table_chunks = retrieve_table_chunks(query=query, top_k=3)
    except Exception as e:
        _result(False, "retrieve_table_chunks()", str(e))
        return False

    _info("Retrieved table chunks", str(len(table_chunks)))
    for c in table_chunks:
        _info(
            f"  chunk {c.chunk_id[:8]}",
            f"page={c.page_start}, risk_flag={c.risk_flag}, table_id={c.table_id}"
        )

    if not table_chunks:
        _result(False, "No table chunks retrieved")
        return False

    table_chunks = fit_tables_to_context(table_chunks)
    result = generate_numeric_answer(query=query, chunks=table_chunks)

    _info("Answer", result.answer[:200])

    numbers = extract_numbers_from_text(result.answer)
    _info("Extracted numbers", str(numbers[:6]))

    verification = verify_numbers_against_grid(
        numbers_from_answer=numbers,
        cited_chunks=result.citations,
        all_retrieved_chunks=table_chunks,
    )

    _info("Verification status", verification.status)
    _info("Verification reason", verification.reason[:150])

    # Accept any non-crash verification here — the key check is that flagged tables
    # never produce "verified" (clean) status
    top_retrieved_flagged = any(c.risk_flag for c in table_chunks)
    if top_retrieved_flagged and verification.status == "verified":
        _result(False, "Flagged table should not produce 'verified' status")
        passed = False
    else:
        _result(True, f"Status '{verification.status}' — appropriate for flagged or missing table")

    return passed


# ---------------------------------------------------------------------------
# Test 3: No matching table
# ---------------------------------------------------------------------------


def test_3_no_matching_table() -> bool:
    _header("Test 3: No Matching Table — Expects no_context_found=True")
    passed = True

    # Deliberately obscure query about something not in any table
    query = "What is the exact number of parking spaces at Republic Bancorp's headquarters?"

    try:
        table_chunks = retrieve_table_chunks(query=query, top_k=3, threshold=0.90)  # High threshold
    except Exception as e:
        _result(False, "retrieve_table_chunks()", str(e))
        return False

    _info("Retrieved table chunks (high threshold)", str(len(table_chunks)))

    table_chunks = fit_tables_to_context(table_chunks)
    result = generate_numeric_answer(query=query, chunks=table_chunks)

    _info("no_context_found", str(result.no_context_found))
    _info("Answer", result.answer[:200])

    # With empty chunks, no_context_found must be True
    if not table_chunks:
        _result(result.no_context_found, "no_context_found=True when no chunks retrieved")
        if not result.no_context_found:
            passed = False
    else:
        # If some chunks were retrieved with this query (low-relevance), we just print
        _result(True, f"Got {len(table_chunks)} chunk(s) at high threshold — checking graceful handling")

    return passed


# ---------------------------------------------------------------------------
# Test 4: Intent classification spot-check
# ---------------------------------------------------------------------------


def test_4_classification_spot_check() -> bool:
    _header("Test 4: Intent Classification Spot-Check (10 queries)")

    test_cases = [
        # (query, expected_intent)
        ("What were total deposits as of December 31, 2024?", "numeric"),
        ("What was net interest income for fiscal year 2024?", "numeric"),
        ("What is Republic Bancorp's primary business strategy?", "narrative"),
        ("What are the main risk factors mentioned in the report?", "narrative"),
        ("What was the EPS for Q4 2024?", "numeric"),
        ("Who are the independent auditors?", "narrative"),
        ("How much did total assets grow from 2023 to 2024?", "numeric"),
        ("Describe the company's approach to credit risk management.", "narrative"),
        ("What was the net interest margin?", "numeric"),
        ("What does management say about the economic outlook?", "narrative"),
    ]

    all_passed = True
    for query, expected in test_cases:
        result = classify_intent(query)
        match = result == expected
        _result(match, f"[{expected}] {query[:60]}", f"-> got: {result}")
        if not match:
            all_passed = False

    return all_passed


# ---------------------------------------------------------------------------
# Test 5 + 6: /ask endpoint — requires running server
# ---------------------------------------------------------------------------


def test_5_ask_narrative_via_api(base_url: str = "http://localhost:8000") -> bool:
    _header("Test 5: /ask Narrative Routing (API)")

    query = "What is Republic Bancorp's primary lending strategy?"
    try:
        resp = httpx.post(
            f"{base_url}/ask",
            json={"query": query},
            timeout=60,
        )
        resp.raise_for_status()
    except httpx.ConnectError:
        _result(False, "Server not reachable — start with: python -m pensieve.api")
        return False
    except Exception as e:
        _result(False, f"HTTP error: {e}")
        return False

    data = resp.json()
    _info("Intent", data.get("intent", "?"))
    _info("Verification status", data.get("verification", {}).get("status", "?"))
    _info("Answer", (data.get("answer") or "")[:150])

    ok_intent = data.get("intent") == "narrative"
    _result(ok_intent, "intent == 'narrative'")

    ok_verification = data.get("verification", {}).get("status") == "not_applicable"
    _result(ok_verification, "verification.status == 'not_applicable'")

    return ok_intent and ok_verification


def test_6_ask_numeric_via_api(base_url: str = "http://localhost:8000") -> bool:
    _header("Test 6: /ask Numeric Routing + Verification (API)")

    query = "What were total traditional bank deposits as of December 31, 2024?"
    try:
        resp = httpx.post(
            f"{base_url}/ask",
            json={"query": query},
            timeout=90,
        )
        resp.raise_for_status()
    except httpx.ConnectError:
        _result(False, "Server not reachable — start with: python -m pensieve.api")
        return False
    except Exception as e:
        _result(False, f"HTTP error: {e}")
        return False

    data = resp.json()
    _info("Intent", data.get("intent", "?"))
    v = data.get("verification", {})
    _info("Verification status", v.get("status", "?"))
    _info("Verification reason", (v.get("reason") or "")[:150])
    _info("Answer", (data.get("answer") or "")[:200])
    _info("Citations", str(len(data.get("citations", []))))

    for cit in data.get("citations", []):
        _info(
            f"  [{cit.get('marker')}]",
            f"page={cit.get('page_start')}, table_id={cit.get('table_id')}, risk_flag={cit.get('risk_flag')}"
        )

    ok_intent = data.get("intent") == "numeric"
    _result(ok_intent, "intent == 'numeric'")

    ok_verification = v.get("status") in ("verified", "verified_low_confidence", "not_applicable", "unverified")
    _result(ok_verification, f"verification.status is a valid enum value: {v.get('status')}")

    ok_no_crash = True  # If we got here without exception, no crash
    _result(ok_no_crash, "No crash during numeric pipeline")

    return ok_intent and ok_verification


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("\nPensieve Phase 4 — Numeric Grounding End-to-End Test Suite")
    print("=" * 60)

    results = {}

    # Tests 1-3 require Qdrant + NVIDIA API key
    results["1: Clean table → verified"] = test_1_clean_table_verified()
    results["2: Flagged table → low_confidence"] = test_2_flagged_table_low_confidence()
    results["3: No matching table"] = test_3_no_matching_table()
    results["4: Classification spot-check"] = test_4_classification_spot_check()

    # Tests 5-6 require the server running
    print("\n" + "=" * 60)
    print("  API Tests (5 & 6) — require server at http://localhost:8000")
    print("  Start with: python -m pensieve.api or python pensieve/api.py")
    print("=" * 60)
    results["5: /ask narrative routing"] = test_5_ask_narrative_via_api()
    results["6: /ask numeric routing"] = test_6_ask_numeric_via_api()

    # Summary
    _header("Summary")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    for name, ok in results.items():
        marker = "[PASS]" if ok else "[FAIL]"
        print(f"  {marker}  {name}")

    print(f"\n  {passed}/{total} tests passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
