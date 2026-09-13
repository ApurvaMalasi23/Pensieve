"""
pensieve/comparator.py
-----------------------
Phase 5 — Multi-Document Comparison Engine

Enables comparison across multiple ingested documents (different companies,
different fiscal years) using metadata filters in Qdrant.

Key Responsibilities:
1. extract_comparison_entities: Extract entities (company, fiscal year) from query via LLM.
2. detect_comparison_intent: Determine if query requires multi-document comparison.
3. resolve_entities_against_corpus: Map user-specified names/years to canonical Qdrant metadata.
4. execute_per_entity_pipeline: Run retrieval, generation, and verification for each entity.
5. compute_numeric_delta: Programmatically compute absolute and percentage deltas (no LLM math).
6. synthesize_comparative_answer: Synthesize a clear side-by-side comparison with table & deltas.
7. rollup_verification: Apply the weakest-link rule to determine comparative verification status.
8. execute_comparison: End-to-end orchestration of multi-document comparison.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from pensieve.classifier import classify_intent
from pensieve.config import (
    GENERATION_LLM_BASE_URL,
    GENERATION_LLM_MODEL,
    LLM_GENERATION_MAX_TOKENS,
    LLM_GENERATION_TIMEOUT,
    NUMERIC_CONTEXT_MAX_TOKENS,
    NUMERIC_LLM_MODEL,
    NUMERIC_RETRIEVAL_TOP_K,
    QDRANT_COLLECTION,
    RETRIEVAL_TOP_K_DEFAULT,
)
from pensieve.generator import (
    Citation,
    GenerationResult,
    _call_llm_with_retry,
    _get_generation_client,
    format_context_blocks,
    generate_answer,
    parse_citations,
)
from pensieve.logger import get_logger
from pensieve.numeric_grounding import (
    VerificationResult,
    extract_numbers_from_text,
    fit_tables_to_context,
    generate_numeric_answer,
    normalize_number,
    verify_numbers_against_grid,
)
from pensieve.retriever import (
    RetrievedChunk,
    retrieve_narrative_chunks,
    retrieve_table_chunks,
)
from pensieve.vector_store import get_client

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class ComparisonEntity:
    """An entity target extracted from a comparison query."""
    company_name: str | None = None
    fiscal_year: str | None = None
    raw_mention: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_name": self.company_name,
            "fiscal_year": self.fiscal_year,
            "raw_mention": self.raw_mention,
        }


@dataclass
class PerEntityResult:
    """Execution and verification outcome for a single entity in a comparison."""
    entity: dict[str, Any]
    intent: str
    answer: str
    verification_status: str  # verified | verified_low_confidence | unverified | no_context_found | not_applicable
    verification_reason: str
    citations: list[dict[str, Any]]
    chunks: list[RetrievedChunk] = field(default_factory=list)
    numbers_extracted: list[str] = field(default_factory=list)
    risk_flag: bool = False
    risk_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "intent": self.intent,
            "answer": self.answer,
            "verification_status": self.verification_status,
            "verification_reason": self.verification_reason,
            "citations": self.citations,
            "numbers_extracted": self.numbers_extracted,
            "risk_flag": self.risk_flag,
            "risk_reasons": self.risk_reasons,
        }


@dataclass
class ComparisonResponse:
    """Complete result of a multi-document comparison."""
    query: str
    intent: str
    comparison_answer: str
    verification_status: str
    verification_reason: str
    per_entity_results: list[dict[str, Any]]
    deltas: dict[str, Any] | None
    citations: list[dict[str, Any]]
    no_context_found: bool


# ---------------------------------------------------------------------------
# Corpus Metadata Discovery & Entity Resolution
# ---------------------------------------------------------------------------

def get_known_documents(client: QdrantClient | None = None) -> list[dict[str, str | None]]:
    """Query Qdrant to discover distinct (company_name, fiscal_year) pairs in the corpus."""
    qdrant = client or get_client()
    try:
        points, _ = qdrant.scroll(
            collection_name=QDRANT_COLLECTION,
            limit=2000,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as exc:
        log.warning("Failed to scroll Qdrant for known documents: %s", exc)
        return []

    seen = set()
    docs = []
    for pt in points:
        payload = pt.payload or {}
        comp = payload.get("company_name")
        fy = payload.get("fiscal_year")
        key = (comp, fy)
        if key not in seen and (comp or fy):
            seen.add(key)
            docs.append({"company_name": comp, "fiscal_year": fy})

    log.debug("Discovered %d unique document metadata pairs in Qdrant: %s", len(docs), docs)
    return docs


def resolve_entity(
    entity: ComparisonEntity,
    known_docs: list[dict[str, str | None]],
) -> ComparisonEntity:
    """Resolve extracted entity fields against known corpus metadata.
    
    Handles minor spelling, casing, punctuation, and year formats (e.g. 'FY24' -> '2024').
    """
    comp_input = (entity.company_name or "").strip().lower()
    fy_input = (entity.fiscal_year or "").strip().lower()

    resolved_comp = entity.company_name
    resolved_fy = entity.fiscal_year

    # 1. Company resolution
    if comp_input:
        best_match = None
        for doc in known_docs:
            known_comp = (doc.get("company_name") or "").strip()
            known_comp_lower = known_comp.lower()
            if not known_comp:
                continue

            # Exact or substring match
            if comp_input == known_comp_lower:
                best_match = known_comp
                break
            # e.g. "lux" in "lux industries limited" or "republic" in "republic bancorp"
            if comp_input in known_comp_lower or known_comp_lower in comp_input:
                best_match = known_comp

        if best_match:
            resolved_comp = best_match

    # 2. Fiscal year resolution
    if fy_input:
        # Standardize FY24 -> 2024, FY 2024 -> 2024, 2024-25 -> 2024-25
        clean_fy = re.sub(r"^fy\s*", "", fy_input).strip()
        best_fy = None
        for doc in known_docs:
            known_fy = (doc.get("fiscal_year") or "").strip()
            known_fy_lower = known_fy.lower()
            if not known_fy:
                continue

            if clean_fy == known_fy_lower:
                best_fy = known_fy
                break
            # E.g. "2024" in "2024" or "2025" in "2025-26"
            if clean_fy in known_fy_lower or known_fy_lower in clean_fy:
                best_fy = known_fy

        if best_fy:
            resolved_fy = best_fy

    return ComparisonEntity(
        company_name=resolved_comp,
        fiscal_year=resolved_fy,
        raw_mention=entity.raw_mention,
    )


# ---------------------------------------------------------------------------
# Task 1: Entity Extraction & Intent Detection
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """You are an information extraction assistant for Pensieve, a financial document analysis platform.
Your task is to analyze a user's question and identify all distinct company names and/or fiscal years/filing periods being inquired about or compared.

