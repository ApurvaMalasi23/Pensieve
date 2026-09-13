"""
scripts/smoke_test_retrieval.py
--------------------------------
Phase 2 — Smoke-Test Retrieval Script

Runs two sanity queries against the populated Qdrant collection to verify
that ingestion actually produced queryable results:

    1. Plain vector search for "net interest income" — top 5 results
    2. Filtered vector search with company_name + section_type="table" — top 5

This is NOT Phase 3 retrieval logic — it's a minimal proof-of-concept that:
    a) chunks were ingested successfully
    b) payload indexes are working (metadata filter doesn't scan all points)
    c) risk_flag survives correctly into table chunk payloads

Usage
-----
    python scripts/smoke_test_retrieval.py
    python scripts/smoke_test_retrieval.py --collection pensieve_chunks
    python scripts/smoke_test_retrieval.py --company "Republic Bancorp"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from pensieve.config import QDRANT_COLLECTION, EMBEDDING_PROVIDER
from pensieve.embedder import embed_texts, get_vector_dim
from pensieve.vector_store import get_client
from pensieve.logger import get_logger

log = get_logger("smoke_test")

_DIVIDER = "-" * 72


def _format_result(rank: int, hit) -> str:
    p = hit.payload or {}
    lines = [
        f"  #{rank}  score={hit.score:.4f}",
        f"      chunk_id      : {p.get('chunk_id', '?')}",
        f"      section_type  : {p.get('section_type', '?')}",
        f"      company       : {p.get('company_name', '?')}",
        f"      fiscal_year   : {p.get('fiscal_year', '?')}",
        f"      page_start    : {p.get('page_start', '?')}",
    ]
    if p.get("section_type") == "table":
        lines.append(f"      table_id      : {p.get('table_id', '?')}")
        lines.append(f"      risk_flag     : {p.get('risk_flag', '?')}")
        reasons = p.get("risk_reasons", [])
        if reasons:
            lines.append(f"      risk_reasons  : {reasons[0][:60]}...")
        lines.append(f"      rows x cols   : {p.get('rows')} x {p.get('cols')}")
        lines.append(f"      truncated     : {p.get('truncated_for_embedding', False)}")
    # Preview first 120 chars of text.
    text_preview = (p.get("text") or "")[:120].replace("\n", " ")
    lines.append(f"      text preview  : {text_preview!r}")
    return "\n".join(lines)


def run_smoke_test(
    query: str = "net interest income",
    company_name: str | None = None,
    collection: str = QDRANT_COLLECTION,
    provider: str = EMBEDDING_PROVIDER,
    top_k: int = 5,
) -> None:
    client = get_client()

    # Verify collection exists.
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        print(f"\n[ERROR] Collection '{collection}' does not exist in Qdrant.")
        print("  Run the embed runner first:")
        print(f"    python -m pensieve.embed_runner --json-dir ./output")
        sys.exit(1)

    info = client.get_collection(collection_name=collection)
    point_count = info.points_count
    print(f"\nCollection '{collection}' — {point_count:,} point(s) total.")

    # Embed the query string.
    print(f"\nEmbedding query: {query!r}  (provider={provider})")
    [query_vector] = embed_texts([query], provider=provider)

    # -----------------------------------------------------------------------
    # Query 1: Plain vector search
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print(f"  QUERY 1 — Plain vector search  (top {top_k})")
    print(f"  Query: {query!r}")
    print("=" * 72)

    hits = client.query_points(
        collection_name=collection,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    ).points
    if not hits:
        print("  [WARNING] No results returned — collection may be empty.")
    for i, hit in enumerate(hits, start=1):
        print(_format_result(i, hit))
        print(_DIVIDER)

    # -----------------------------------------------------------------------
    # Query 2: Filtered vector search — tables only for a specific company
    # -----------------------------------------------------------------------
    from qdrant_client.http import models as qmodels

    # Determine filter company: use provided arg or detect from first result.
    filter_company = company_name
    if not filter_company and hits:
        filter_company = (hits[0].payload or {}).get("company_name")

    print("\n" + "=" * 72)
    print(f"  QUERY 2 — Filtered vector search  (top {top_k})")
    print(f"  Query : {query!r}")
    print(f"  Filter: company_name='{filter_company}'  AND  section_type='table'")
    print("=" * 72)

    conditions = [
        qmodels.FieldCondition(
            key="section_type",
            match=qmodels.MatchValue(value="table"),
        ),
    ]
    if filter_company:
        conditions.append(
            qmodels.FieldCondition(
                key="company_name",
                match=qmodels.MatchValue(value=filter_company),
            )
        )

    filtered_hits = client.query_points(
        collection_name=collection,
        query=query_vector,
        query_filter=qmodels.Filter(must=conditions),
        limit=top_k,
        with_payload=True,
    ).points
    if not filtered_hits:
        print("  [WARNING] No results returned for this filter.")
        print("  (Check that company_name is indexed and matches exactly.)")
    for i, hit in enumerate(filtered_hits, start=1):
        print(_format_result(i, hit))
        print(_DIVIDER)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    flagged_in_results = sum(
        1 for h in filtered_hits if (h.payload or {}).get("risk_flag") is True
    )
    print(f"\nSmoke test complete.")
    print(f"  Query 1 returned : {len(hits)} result(s)")
    print(f"  Query 2 returned : {len(filtered_hits)} table result(s)  ({flagged_in_results} risk-flagged)")

    if hits and filtered_hits:
        print("\n  [PASS] Qdrant is populated and filterable.")
    else:
        print("\n  [WARN] Some queries returned no results — check ingestion logs.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="smoke_test_retrieval",
        description="Pensieve Phase 2 — smoke-test vector search against Qdrant.",
    )
    parser.add_argument(
        "--query",
        default="net interest income",
        help="Query string for both searches. Default: 'net interest income'",
    )
    parser.add_argument(
        "--company",
        default=None,
        help="Company name to use in the filtered search. Auto-detected from first result if not set.",
    )
    parser.add_argument(
        "--collection",
        default=QDRANT_COLLECTION,
        help=f"Qdrant collection name. Default: {QDRANT_COLLECTION}",
    )
    parser.add_argument(
        "--provider",
        choices=["local", "openai"],
        default=EMBEDDING_PROVIDER,
        help=f"Embedding provider. Default: {EMBEDDING_PROVIDER}",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to retrieve per query. Default: 5",
    )

    args = parser.parse_args()
    run_smoke_test(
        query=args.query,
        company_name=args.company,
        collection=args.collection,
        provider=args.provider,
        top_k=args.top_k,
    )


if __name__ == "__main__":
    main()
