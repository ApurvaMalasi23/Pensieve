"use client";

import React, { useState } from "react";
import { AskResponse, Citation } from "@/types/api";
import { VerificationBadge } from "./VerificationBadge";
import { CitationChip } from "./CitationChip";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronDown,
  ChevronUp,
  Scale,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ComparisonViewProps {
  response: AskResponse;
  onSelectCitation: (citation: Citation) => void;
}

export const ComparisonView: React.FC<ComparisonViewProps> = ({
  response,
  onSelectCitation,
}) => {
  const [showEntityDetails, setShowEntityDetails] = useState(true);
  const deltas = response.deltas;
  const perEntity = response.per_entity_results || [];

  return (
    <div
      data-testid="comparison-view"
      className="animate-settle space-y-4 rounded-2xl border border-white/[0.05] bg-[#121216]/75 backdrop-blur-2xl p-5 shadow-[0_16px_40px_rgba(0,0,0,0.6),inset_0_1px_0_rgba(255,255,255,0.05)] text-[#F7F7F4]"
    >
      {/* Top Banner: Multi-Document Comparison Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.04] pb-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#CBB282]/15 text-[#CBB282] border border-[#CBB282]/25 shadow-[0_0_8px_rgba(203,178,130,0.15)]">
            <Scale className="h-4 w-4 stroke-[1.8]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-serif font-medium text-[#F7F7F4] text-sm sm:text-[15px] tracking-[0.01em]">
                Cross-Document Comparison
              </h4>
              <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-[9.5px] text-[#CDCBC4] tabular-nums font-mono border border-white/[0.05]">
                {perEntity.length} filings evaluated
              </span>
            </div>
            <p className="text-xs text-[#82807A] mt-0.5 font-light">
              Synthesis derived from multiple independent corporate filings
            </p>
          </div>
        </div>

        {/* Overall Rollup Verification Badge */}
        {response.verification && (
          <div>
            <VerificationBadge
              status={response.verification.status}
              reason={response.verification.reason}
            />
          </div>
        )}
      </div>

      {/* Programmatic Deltas Card (if numeric comparison) */}
      {deltas && (
        <div
          data-testid="numeric-deltas-card"
          className="rounded-xl border border-[#52B788]/25 bg-[#52B788]/5 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
        >
          <div className="flex items-center justify-between border-b border-[#52B788]/20 pb-2 mb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-[#52B788]">
              Programmatic Delta Computation
            </span>
            <div className="flex items-center gap-1.5 text-xs font-semibold">
              {deltas.direction === "increase" && (
                <span className="inline-flex items-center gap-1 text-[#52B788] tabular-nums font-mono">
                  <TrendingUp className="h-3.5 w-3.5 stroke-[2]" />
                  +{deltas.percentage_delta?.toLocaleString()}%
                </span>
              )}
              {deltas.direction === "decrease" && (
                <span className="inline-flex items-center gap-1 text-[#E06D6D] tabular-nums font-mono">
                  <TrendingDown className="h-3.5 w-3.5 stroke-[2]" />
                  {deltas.percentage_delta?.toLocaleString()}%
                </span>
              )}
              {deltas.direction === "flat" && (
                <span className="inline-flex items-center gap-1 text-[#82807A] tabular-nums font-mono">
                  <Minus className="h-3.5 w-3.5 stroke-[2]" />
                  Flat (0%)
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-xs">
            <div className="rounded-lg bg-[#17181D] p-3.5 border border-white/[0.05] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
              <span className="text-[11px] text-[#82807A] block">
                {deltas.entity_a?.entity?.company_name || "Entity A"}
                {deltas.entity_a?.entity?.fiscal_year && ` (FY ${deltas.entity_a.entity.fiscal_year})`}
              </span>
              <span className="text-lg font-semibold text-[#F7F7F4] mt-1 block tabular-nums font-mono">
                {deltas.entity_a?.raw_value}
              </span>
            </div>

            <div className="rounded-lg bg-[#17181D] p-3.5 border border-white/[0.05] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
              <span className="text-[11px] text-[#82807A] block">
                {deltas.entity_b?.entity?.company_name || "Entity B"}
                {deltas.entity_b?.entity?.fiscal_year && ` (FY ${deltas.entity_b.entity.fiscal_year})`}
              </span>
              <span className="text-lg font-semibold text-[#F7F7F4] mt-1 block tabular-nums font-mono">
                {deltas.entity_b?.raw_value}
              </span>
            </div>
          </div>

          <div className="mt-2.5 text-[11px] text-[#52B788]/80 text-right tabular-nums font-mono">
            Absolute delta: {deltas.absolute_delta?.toLocaleString()}
          </div>
        </div>
      )}

      {/* Synthesized Cross-Document Answer */}
      <div className="rounded-xl bg-[#17181D]/80 p-4 border border-white/[0.05] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
        <span className="text-[10.5px] font-mono uppercase tracking-wider text-[#82807A] block mb-1.5">
          Synthesized Analysis
        </span>
        <div className="text-sm leading-relaxed text-[#F7F7F4] font-sans">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => <p className="mb-2.5 last:mb-0 leading-relaxed text-[#F7F7F4]">{children}</p>,
              strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
              ul: ({ children }) => <ul className="mb-2.5 list-disc pl-5 space-y-1 text-[#CDCBC4]">{children}</ul>,
              ol: ({ children }) => <ol className="mb-2.5 list-decimal pl-5 space-y-1 text-[#CDCBC4]">{children}</ol>,
              li: ({ children }) => <li className="leading-relaxed">{children}</li>,
              table: ({ children }) => (
                <div className="my-3 overflow-x-auto rounded-xl border border-white/[0.05] bg-[#0B0B0D] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                  <table className="w-full border-collapse text-left text-xs tabular-nums font-mono">
                    {children}
                  </table>
                </div>
              ),
              thead: ({ children }) => (
                <thead className="border-b border-white/[0.06] bg-white/[0.015] text-[10px] font-mono tracking-wider uppercase text-[#CBB282]">
                  {children}
                </thead>
              ),
              th: ({ children }) => (
                <th className="px-3 py-1.5 font-medium text-[#CBB282] border-r border-white/[0.04] last:border-0">{children}</th>
              ),
              tbody: ({ children }) => (
                <tbody className="divide-y divide-white/[0.035] font-mono text-[11px]">{children}</tbody>
              ),
              tr: ({ children }) => (
                <tr className="hover:bg-white/[0.025] transition-colors">{children}</tr>
              ),
              td: ({ children }) => (
                <td className="px-3 py-1.5 text-[#CDCBC4] tabular-nums font-mono border-r border-white/[0.035] last:border-0">{children}</td>
              ),
            }}
          >
            {response.answer}
          </ReactMarkdown>
        </div>

        {/* Global comparison citations */}
        {response.citations && response.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-white/[0.04]">
            <span className="text-[10.5px] text-[#82807A] font-mono uppercase tracking-wider block mb-1.5">
              Referenced Filings ({response.citations.length}):
            </span>
            <div className="flex flex-wrap gap-1.5">
              {response.citations.map((c, i) => (
                <CitationChip key={i} citation={c} onClick={onSelectCitation} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Collapsible Per-Entity Breakdown Details */}
      {perEntity.length > 0 && (
        <div className="pt-2">
          <button
            type="button"
            onClick={() => setShowEntityDetails(!showEntityDetails)}
            className="flex items-center gap-1.5 text-xs text-[#82807A] hover:text-[#F7F7F4] transition-colors cursor-pointer"
          >
            {showEntityDetails ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
            <span>
              {showEntityDetails ? "Hide individual filing breakdowns" : "Show individual filing breakdowns"}
            </span>
          </button>

          {showEntityDetails && (
            <div className="mt-3 space-y-3">
              {perEntity.map((entityRes, idx) => {
                const companyName = entityRes.entity?.company_name || "Filing";
                const fiscalYear = entityRes.entity?.fiscal_year || "N/A";
                const vStatus = entityRes.verification_status || (entityRes as any).verification?.status || "not_applicable";
                const vReason = entityRes.verification_reason || (entityRes as any).verification?.reason;

                return (
                  <div
                    key={idx}
                    className="rounded-xl border border-white/[0.04] bg-[#17181D]/70 p-3.5 text-xs space-y-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]"
                  >
                    <div className="flex items-center justify-between border-b border-white/[0.04] pb-2">
                      <span className="font-serif font-medium text-[#F7F7F4] text-sm">
                        {companyName} (FY {fiscalYear})
                      </span>
                      <VerificationBadge
                        status={vStatus}
                        reason={vReason}
                        compact
                      />
                    </div>

                    <div className="text-[#CDCBC4] leading-relaxed text-xs font-sans">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed text-[#CDCBC4]">{children}</p>,
                          strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                        }}
                      >
                        {entityRes.answer}
                      </ReactMarkdown>
                    </div>

                    {entityRes.citations && entityRes.citations.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-1">
                        {entityRes.citations.map((c, cIdx) => (
                          <CitationChip
                            key={cIdx}
                            citation={c}
                            onClick={onSelectCitation}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