Rules:
1. Extract each distinct target as an object with:
   - "company_name": the company name (or null if not specified)
   - "fiscal_year": the fiscal year or reporting period (e.g., "2024", "2025-26", or null if not specified)
   - "raw_mention": the exact words in the query referencing this entity
2. If the user asks to compare two companies (e.g. "Compare revenue of Lux Industries and Republic Bancorp"), extract two entities.
3. If the user asks to compare two years for the same company (e.g. "Republic Bancorp 2023 vs 2024"), extract two entities with the same company_name and different fiscal_years.
4. If only one company/year is mentioned, extract one entity.
5. If no specific company or year is mentioned, return an empty list.
6. Return ONLY valid JSON in the exact format:
{
  "entities": [
    {"company_name": "...", "fiscal_year": "...", "raw_mention": "..."},
    ...
  ]
}
"""


def extract_comparison_entities(
    query: str,
    client: OpenAI | None = None,
    known_docs: list[dict[str, str | None]] | None = None,
) -> list[ComparisonEntity]:
    """Extract entities (company_name, fiscal_year) from the user query via LLM."""
    llm_client = client or _get_generation_client()

    messages = [
        {"role": "system", "content": _EXTRACTION_PROMPT},
        {"role": "user", "content": f"User Query: {query}"},
    ]

    try:
        raw_response = _call_llm_with_retry(
            client=llm_client,
            model=GENERATION_LLM_MODEL,
            messages=messages,
            max_tokens=300,
        )
        # Parse JSON
        clean = raw_response.strip()
        if "```" in clean:
            clean = re.sub(r"^```(?:json)?", "", clean)
            clean = re.sub(r"```$", "", clean).strip()

        data = json.loads(clean)
        raw_entities = data.get("entities", [])
    except Exception as exc:
        log.warning("LLM entity extraction failed for query %r: %s. Falling back to heuristic.", query, exc)
        raw_entities = _heuristic_entity_extraction(query, known_docs)

    entities: list[ComparisonEntity] = []
    for item in raw_entities:
        comp = item.get("company_name")
        fy = item.get("fiscal_year")
        mention = item.get("raw_mention") or ""
        if comp or fy:
            entities.append(ComparisonEntity(
                company_name=comp if comp and comp.lower() != "null" else None,
                fiscal_year=str(fy) if fy and str(fy).lower() != "null" else None,
                raw_mention=mention,
            ))

    # Resolve against known documents in Qdrant
    if known_docs is None:
        known_docs = get_known_documents()

    resolved = [resolve_entity(e, known_docs) for e in entities]
    log.info("Extracted %d comparison entities for %r: %s", len(resolved), query, resolved)
    return resolved


def _heuristic_entity_extraction(
    query: str,
    known_docs: list[dict[str, str | None]] | None = None,
) -> list[dict[str, Any]]:
    """Heuristic fallback extraction matching against known corpus metadata."""
    if known_docs is None:
        known_docs = get_known_documents()

    matched = []
    q_lower = query.lower()

    for doc in known_docs:
        comp = doc.get("company_name")
        fy = doc.get("fiscal_year")
        comp_hit = bool(comp and comp.lower() in q_lower)
        fy_hit = bool(fy and fy.lower() in q_lower)

        if comp_hit or fy_hit:
            matched.append({
                "company_name": comp if comp_hit else None,
                "fiscal_year": fy if fy_hit else None,
                "raw_mention": comp or fy or "",
            })

    return matched


def detect_comparison_intent(
    query: str,
    entities: list[ComparisonEntity] | None = None,
    client: OpenAI | None = None,
) -> tuple[bool, list[ComparisonEntity]]:
    """Determine whether the query represents a multi-document comparison.
    
    Returns
    -------
    (is_comparison, entities):
        True if 2+ distinct entities are detected and comparative intent is present.
    """
    if entities is None:
        entities = extract_comparison_entities(query, client=client)

    if len(entities) < 2:
        return False, entities

    # Check if entities are distinct
    distinct = set()
    for e in entities:
        distinct.add((e.company_name, e.fiscal_year))

    if len(distinct) < 2:
        # Both entities resolved to the exact same document target
        return False, entities

    return True, entities


# ---------------------------------------------------------------------------
# Task 2: Per-Entity Retrieval, Generation, and Verification
# ---------------------------------------------------------------------------

def execute_per_entity_pipeline(
    query: str,
    entity: ComparisonEntity,
    intent: str,
    top_k: int | None = None,
    client: OpenAI | None = None,
) -> PerEntityResult:
    """Execute retrieval, generation, and verification for a single comparison entity."""
    comp_name = entity.company_name
    fiscal_year = entity.fiscal_year

    log.info(
        "Executing per-entity pipeline for company=%s, fiscal_year=%s, intent=%s",
        comp_name, fiscal_year, intent,
    )

    if intent == "narrative":
        try:
            chunks = retrieve_narrative_chunks(
                query=query,
                top_k=top_k or RETRIEVAL_TOP_K_DEFAULT,
                company_name=comp_name,
                fiscal_year=fiscal_year,
            )
        except Exception as exc:
            log.warning("Per-entity narrative retrieval failed: %s", exc)
            chunks = []

        if not chunks:
            return PerEntityResult(
                entity=entity.to_dict(),
                intent=intent,
                answer=f"No relevant narrative information found for {comp_name or 'unspecified company'} (FY {fiscal_year or 'unspecified'}).",
                verification_status="no_context_found",
                verification_reason="No matching chunks found in the corpus for this entity.",
                citations=[],
                chunks=[],
            )

        gen_result: GenerationResult = generate_answer(query=query, chunks=chunks, client=client)
        citations_out = [
            {
                "marker": c.get("marker", "[?]"),
                "chunk_id": c.get("chunk_id", ""),
                "doc_id": c.get("doc_id", ""),
                "source_filename": c.get("source_filename", ""),
                "company_name": c.get("company_name"),
                "fiscal_year": c.get("fiscal_year"),
                "page_start": c.get("page_start", 0),
                "page_end": c.get("page_end", 0),
                "excerpt": c.get("excerpt", ""),
            }
            for c in gen_result.citations
        ]

        status = "no_context_found" if gen_result.no_context_found else "not_applicable"
        reason = (
            "Refusal or no citations returned."
            if gen_result.no_context_found
            else "Narrative query: numeric verification not applicable."
        )

        return PerEntityResult(
            entity=entity.to_dict(),
            intent=intent,
            answer=gen_result.answer,
            verification_status=status,
            verification_reason=reason,
            citations=citations_out,
            chunks=chunks,
        )

    else:
        # intent == "numeric"
        try:
            table_chunks = retrieve_table_chunks(
                query=query,
                top_k=top_k or NUMERIC_RETRIEVAL_TOP_K,
                company_name=comp_name,
                fiscal_year=fiscal_year,
            )
        except Exception as exc:
            log.warning("Per-entity table retrieval failed: %s", exc)
            table_chunks = []

        if not table_chunks:
            return PerEntityResult(
                entity=entity.to_dict(),
                intent=intent,
                answer=f"No relevant financial tables found for {comp_name or 'unspecified company'} (FY {fiscal_year or 'unspecified'}).",
                verification_status="no_context_found",
                verification_reason="No matching table chunks found in the corpus for this entity.",
                citations=[],
                chunks=[],
            )

        table_chunks = fit_tables_to_context(table_chunks)
        gen_result = generate_numeric_answer(query=query, chunks=table_chunks, client=client)

        if gen_result.no_context_found:
            return PerEntityResult(
                entity=entity.to_dict(),
                intent=intent,
                answer=gen_result.answer,
                verification_status="no_context_found",
                verification_reason="Model refused or no context citations found for numeric query.",
                citations=[],
                chunks=table_chunks,
            )

        # Extract and verify numbers against table cells
        numbers = extract_numbers_from_text(gen_result.answer)
        verif_res: VerificationResult = verify_numbers_against_grid(
            numbers_from_answer=numbers,
            cited_chunks=gen_result.citations,
            all_retrieved_chunks=table_chunks,
        )

        # Check risk flag
        has_risk = any(c.risk_flag for c in table_chunks)
        risk_reasons = []
        for c in table_chunks:
            risk_reasons.extend(c.risk_reasons)

        chunk_by_id = {c.chunk_id: c for c in table_chunks}
        citations_out = []
        for cit_dict in gen_result.citations:
            cid = cit_dict.get("chunk_id", "")
            rc = chunk_by_id.get(cid)
            citations_out.append({
                "marker": cit_dict["marker"],
                "chunk_id": cid,
                "doc_id": cit_dict["doc_id"],
                "source_filename": cit_dict["source_filename"],
                "company_name": cit_dict.get("company_name"),
                "fiscal_year": cit_dict.get("fiscal_year"),
                "page_start": cit_dict["page_start"],
                "page_end": cit_dict["page_end"],
                "table_id": rc.table_id if rc else None,
                "risk_flag": rc.risk_flag if rc else False,
                "risk_reasons": rc.risk_reasons if rc else [],
                "excerpt": cit_dict["excerpt"],
            })

        return PerEntityResult(
            entity=entity.to_dict(),
            intent=intent,
            answer=gen_result.answer,
            verification_status=verif_res.status,
            verification_reason=verif_res.reason,
            citations=citations_out,
            chunks=table_chunks,
            numbers_extracted=numbers,
            risk_flag=has_risk,
            risk_reasons=risk_reasons,
        )


# ---------------------------------------------------------------------------
# Task 3: Programmatic Delta Computation & Synthesis
# ---------------------------------------------------------------------------

def _parse_float_safe(s: str) -> float | None:
    """Parse a financial number string (stripping commas, currency symbols, percentages)."""
    clean = s.strip()
    clean = re.sub(r"[\$,₹€£%]", "", clean)
    clean = clean.replace(",", "")
    # Handle parentheses negative: (123.45) -> -123.45
    if clean.startswith("(") and clean.endswith(")"):
        clean = "-" + clean[1:-1].strip()
    try:
        return float(clean)
    except ValueError:
        return None


def compute_numeric_delta(per_entity_results: list[PerEntityResult]) -> dict[str, Any] | None:
    """Deterministically compute absolute and percentage delta between two entities.
    
    CRITICAL: Pensieve never relies on LLM arithmetic for financial deltas.
    """
    if len(per_entity_results) < 2:
        return None

    res_a, res_b = per_entity_results[0], per_entity_results[1]

    # Must both have numbers extracted
    if not res_a.numbers_extracted or not res_b.numbers_extracted:
        return None

    val_a = _parse_float_safe(res_a.numbers_extracted[0])
    val_b = _parse_float_safe(res_b.numbers_extracted[0])

    if val_a is None or val_b is None:
        return None

    abs_diff = val_b - val_a
    pct_diff = ((val_b - val_a) / abs(val_a)) * 100.0 if val_a != 0 else None

    direction = "increase" if abs_diff > 0 else "decrease" if abs_diff < 0 else "no change"

    return {
        "entity_a": {
            "entity": res_a.entity,
            "raw_value": res_a.numbers_extracted[0],
            "parsed_value": val_a,
        },
        "entity_b": {
            "entity": res_b.entity,
            "raw_value": res_b.numbers_extracted[0],
            "parsed_value": val_b,
        },
        "absolute_delta": round(abs_diff, 4),
        "percentage_delta": round(pct_diff, 2) if pct_diff is not None else None,
        "direction": direction,
    }


_SYNTHESIS_PROMPT = """You are Pensieve's comparative financial analysis assistant.
Your task is to synthesize a clear, objective, and well-structured comparative answer comparing the two entities based on the per-entity answers and programmatic metrics provided below.

