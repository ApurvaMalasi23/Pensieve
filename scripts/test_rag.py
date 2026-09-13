"""
scripts/test_rag.py
-------------------
Phase 3 — Manual Verification Script for RAG with Citations

Executes the 4 required test cases against live Qdrant + NVIDIA NIM:
    1. Direct narrative question (answerable)
    2. Scoped question using company_name & fiscal_year filters
    3. Unanswerable / out-of-corpus question (confirms no_context_found triggers)
    4. Citation spot-check (validates cited page/company matches real chunk metadata)

Usage
-----
    python scripts/test_rag.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from pensieve.config import QDRANT_COLLECTION, GENERATION_LLM_MODEL
from pensieve.generator import generate_answer
from pensieve.logger import get_logger
from pensieve.retriever import retrieve_narrative_chunks
from pensieve.vector_store import get_client

log = get_logger("test_rag")

_DIVIDER = "=" * 80
_SUBDIVIDER = "-" * 80


def print_result(title: str, query: str, res, chunks):
    print("\n" + _DIVIDER)
    print(f"  {title}")
    print(_DIVIDER)
    print(f"Query: {query}")
    print(f"Retrieved narrative chunks: {len(chunks)}")
    for i, c in enumerate(chunks, start=1):
        print(f"  Passage [{i}]: doc_id={c.doc_id[:8]}.. page={c.page_start}-{c.page_end} score={c.score:.4f} company={c.company_name} FY={c.fiscal_year}")
    print(_SUBDIVIDER)
    print("Generated Answer:")
    print(res.answer)
    print(_SUBDIVIDER)
    print(f"no_context_found: {res.no_context_found}")
    print(f"Programmatically mapped citations: {len(res.citations)}")
    for cit in res.citations:
        print(f"  * Marker: {cit['marker']}")
        print(f"    Company: {cit['company_name']}, FY: {cit['fiscal_year']}")
        print(f"    Page Range: {cit['page_start']} - {cit['page_end']}")
        print(f"    Source File: {cit['source_filename']}")
        print(f"    Excerpt: {cit['excerpt'][:120]}...")


def main():
    print("\n" + "#" * 80)
    print(f"# Starting Phase 3 RAG Verification (Collection: '{QDRANT_COLLECTION}', Model: '{GENERATION_LLM_MODEL}')")
    print("#" * 80)

    # 0. Health check
    client = get_client()
    info = client.get_collection(QDRANT_COLLECTION)
    print(f"Qdrant status: OK ({info.points_count} points in collection '{QDRANT_COLLECTION}')\n")

    # -----------------------------------------------------------------------
    # Test 1: Direct narrative question (answerable)
    # -----------------------------------------------------------------------
    q1 = "What are Republic Bancorp's primary business activities and services?"
    chunks1 = retrieve_narrative_chunks(query=q1, top_k=5)
    res1 = generate_answer(query=q1, chunks=chunks1)
    print_result("TEST 1: Direct Narrative Question (Answerable)", q1, res1, chunks1)
    assert not res1.no_context_found, "Test 1 failed: Expected grounded answer, got no_context_found=True"
    assert len(res1.citations) > 0, "Test 1 failed: Expected at least 1 citation"
    print("\n>>> TEST 1 PASSED: Grounded answer with valid citations generated.")

    # -----------------------------------------------------------------------
    # Test 2: Scoped question with company and fiscal_year filters
    # -----------------------------------------------------------------------
    q2 = "What are the company's key markets and retail banking footprint?"
    company = "Republic Bancorp"
    year = "2024"
    chunks2 = retrieve_narrative_chunks(query=q2, top_k=5, company_name=company, fiscal_year=year)
    res2 = generate_answer(query=q2, chunks=chunks2)
    print_result("TEST 2: Filtered Question (Scoped to Republic Bancorp FY2024)", q2, res2, chunks2)
    assert not res2.no_context_found, "Test 2 failed: Expected answer for filtered query"
    for c in chunks2:
        assert c.company_name == company, f"Filter breach: {c.company_name} != {company}"
        assert str(c.fiscal_year) == year, f"Filter breach: {c.fiscal_year} != {year}"
    print("\n>>> TEST 2 PASSED: Filters strictly respected across all retrieved chunks.")

    # -----------------------------------------------------------------------
    # Test 3: Unanswerable question (confirms no_context_found path)
    # -----------------------------------------------------------------------
    q3 = "What are Republic Bancorp's manufacturing operations and supply chains for electric vehicles in Japan?"
    chunks3 = retrieve_narrative_chunks(query=q3, top_k=5, threshold=0.50)
    res3 = generate_answer(query=q3, chunks=chunks3)
    print_result("TEST 3: Unanswerable Question (Refusal / No-Context Verification)", q3, res3, chunks3)
    assert res3.no_context_found, "Test 3 failed: Expected no_context_found=True for out-of-corpus query"
    print("\n>>> TEST 3 PASSED: System safely refused without hallucination.")

    # -----------------------------------------------------------------------
    # Test 4: Citation Spot-Check
    # -----------------------------------------------------------------------
    print("\n" + _DIVIDER)
    print("  TEST 4: Citation Spot-Check Validation")
    print(_DIVIDER)
    print("Verifying Test 1's citations against actual chunk metadata...")
    for cit in res1.citations:
        marker = cit["marker"]
        idx = int(marker.strip("[]"))
        corresponding_chunk = chunks1[idx - 1]

        print(f"\nChecking Citation Marker {marker}:")
        print(f"  Reported company : {cit['company_name']} == {corresponding_chunk.company_name}")
        print(f"  Reported FY      : {cit['fiscal_year']} == {corresponding_chunk.fiscal_year}")
        print(f"  Reported pages   : {cit['page_start']}-{cit['page_end']} == {corresponding_chunk.page_start}-{corresponding_chunk.page_end}")
        print(f"  Reported doc_id  : {cit['doc_id']} == {corresponding_chunk.doc_id}")

        assert cit["company_name"] == corresponding_chunk.company_name
        assert cit["fiscal_year"] == corresponding_chunk.fiscal_year
        assert cit["page_start"] == corresponding_chunk.page_start
        assert cit["page_end"] == corresponding_chunk.page_end
        assert cit["doc_id"] == corresponding_chunk.doc_id

    print("\n>>> TEST 4 PASSED: All citations trace 100% accurately to real chunk metadata.")
    print("\n" + "=" * 80)
    print("  ALL 4 PHASE 3 VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
