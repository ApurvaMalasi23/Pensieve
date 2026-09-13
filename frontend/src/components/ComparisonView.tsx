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
      className="animate-settle space-y-4 rounded-2xl border border-white/[0.08] bg-[#13161F] p-5 shadow-sm text-[#F1F3F9]"
    >
      {/* Top Banner: Multi-Document Comparison Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] pb-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#E59500]/15 text-[#E59500] border border-[#E59500]/25">
            <Scale className="h-4 w-4 stroke-[1.8]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-medium text-[#F1F3F9] text-sm">
                Cross-Document Comparison
              </h4>
              <span className="rounded bg-white/6 px-1.5 py-0.5 text-[10px] text-[#8C93A5] tabular-nums font-mono border border-white/6">
                {perEntity.length} filings evaluated
              </span>
            </div>
            <p className="text-xs text-[#8C93A5] mt-0.5">
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
          className="rounded-xl border border-[#10B981]/25 bg-[#10B981]/6 p-4"
        >
          <div className="flex items-center justify-between border-b border-[#10B981]/20 pb-2 mb-3">
            <span className="text-xs font-medium text-[#10B981]">
              Programmatic Delta Computation
            </span>
            <div className="flex items-center gap-1.5 text-xs font-semibold">
              {deltas.direction === "increase" && (
                <span className="inline-flex items-center gap-1 text-[#10B981] tabular-nums font-mono">
                  <TrendingUp className="h-3.5 w-3.5 stroke-[2]" />
                  +{deltas.percentage_delta?.toLocaleString()}%
                </span>
              )}
              {deltas.direction === "decrease" && (
                <span className="inline-flex items-center gap-1 text-[#EF4444] tabular-nums font-mono">
                  <TrendingDown className="h-3.5 w-3.5 stroke-[2]" />
                  {deltas.percentage_delta?.toLocaleString()}%
                </span>
              )}
              {deltas.direction === "flat" && (
                <span className="inline-flex items-center gap-1 text-[#8C93A5] tabular-nums font-mono">
                  <Minus className="h-3.5 w-3.5 stroke-[2]" />
                  Flat (0%)
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-xs">
            <div className="rounded-lg bg-[#181C28] p-3.5 border border-white/[0.08]">
              <span className="text-[11px] text-[#8C93A5] block">
                {deltas.entity_a?.entity?.company_name || "Entity A"}
                {deltas.entity_a?.entity?.fiscal_year && ` (FY ${deltas.entity_a.entity.fiscal_year})`}
              </span>
              <span className="text-lg font-semibold text-[#F1F3F9] mt-1 block tabular-nums font-mono">
                {deltas.entity_a?.raw_value}
              </span>
            </div>

            <div className="rounded-lg bg-[#181C28] p-3.5 border border-white/[0.08]">
              <span className="text-[11px] text-[#8C93A5] block">
                {deltas.entity_b?.entity?.company_name || "Entity B"}
                {deltas.entity_b?.entity?.fiscal_year && ` (FY ${deltas.entity_b.entity.fiscal_year})`}
              </span>
              <span className="text-lg font-semibold text-[#F1F3F9] mt-1 block tabular-nums font-mono">
                {deltas.entity_b?.raw_value}
              </span>
            </div>
          </div>

          <div className="mt-2.5 text-[11px] text-[#10B981]/80 text-right tabular-nums font-mono">
            Absolute delta: {deltas.absolute_delta?.toLocaleString()}
          </div>
        </div>
      )}

      {/* Synthesized Cross-Document Answer */}
      <div className="rounded-xl bg-[#181C28] p-4 border border-white/[0.06]">
        <span className="text-[11px] font-mono uppercase tracking-wider text-[#8C93A5] block mb-1.5">
          Synthesized Analysis
        </span>
        <div className="text-sm leading-relaxed text-[#F1F3F9] font-sans">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => <p className="mb-2.5 last:mb-0 leading-relaxed text-[#F1F3F9]">{children}</p>,
              strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
              ul: ({ children }) => <ul className="mb-2.5 list-disc pl-5 space-y-1 text-[#C2C7D4]">{children}</ul>,
              ol: ({ children }) => <ol className="mb-2.5 list-decimal pl-5 space-y-1 text-[#C2C7D4]">{children}</ol>,
              li: ({ children }) => <li className="leading-relaxed">{children}</li>,
              table: ({ children }) => (
                <div className="my-3 overflow-x-auto rounded-xl border border-white/10 bg-[#0A0B0E]/70 p-1">
                  <table className="w-full border-collapse text-left text-xs tabular-nums font-mono">
                    {children}
                  </table>
                </div>
              ),
              thead: ({ children }) => (
                <thead className="border-b border-white/10 bg-white/[0.02] text-[10px] font-mono tracking-wider uppercase text-[#8C93A5]">
                  {children}
                </thead>
              ),
              th: ({ children }) => (
                <th className="px-3 py-1.5 font-semibold text-[#E59500]">{children}</th>
              ),
              tbody: ({ children }) => (
                <tbody className="divide-y divide-white/6 font-mono text-[11px]">{children}</tbody>
              ),
              tr: ({ children }) => (
                <tr className="hover:bg-white/[0.03] transition-colors">{children}</tr>
              ),
              td: ({ children }) => (
                <td className="px-3 py-1.5 text-[#F1F3F9] tabular-nums font-mono">{children}</td>
              ),
            }}
          >
            {response.answer}
          </ReactMarkdown>
        </div>

        {/* Global comparison citations */}
        {response.citations && response.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-white/6">
            <span className="text-[11px] text-[#8E8D8A] font-medium block mb-1.5">
              Referenced filings ({response.citations.length}):
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
            className="flex items-center gap-1.5 text-xs text-[#8E8D8A] hover:text-[#F0EFEA] transition-colors cursor-pointer"
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
                    className="rounded-xl border border-white/[0.06] bg-[#181C28] p-3.5 text-xs space-y-2"
                  >
                    <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                      <span className="font-medium text-[#F1F3F9]">
                        {companyName} (FY {fiscalYear})
                      </span>
                      <VerificationBadge
                        status={vStatus}
                        reason={vReason}
                        compact
                      />
                    </div>

                    <div className="text-[#C2C7D4] leading-relaxed text-xs font-sans">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed text-[#C2C7D4]">{children}</p>,
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
