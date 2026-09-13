"""
scripts/test_comparison_rag.py
------------------------------
Live end-to-end verification script for Phase 5: Multi-Document Comparison.

Queries the live system with real documents in Qdrant (Republic Bancorp & LUX INDUSTRIES LIMITED)
and calls NVIDIA NIM LLM for live verification, delta computation, and synthesis.
"""

import json
import sys
from dotenv import load_dotenv

load_dotenv()

from pensieve.api import app
from pensieve.comparator import extract_comparison_entities, detect_comparison_intent, execute_comparison
from fastapi.testclient import TestClient

client = TestClient(app)

SEPARATOR = "=" * 70

def test_query(title: str, query: str):
    print(f"\n{SEPARATOR}")
    print(f"TEST: {title}")
    print(f"Query: {query}")
    print(SEPARATOR)

    response = client.post("/ask", json={"query": query})
    if response.status_code != 200:
        print(f"[FAIL] HTTP {response.status_code}: {response.text}")
        return False

    data = response.json()
    print(f"Comparison Mode   : {data.get('comparison')}")
    print(f"Intent            : {data.get('intent')}")
    print(f"Verification Status: {data.get('verification', {}).get('status')}")
    print(f"Verification Reason: {data.get('verification', {}).get('reason')}")

    if data.get('entities_compared'):
        print("\nEntities Compared:")
        for e in data['entities_compared']:
            print(f"  - Company: {e.get('company_name')}, FY: {e.get('fiscal_year')}")

    if data.get('deltas'):
        d = data['deltas']
        print("\nProgrammatic Deltas:")
        print(f"  - Entity A: {d['entity_a']['entity'].get('company_name')} = {d['entity_a']['raw_value']}")
        print(f"  - Entity B: {d['entity_b']['entity'].get('company_name')} = {d['entity_b']['raw_value']}")
        print(f"  - Absolute Delta  : {d['absolute_delta']}")
        print(f"  - Percentage Delta: {d['percentage_delta']}%")
        print(f"  - Direction       : {d['direction']}")

    print("\nAnswer / Synthesis:")
    print(data.get('answer', '')[:500] + ("..." if len(data.get('answer', '')) > 500 else ""))

    print(f"\nCitations ({len(data.get('citations', []))}):")
    for cit in data.get('citations', [])[:3]:
        comp = cit.get('company_name') or 'N/A'
        fy = cit.get('fiscal_year') or 'N/A'
        p_start = cit.get('page_start')
        p_end = cit.get('page_end')
        tbl = cit.get('table_id') or 'narrative'
        flag = f"[RISK FLAGGED]" if cit.get('risk_flag') else "[CLEAN]"
        print(f"  {cit.get('marker')} {comp} (FY {fy}, pg {p_start}-{p_end}, {tbl}) {flag}")

    print(f"[PASS] Successfully completed query.")
    return True

def main():
    print("=== PENSIEVE PHASE 5 LIVE VERIFICATION ===")
    
    # Test 1: Cross-document narrative comparison
    t1 = test_query(
        "Cross-Company Narrative Comparison",
        "Compare the business activities of Republic Bancorp and Lux Industries"
    )

    # Test 2: Cross-document numeric comparison
    t2 = test_query(
        "Cross-Company Numeric Comparison",
        "Compare total revenue or income of Republic Bancorp in 2024 and Lux Industries in 2025-26"
    )

    # Test 3: Partial / Missing Entity Coverage
    t3 = test_query(
        "Partial Coverage (One In-Corpus, One Missing)",
        "Compare the revenue of Republic Bancorp and Apple in 2024"
    )

    # Test 4: Single-Document Regression Check
    t4 = test_query(
        "Single-Document Non-Comparison Path",
        "What were total deposits of Republic Bancorp as of December 31, 2024?"
    )

    print(f"\n{SEPARATOR}")
    print("SUMMARY OF PHASE 5 LIVE TESTS:")
    print(f"  1. Narrative Comparison : {'[PASS]' if t1 else '[FAIL]'}")
    print(f"  2. Numeric Comparison   : {'[PASS]' if t2 else '[FAIL]'}")
    print(f"  3. Partial Coverage     : {'[PASS]' if t3 else '[FAIL]'}")
    print(f"  4. Single-Doc Path      : {'[PASS]' if t4 else '[FAIL]'}")
    print(SEPARATOR)

if __name__ == "__main__":
    main()