Strict instructions:
1. Grounding: Rely strictly on the per-entity statements and metrics provided.
2. Structure:
   - Provide a concise summary comparing the two entities.
   - Include a Markdown Comparison Table highlighting key metrics, source periods, values, and verification status.
   - Present the exact programmatic delta if available. DO NOT calculate your own numbers or modify the delta.
3. Citations: Retain and include the bracket citation markers [1], [2] referencing the source claims.
4. Transparency: If any entity has warnings (risk flags, low confidence, or unverified numbers), note this clearly in the synthesis.
"""


def synthesize_comparative_answer(
    query: str,
    intent: str,
    per_entity_results: list[PerEntityResult],
    deltas: dict[str, Any] | None,
    client: OpenAI | None = None,
) -> str:
    """Synthesize a unified comparative answer with table and deltas."""
    # If all entities returned no context found, return clean refusal
    if all(r.verification_status == "no_context_found" for r in per_entity_results):
        return (
            f"No relevant information was found in the ingested documents for either entity "
            f"to answer the question: {query}"
        )

    # Build context for synthesis
    sections = []
    for i, res in enumerate(per_entity_results, start=1):
        ent_desc = f"{res.entity.get('company_name') or 'Unspecified'} (FY {res.entity.get('fiscal_year') or 'Unspecified'})"
        sections.append(
            f"--- Entity {i}: {ent_desc} ---\n"
            f"Verification Status: {res.verification_status}\n"
            f"Extracted Numbers: {res.numbers_extracted}\n"
            f"Answer: {res.answer}\n"
        )

    context_str = "\n".join(sections)
    delta_str = ""
    if deltas:
        pct_text = f"{deltas['percentage_delta']}%" if deltas["percentage_delta"] is not None else "N/A"
        delta_str = (
            f"\nProgrammatic Delta (precomputed):\n"
            f"- Absolute Difference: {deltas['absolute_delta']}\n"
            f"- Percentage Difference: {pct_text}\n"
            f"- Direction: {deltas['direction']}\n"
        )

    user_prompt = (
        f"User Comparison Query: {query}\n"
        f"Intent: {intent}\n\n"
        f"{context_str}\n"
        f"{delta_str}\n"
        f"Synthesize the comparative analysis now:"
    )

    llm_client = client or _get_generation_client()
    messages = [
        {"role": "system", "content": _SYNTHESIS_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        synth = _call_llm_with_retry(
            client=llm_client,
            model=GENERATION_LLM_MODEL,
            messages=messages,
            max_tokens=LLM_GENERATION_MAX_TOKENS,
        )
        return synth
    except Exception as exc:
        log.warning("LLM comparative synthesis failed: %s. Falling back to template synthesis.", exc)
        return _template_comparative_synthesis(per_entity_results, deltas)


def _template_comparative_synthesis(
    per_entity_results: list[PerEntityResult],
    deltas: dict[str, Any] | None,
) -> str:
    """Deterministic fallback synthesis if LLM call fails."""
    lines = ["### Multi-Document Comparison\n"]
    lines.append("| Entity | Fiscal Year | Status | Key Answer / Figures |")
    lines.append("| :--- | :--- | :--- | :--- |")
    for r in per_entity_results:
        comp = r.entity.get("company_name") or "N/A"
        fy = r.entity.get("fiscal_year") or "N/A"
        lines.append(f"| {comp} | {fy} | {r.verification_status} | {r.answer[:120]}... |")

    if deltas:
        lines.append("\n**Programmatic Delta:**")
        pct = f" ({deltas['percentage_delta']}%)" if deltas["percentage_delta"] is not None else ""
        lines.append(f"- Absolute Delta: {deltas['absolute_delta']}{pct} ({deltas['direction']})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Task 4: Rollup Verification Status
# ---------------------------------------------------------------------------

def rollup_verification(per_entity_results: list[PerEntityResult]) -> tuple[str, str]:
    """Roll up individual entity verification statuses using the weakest-link rule.
    
    Priority:
      1. unverified
      2. verified_low_confidence
      3. verified
      4. mixed_coverage / no_context_found
    """
    statuses = [r.verification_status for r in per_entity_results]

    if all(s == "no_context_found" for s in statuses):
        return "no_context_found", "No relevant context found for any of the compared entities."

    if any(s == "no_context_found" for s in statuses):
        missing = [
            r.entity.get("company_name") or "Entity"
            for r in per_entity_results if r.verification_status == "no_context_found"
        ]
        return "mixed_coverage", f"Partial coverage: no context found for {', '.join(missing)}."

    if any(s == "unverified" for s in statuses):
        unverif = [
            r.entity.get("company_name") or "Entity"
            for r in per_entity_results if r.verification_status == "unverified"
        ]
        return "unverified", f"One or more entities could not be verified against table cells: {', '.join(unverif)}."

    if any(s == "verified_low_confidence" for s in statuses):
        low_conf = [
            r.entity.get("company_name") or "Entity"
            for r in per_entity_results if r.verification_status == "verified_low_confidence"
        ]
        return "verified_low_confidence", f"Figures verified, but extraction quality risk flags present for: {', '.join(low_conf)}."

    if all(s == "verified" for s in statuses):
        return "verified", "All compared figures verified exactly against extracted table cells."

    if all(s in ("not_applicable", "verified") for s in statuses):
        return "not_applicable", "Narrative comparison: numeric cell verification is not applicable."

    return "verified", "Comparison completed."


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def execute_comparison(
    query: str,
    entities: list[ComparisonEntity],
    client: OpenAI | None = None,
) -> ComparisonResponse:
    """Execute end-to-end multi-document comparison."""
    # 1. Classify query intent
    intent = classify_intent(query)
    log.info("Comparison query intent: %s for query: %r", intent, query)

    # 2. Run per-entity retrieval, generation, and verification
    per_entity_results: list[PerEntityResult] = []
    for ent in entities:
        res = execute_per_entity_pipeline(
            query=query,
            entity=ent,
            intent=intent,
            client=client,
        )
        per_entity_results.append(res)

    # 3. Compute programmatic deltas if numeric
    deltas = None
    if intent == "numeric":
        deltas = compute_numeric_delta(per_entity_results)

    # 4. Synthesize comparative answer
    synth_answer = synthesize_comparative_answer(
        query=query,
        intent=intent,
        per_entity_results=per_entity_results,
        deltas=deltas,
        client=client,
    )

    # 5. Rollup verification status
    rollup_status, rollup_reason = rollup_verification(per_entity_results)

    # 6. Aggregate citations across all entities
    all_citations: list[dict[str, Any]] = []
    seen_chunks = set()
    for res in per_entity_results:
        for cit in res.citations:
            cid = cit.get("chunk_id")
            if cid and cid not in seen_chunks:
                seen_chunks.add(cid)
                all_citations.append(cit)

    no_context = rollup_status == "no_context_found"

    return ComparisonResponse(
        query=query,
        intent=intent,
        comparison_answer=synth_answer,
        verification_status=rollup_status,
        verification_reason=rollup_reason,
        per_entity_results=[r.to_dict() for r in per_entity_results],
        deltas=deltas,
        citations=all_citations,
        no_context_found=no_context,
    )
