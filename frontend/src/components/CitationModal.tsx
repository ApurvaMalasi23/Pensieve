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
        className="rich-modal relative flex max-h-[90vh] w-full max-w-3xl flex-col rounded-2xl bg-[#181C28] border border-white/10 text-[#F1F3F9] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        data-testid="citation-modal"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/8 px-6 py-4 bg-[#181C28]">
          <div className="flex items-center gap-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#E59500]/15 text-[#E59500] text-xs font-mono font-semibold border border-[#E59500]/25">
              {citation.marker}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h3 id="citation-title" className="font-medium text-[#F1F3F9] text-sm md:text-base">
                  {citation.company_name || "Document Source"}
                </h3>
                {citation.fiscal_year && (
                  <span className="text-xs text-[#8C93A5] bg-white/6 border border-white/6 px-2 py-0.5 rounded font-mono tabular-nums">
                    FY {citation.fiscal_year}
                  </span>
                )}
                {isTable ? (
                  <span className="inline-flex items-center gap-1 text-[11px] bg-[#E59500]/10 text-[#E59500] border border-[#E59500]/20 px-2 py-0.5 rounded font-normal">
                    <TableIcon className="h-3 w-3" /> Table Excerpt
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[11px] bg-white/6 text-[#8C93A5] border border-white/6 px-2 py-0.5 rounded font-normal">
                    <FileText className="h-3 w-3" /> Narrative Excerpt
                  </span>
                )}
              </div>
              <p className="text-xs text-[#8C93A5] mt-0.5 tabular-nums">
                {citation.source_filename} — Page {citation.page_start}
                {citation.page_end !== citation.page_start && ` to ${citation.page_end}`}
                {citation.table_id && ` (${citation.table_id})`}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#8C93A5] hover:bg-white/5 hover:text-[#F1F3F9] transition-colors cursor-pointer"
            title="Close modal (Escape)"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Extraction Risk Warning Banner */}
        {isFlagged && (
          <div className="border-b border-[#F59E0B]/30 bg-[#F59E0B]/10 px-6 py-3 text-[#F59E0B]">
            <div className="flex items-start gap-2.5">
              <ShieldAlert className="h-4 w-4 shrink-0 text-[#F59E0B] mt-0.5 stroke-[1.8]" />
              <div className="text-xs leading-normal">
                <span className="font-semibold text-[#F59E0B]">Extraction Quality Notice: </span>
                <span>Pensieve flagged this table during parsing for potential structural or OCR anomalies.</span>
                {citation.risk_reasons && citation.risk_reasons.length > 0 && (
                  <ul className="mt-1.5 list-disc list-inside space-y-0.5 text-[11px] text-[#F59E0B]/90 tabular-nums">
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
        <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-[#13161F]">
          <div className="flex items-center justify-between text-xs text-[#8C93A5]">
            <span className="text-[11px] font-medium text-[#8C93A5] uppercase tracking-wider font-mono">
              Ground Truth Excerpt
            </span>
            <span className="text-[11px] text-[#585E70] tabular-nums font-mono">
              ID: {citation.chunk_id ? citation.chunk_id.slice(0, 12) : "N/A"}
            </span>
          </div>

          <div className="rounded-xl border border-white/8 bg-[#181C28] p-5 text-sm text-[#F1F3F9] overflow-x-auto">
            {isTable ? (
              <div className="prose prose-invert max-w-none text-xs text-[#F1F3F9]">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    table: ({ node, ...props }) => (
                      <div className="overflow-x-auto my-1 rounded-lg border border-white/10">
                        <table className="w-full text-left border-collapse text-xs tabular-nums" {...props} />
                      </div>
                    ),
                    thead: ({ node, ...props }) => (
                      <thead className="bg-[#181C28] text-[#F1F3F9] font-medium border-b border-white/10" {...props} />
                    ),
                    th: ({ node, ...props }) => (
                      <th className="px-3 py-2 border-r border-white/8 last:border-0 font-medium text-[#F1F3F9]" {...props} />
                    ),
                    td: ({ node, ...props }) => (
                      <td className="px-3 py-2 border-t border-r border-white/6 last:border-r-0 text-[11px] text-[#F1F3F9] tabular-nums" {...props} />
                    ),
                    tr: ({ node, ...props }) => (
                      <tr className="hover:bg-white/4 even:bg-white/2 transition-colors" {...props} />
                    ),
                    p: ({ node, ...props }) => (
                      <p className="mb-2 text-[#8E8D8A] leading-relaxed text-xs" {...props} />
                    ),
                  }}
                >
                  {citation.excerpt}
                </ReactMarkdown>
              </div>
            ) : (
              <p className="text-[#F0EFEA] whitespace-pre-wrap leading-relaxed text-xs max-w-prose">
                {citation.excerpt}
              </p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-white/8 px-6 py-3 bg-[#1C1C22] flex items-center justify-between text-xs text-[#8E8D8A]">
          <span className="text-[11px]">Cell-level table grounding active</span>
          <span className="text-[11px] font-mono text-[#5C5B58]">Press Esc to dismiss</span>
        </div>
      </div>
    </div>
  );
};
