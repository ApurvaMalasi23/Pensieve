"use client";

import React, { useState } from "react";
import { CheckCircle2, ShieldAlert, AlertOctagon, Info, ChevronDown, ChevronUp, Check, Cpu } from "lucide-react";

interface VerificationBadgeProps {
  status: "verified" | "verified_low_confidence" | "unverified" | "not_applicable" | string;
  reason?: string;
  className?: string;
  compact?: boolean;
}

export const VerificationBadge: React.FC<VerificationBadgeProps> = ({
  status,
  reason,
  className = "",
  compact = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (status === "not_applicable") {
    return null;
  }

  if (status === "verified") {
    return (
      <div
        data-testid="verification-badge-verified"
        className={`animate-settle rounded-2xl border border-[#10B981]/25 bg-gradient-to-br from-[#0D1C16]/70 via-[#0A1611]/50 to-[#08100C]/40 backdrop-blur-xl p-4 text-[#10B981] shadow-[0_8px_24px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(16,185,129,0.12)] transition-all ${className}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <div className="flex h-4.5 w-4.5 shrink-0 items-center justify-center text-[#10B981] mt-0.5">
              <CheckCircle2 className="h-4.5 w-4.5 stroke-[1.8]" />
            </div>
            <div className="flex flex-col text-xs leading-relaxed">
              <span className="font-semibold text-[#F1F3F9] tracking-tight">
                Verified Against Source Table
              </span>
              {!compact && (
                <span className="text-[#10B981]/85 text-[11px] mt-0.5 font-light">
                  Figures matched cell-for-cell against extracted financial table cells.
                </span>
              )}
            </div>
          </div>

          {!compact && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              data-testid="inspect-proof-button"
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-mono text-[#10B981] bg-[#10B981]/10 hover:bg-[#10B981]/20 transition-all cursor-pointer shrink-0 border border-[#10B981]/25 shadow-xs"
            >
              <Cpu className="h-3 w-3" />
              <span>{isExpanded ? "Hide Proof" : "Inspect Proof"}</span>
              {isExpanded ? (
                <ChevronUp className="h-3 w-3 ml-0.5" />
              ) : (
                <ChevronDown className="h-3 w-3 ml-0.5" />
              )}
            </button>
          )}
        </div>

        {/* Micro-Audit Proof Accordion */}
        {isExpanded && !compact && (
          <div className="mt-3.5 pt-3.5 border-t border-[#10B981]/15 space-y-2 text-[11px] font-mono text-[#C2C7D4] animate-settle">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div className="rounded-xl bg-[#0A0B0E]/80 border border-white/[0.06] p-3 shadow-sm">
                <span className="text-[10px] uppercase text-[#8C93A5] block mb-1 font-mono tracking-wider">
                  Mathematical Delta
                </span>
                <span className="text-[#10B981] font-semibold text-xs flex items-center gap-1.5">
                  <Check className="h-3.5 w-3.5 stroke-[2.5]" /> Exact Match (Δ = 0.00%)
                </span>
                <p className="text-[10px] text-[#8C93A5] mt-1.5 font-sans font-light leading-relaxed">
                  Target figure matched against primary source cell coordinates without discrepancy.
                </p>
              </div>

              <div className="rounded-xl bg-[#0A0B0E]/80 border border-white/[0.06] p-3 shadow-sm">
                <span className="text-[10px] uppercase text-[#8C93A5] block mb-1 font-mono tracking-wider">
                  Audit Protocol
                </span>
                <span className="text-[#F1F3F9] font-semibold text-xs">
                  Cell-Level OCR Crosscheck
                </span>
                <p className="text-[10px] text-[#8C93A5] mt-1.5 font-sans font-light leading-relaxed">
                  Grounding engine validated tabular row headers and column period parity.
                </p>
              </div>
            </div>

            {reason && (
              <div className="rounded-xl bg-[#0A0B0E]/80 border border-[#10B981]/20 px-3.5 py-2 text-[10.5px] text-[#10B981]/90 flex items-center justify-between">
                <span>{reason}</span>
                <span className="text-[#8C93A5] text-[10px] uppercase tracking-wider font-mono font-medium">Fidelity: High</span>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  if (status === "verified_low_confidence") {
    return (
      <div
        data-testid="verification-badge-low-confidence"
        className={`animate-settle rounded-2xl border border-[#F59E0B]/30 bg-gradient-to-br from-[#1C1408]/70 via-[#160F06]/50 to-[#100B04]/40 backdrop-blur-xl p-4 text-[#F59E0B] shadow-[0_8px_24px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(245,158,11,0.12)] transition-all ${className}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <div className="flex h-4.5 w-4.5 shrink-0 items-center justify-center text-[#F59E0B] mt-0.5">
              <ShieldAlert className="h-4.5 w-4.5 stroke-[1.8]" />
            </div>
            <div className="flex flex-col text-xs leading-relaxed max-w-xl">
              <span className="font-semibold text-[#F1F3F9] tracking-tight">
                Verified with Table Extraction Warning
              </span>
              <p className="mt-1 text-[11px] leading-normal text-[#F59E0B] bg-[#0A0B0E]/80 rounded-xl px-3 py-2 border border-[#F59E0B]/20 tabular-nums font-light">
                {reason || "The cited table was flagged for structural or OCR irregularities. Please verify against original PDF."}
              </p>
            </div>
          </div>

          {!compact && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              data-testid="inspect-proof-button"
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-mono text-[#F59E0B] bg-[#F59E0B]/10 hover:bg-[#F59E0B]/20 transition-all cursor-pointer shrink-0 border border-[#F59E0B]/25 shadow-xs"
            >
              <Cpu className="h-3 w-3" />
              <span>{isExpanded ? "Hide Audit" : "Inspect Audit"}</span>
              {isExpanded ? (
                <ChevronUp className="h-3 w-3 ml-0.5" />
              ) : (
                <ChevronDown className="h-3 w-3 ml-0.5" />
              )}
            </button>
          )}
        </div>

        {/* Micro-Audit Warning Breakdown */}
        {isExpanded && !compact && (
          <div className="mt-3.5 pt-3.5 border-t border-[#F59E0B]/15 space-y-2 text-[11px] font-mono text-[#C2C7D4] animate-settle">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div className="rounded-xl bg-[#0A0B0E]/80 border border-white/[0.06] p-3 shadow-sm">
                <span className="text-[10px] uppercase text-[#8C93A5] block mb-1 font-mono tracking-wider">
                  Confidence Rating
                </span>
                <span className="text-[#F59E0B] font-semibold text-xs">
                  Low / Anomaly Detected
                </span>
                <p className="text-[10px] text-[#8C93A5] mt-1.5 font-sans font-light leading-relaxed">
                  The mathematical figure was matched, but the source table contains misaligned cells or OCR artifacting.
                </p>
              </div>

              <div className="rounded-xl bg-[#0A0B0E]/80 border border-white/[0.06] p-3 shadow-sm">
                <span className="text-[10px] uppercase text-[#8C93A5] block mb-1 font-mono tracking-wider">
                  Analyst Action
                </span>
                <span className="text-[#F1F3F9] font-semibold text-xs">
                  Inspect Source PDF
                </span>
                <p className="text-[10px] text-[#8C93A5] mt-1.5 font-sans font-light leading-relaxed">
                  Click the citation chip to view the bounding box on the original filing page before citing.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (status === "unverified") {
    return (
      <div
        data-testid="verification-badge-unverified"
        className={`animate-settle rounded-2xl border border-[#EF4444]/30 bg-gradient-to-br from-[#1C0A0A]/70 via-[#160808]/50 to-[#100606]/40 backdrop-blur-xl p-4 text-[#EF4444] shadow-[0_8px_24px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(239,68,68,0.12)] transition-all ${className}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <div className="flex h-4.5 w-4.5 shrink-0 items-center justify-center text-[#EF4444] mt-0.5">
              <AlertOctagon className="h-4.5 w-4.5 stroke-[1.8]" />
            </div>
            <div className="flex flex-col text-xs leading-relaxed max-w-xl">
              <span className="font-semibold text-[#F1F3F9] tracking-tight">
                Unverified Numeric Figure
              </span>
              <p className="mt-1 text-[11px] leading-normal text-[#EF4444]/90 bg-[#0A0B0E]/80 rounded-xl px-3 py-2 border border-[#EF4444]/20 font-light">
                {reason || "This number was not located in any retrieved financial table. Verify against the source document directly before relying on this figure."}
              </p>
            </div>
          </div>

          {!compact && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              data-testid="inspect-proof-button"
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-mono text-[#EF4444] bg-[#EF4444]/10 hover:bg-[#EF4444]/20 transition-all cursor-pointer shrink-0 border border-[#EF4444]/25 shadow-xs"
            >
              <Info className="h-3 w-3" />
              <span>{isExpanded ? "Hide Warning" : "Why Unverified?"}</span>
              {isExpanded ? (
                <ChevronUp className="h-3 w-3 ml-0.5" />
              ) : (
                <ChevronDown className="h-3 w-3 ml-0.5" />
              )}
            </button>
          )}
        </div>

        {/* Micro-Audit Unverified Breakdown */}
        {isExpanded && !compact && (
          <div className="mt-3 pt-3 border-t border-[#EF4444]/20 space-y-2 text-[11px] font-mono text-[#C2C7D4] animate-settle">
            <div className="rounded-lg bg-[#13161F] border border-white/6 p-2.5">
              <span className="text-[10px] uppercase text-[#8C93A5] block mb-1">
                Audit Result
              </span>
              <span className="text-[#EF4444] font-semibold text-xs">
                Zero Direct Tabular Matches
              </span>
              <p className="text-[10px] text-[#8C93A5] mt-1 font-sans">
                The synthesized response included a figure that could not be reconciled with certainty against structured table cells in the index.
              </p>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`animate-settle inline-flex items-center gap-2 rounded-md border border-white/8 bg-[#141418] px-2.5 py-1 text-xs text-[#8E8D8A] ${className}`}>
      <Info className="h-3.5 w-3.5 text-[#8E8D8A]" />
      <span>Status: {status}</span>
    </div>
  );
};
