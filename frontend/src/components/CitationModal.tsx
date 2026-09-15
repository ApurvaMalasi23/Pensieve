"use client";

import React, { useEffect } from "react";
import { Citation } from "@/types/api";
import { X, ShieldAlert, FileText, Table as TableIcon } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface CitationModalProps {
  citation: Citation | null;
  onClose: () => void;
}

export const CitationModal: React.FC<CitationModalProps> = ({ citation, onClose }) => {
  // Usability pass: Escape key closes modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    if (citation) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [citation, onClose]);

  if (!citation) return null;

  const isTable = Boolean(citation.table_id || citation.excerpt.includes("|"));
  const isFlagged = Boolean(citation.risk_flag);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="citation-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 animate-settle"
      onClick={onClose}
    >
      <div
        className="rich-modal relative flex max-h-[90vh] w-full max-w-3xl flex-col rounded-2xl bg-[#121216] border border-white/[0.07] text-[#F7F7F4] shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_24px_60px_rgba(0,0,0,0.85)] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        data-testid="citation-modal"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/[0.04] px-6 py-4 bg-[#121216]">
          <div className="flex items-center gap-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#CBB282]/15 text-[#CBB282] text-xs font-mono font-semibold border border-[#CBB282]/25">
              {citation.marker}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h3 id="citation-title" className="font-serif font-medium text-[#F7F7F4] text-base md:text-lg tracking-[0.01em]">
                  {citation.company_name || "Document Source"}
                </h3>
                {citation.fiscal_year && (
                  <span className="text-xs text-[#82807A] bg-white/[0.04] border border-white/[0.05] px-2 py-0.5 rounded font-mono tabular-nums">
                    FY {citation.fiscal_year}
                  </span>
                )}
                {isTable ? (
                  <span className="inline-flex items-center gap-1 text-[11px] bg-[#CBB282]/10 text-[#CBB282] border border-[#CBB282]/20 px-2 py-0.5 rounded font-normal">
                    <TableIcon className="h-3 w-3" /> Table Excerpt
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[11px] bg-white/[0.04] text-[#82807A] border border-white/[0.05] px-2 py-0.5 rounded font-normal">
                    <FileText className="h-3 w-3" /> Narrative Excerpt
                  </span>
                )}
              </div>
              <p className="text-xs text-[#82807A] mt-0.5 tabular-nums font-mono">
                {citation.source_filename} — Page {citation.page_start}
                {citation.page_end !== citation.page_start && ` to ${citation.page_end}`}
                {citation.table_id && ` (${citation.table_id})`}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#82807A] hover:bg-white/[0.05] hover:text-[#F7F7F4] transition-colors cursor-pointer"
            title="Close modal (Escape)"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Extraction Risk Warning Banner */}
        {isFlagged && (
          <div className="border-b border-[#D4A373]/30 bg-[#D4A373]/10 px-6 py-3 text-[#D4A373]">
            <div className="flex items-start gap-2.5">
              <ShieldAlert className="h-4 w-4 shrink-0 text-[#D4A373] mt-0.5 stroke-[1.8]" />
              <div className="text-xs leading-normal">
                <span className="font-semibold text-[#D4A373]">Extraction Quality Notice: </span>
                <span>Pensieve flagged this table during parsing for potential structural or OCR anomalies.</span>
                {citation.risk_reasons && citation.risk_reasons.length > 0 && (
                  <ul className="mt-1.5 list-disc list-inside space-y-0.5 text-[11px] text-[#D4A373]/90 tabular-nums">
                    {citation.risk_reasons.map((reason, idx) => (
                      <li key={idx}>{reason}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-[#0B0B0D]">
          <div className="flex items-center justify-between text-xs text-[#82807A]">
            <span className="text-[10px] font-medium text-[#82807A] uppercase tracking-[0.2em] font-mono">
              Ground Truth Excerpt
            </span>
            <span className="text-[10px] text-[#4A4944] tabular-nums font-mono">
              ID: {citation.chunk_id ? citation.chunk_id.slice(0, 12) : "N/A"}
            </span>
          </div>

          <div className="luxury-ledger-container p-1">
            {isTable ? (
              <div className="overflow-x-auto">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    table: ({ children }) => (
                      <table className="luxury-ledger">
                        {children}
                      </table>
                    ),
                    thead: ({ children }) => <thead>{children}</thead>,
                    th: ({ children }) => <th>{children}</th>,
                    tbody: ({ children }) => <tbody>{children}</tbody>,
                    tr: ({ children }) => <tr>{children}</tr>,
                    td: ({ children }) => <td>{children}</td>,
                    p: ({ children }) => (
                      <p className="mb-2 text-[#82807A] leading-relaxed text-xs">{children}</p>
                    ),
                  }}
                >
                  {citation.excerpt}
                </ReactMarkdown>
              </div>
            ) : (
              <p className="text-[#CDCBC4] whitespace-pre-wrap leading-relaxed text-xs max-w-prose font-sans p-4">
                {citation.excerpt}
              </p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-white/[0.04] px-6 py-3 bg-[#121216] flex items-center justify-between text-xs text-[#82807A]">
          <span className="text-[11px] font-mono">Cell-level table grounding active</span>
          <span className="text-[11px] font-mono text-[#4A4944]">Press Esc to dismiss</span>
        </div>
      </div>
    </div>
  );
};
