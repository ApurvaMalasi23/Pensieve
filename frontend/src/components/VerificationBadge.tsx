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
        className={`animate-settle rounded-2xl border border-[#52B788]/25 bg-gradient-to-br from-[#12231A]/70 via-[#0E1A13]/50 to-[#0A120D]/40 backdrop-blur-xl p-4 text-[#52B788] shadow-[0_8px_24px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(82,183,136,0.12)] transition-all ${className}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <div className="flex h-4.5 w-4.5 shrink-0 items-center justify-center text-[#52B788] mt-0.5">
              <CheckCircle2 className="h-4.5 w-4.5 stroke-[1.8]" />
            </div>
            <div className="flex flex-col text-xs leading-relaxed">
              <span className="font-semibold text-[#F7F7F4] tracking-tight">
                Verified Against Source Table
              </span>
              {!compact && (
                <span className="text-[#52B788]/85 text-[11px] mt-0.5 font-light">
                  Figures matched cell-for-cell against extracted financial table cells.
                </span>
              )}
            </div>
          </div>

          {!compact && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              data-testid="inspect-proof-button"
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-mono text-[#52B788] bg-[#52B788]/10 hover:bg-[#52B788]/20 transition-all cursor-pointer shrink-0 border border-[#52B788]/25 shadow-xs"
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
        className={`animate-settle rounded-2xl border border-[#D4A373]/30 bg-gradient-to-br from-[#1F180F]/70 via-[#19130C]/50 to-[#120D08]/40 backdrop-blur-xl p-4 text-[#D4A373] shadow-[0_8px_24px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(212,163,115,0.12)] transition-all ${className}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <div className="flex h-4.5 w-4.5 shrink-0 items-center justify-center text-[#D4A373] mt-0.5">
              <ShieldAlert className="h-4.5 w-4.5 stroke-[1.8]" />
            </div>
            <div className="flex flex-col text-xs leading-relaxed max-w-xl">
              <span className="font-semibold text-[#F7F7F4] tracking-tight">
                Verified with Table Extraction Warning
              </span>
              <p className="mt-1 text-[11px] leading-normal text-[#D4A373] bg-[#0B0B0D]/80 rounded-xl px-3 py-2 border border-[#D4A373]/20 tabular-nums font-light">
                {reason || "The cited table was flagged for structural or OCR irregularities. Please verify against original PDF."}
              </p>
            </div>
          </div>

          {!compact && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              data-testid="inspect-proof-button"
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-mono text-[#D4A373] bg-[#D4A373]/10 hover:bg-[#D4A373]/20 transition-all cursor-pointer shrink-0 border border-[#D4A373]/25 shadow-xs"
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
        className={`animate-settle rounded-2xl border border-[#E06D6D]/30 bg-gradient-to-br from-[#1F1010]/70 via-[#180C0C]/50 to-[#120808]/40 backdrop-blur-xl p-4 text-[#E06D6D] shadow-[0_8px_24px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(224,109,109,0.12)] transition-all ${className}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <div className="flex h-4.5 w-4.5 shrink-0 items-center justify-center text-[#E06D6D] mt-0.5">
              <AlertOctagon className="h-4.5 w-4.5 stroke-[1.8]" />
            </div>
            <div className="flex flex-col text-xs leading-relaxed max-w-xl">
              <span className="font-semibold text-[#F7F7F4] tracking-tight">
                Unverified Numeric Figure
              </span>
              <p className="mt-1 text-[11px] leading-normal text-[#E06D6D]/90 bg-[#0B0B0D]/80 rounded-xl px-3 py-2 border border-[#E06D6D]/20 font-light">
                {reason || "This number was not located in any retrieved financial table. Verify against the source document directly before relying on this figure."}
              </p>
            </div>
          </div>

          {!compact && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              data-testid="inspect-proof-button"
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-mono text-[#E06D6D] bg-[#E06D6D]/10 hover:bg-[#E06D6D]/20 transition-all cursor-pointer shrink-0 border border-[#E06D6D]/25 shadow-xs"
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
