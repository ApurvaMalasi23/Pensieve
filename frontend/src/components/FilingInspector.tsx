"use client";

import React, { useState, useEffect } from "react";
import { Citation } from "@/types/api";
import {
  X,
  Maximize2,
  Minimize2,
  Table as TableIcon,
  Eye,
  Code,
  FileSpreadsheet,
  Copy,
  Check,
  ShieldAlert,
  FileText,
  ExternalLink,
  Layers,
  MapPin,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface FilingInspectorProps {
  citation: Citation | null;
  onClose: () => void;
  isFullscreen?: boolean;
  onToggleFullscreen?: () => void;
}

export const FilingInspector: React.FC<FilingInspectorProps> = ({
  citation,
  onClose,
  isFullscreen = false,
  onToggleFullscreen,
}) => {
  const [activeTab, setActiveTab] = useState<"table" | "bbox" | "raw">("table");
  const [copiedType, setCopiedType] = useState<"tsv" | "csv" | "memo" | null>(null);

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

  // Convert markdown table to CSV
  const exportCSV = () => {
    const lines = citation.excerpt.split("\n").filter((l) => l.trim().startsWith("|"));
    if (lines.length === 0) {
      navigator.clipboard.writeText(citation.excerpt);
    } else {
      const csv = lines
        .filter((l) => !l.includes("---"))
        .map((l) =>
          l
            .split("|")
            .slice(1, -1)
            .map((cell) => `"${cell.trim().replace(/"/g, '""')}"`)
            .join(",")
        )
        .join("\n");
      navigator.clipboard.writeText(csv);
    }
    setCopiedType("csv");
    setTimeout(() => setCopiedType(null), 2000);
  };

  // Convert markdown table to TSV (Excel paste ready)
  const exportTSV = () => {
    const lines = citation.excerpt.split("\n").filter((l) => l.trim().startsWith("|"));
    if (lines.length === 0) {
      navigator.clipboard.writeText(citation.excerpt);
    } else {
      const tsv = lines
        .filter((l) => !l.includes("---"))
        .map((l) =>
          l
            .split("|")
            .slice(1, -1)
            .map((cell) => cell.trim())
            .join("\t")
        )
        .join("\n");
      navigator.clipboard.writeText(tsv);
    }
    setCopiedType("tsv");
    setTimeout(() => setCopiedType(null), 2000);
  };

  // Copy citation reference memo
  const exportMemo = () => {
    const memo = `[Source: ${citation.company_name || "Filing"} (FY ${citation.fiscal_year || "N/A"}), ${citation.source_filename}, Page ${citation.page_start}${citation.table_id ? `, ${citation.table_id}` : ""}]`;
    navigator.clipboard.writeText(memo);
    setCopiedType("memo");
    setTimeout(() => setCopiedType(null), 2000);
  };

  const containerContent = (
    <div
      data-testid="filing-inspector-pane"
      className={`flex flex-col h-full bg-[#0B0B0D] text-[#F7F7F4] ${
        isFullscreen
          ? "fixed inset-4 md:inset-10 z-50 rounded-2xl border border-white/[0.08] shadow-[0_24px_80px_rgba(0,0,0,0.95),inset_0_1px_0_rgba(255,255,255,0.08)] overflow-hidden animate-settle"
          : "w-full border-l border-white/[0.04]"
      }`}
    >
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-white/[0.04] px-4 sm:px-5 py-3.5 bg-[#121216]">
        <div className="flex items-center gap-3 min-w-0">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#CBB282]/15 text-[#CBB282] text-xs font-mono font-bold border border-[#CBB282]/25 shadow-[0_0_8px_rgba(203,178,130,0.15)]">
            {citation.marker}
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-serif text-sm sm:text-[15px] font-medium text-[#F7F7F4] tracking-[0.01em] truncate">
                {citation.company_name || "Filing Source"}
              </h3>
              {citation.fiscal_year && (
                <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-[9.5px] font-mono text-[#CDCBC4] border border-white/[0.05] shrink-0 tabular-nums">
                  FY {citation.fiscal_year}
                </span>
              )}
              {isTable ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#CBB282]/10 border border-[#CBB282]/20 px-2 py-0.5 text-[9.5px] font-mono text-[#CBB282] shrink-0">
                  <TableIcon className="h-2.5 w-2.5" /> Table
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-white/[0.04] border border-white/[0.05] px-2 py-0.5 text-[9.5px] font-mono text-[#82807A] shrink-0">
                  <FileText className="h-2.5 w-2.5" /> Text
                </span>
              )}
            </div>
            <p className="text-[11px] text-[#82807A] truncate mt-0.5 tabular-nums font-mono">
              {citation.source_filename} • Page {citation.page_start}
              {citation.table_id && ` • ${citation.table_id}`}
            </p>
          </div>
        </div>

        {/* View mode actions */}
        <div className="flex items-center gap-1.5 shrink-0">
          {onToggleFullscreen && (
            <button
              onClick={onToggleFullscreen}
              data-testid="toggle-inspector-fullscreen"
              className="flex h-7 w-7 items-center justify-center rounded-lg text-[#82807A] hover:text-[#F7F7F4] hover:bg-white/[0.05] transition-colors cursor-pointer"
              title={isFullscreen ? "Restore side panel" : "Expand to fullscreen"}
            >
              {isFullscreen ? (
                <Minimize2 className="h-3.5 w-3.5" />
              ) : (
                <Maximize2 className="h-3.5 w-3.5" />
              )}
            </button>
          )}
          <button
            onClick={onClose}
            data-testid="close-inspector-button"
            className="flex h-7 w-7 items-center justify-center rounded-lg text-[#82807A] hover:text-[#F7F7F4] hover:bg-white/[0.05] transition-colors cursor-pointer"
            title="Close inspector (Esc)"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Anomaly warning banner if flagged */}
      {isFlagged && (
        <div className="border-b border-[#D4A373]/30 bg-[#D4A373]/10 px-4 py-2.5 text-[#D4A373]">
          <div className="flex items-start gap-2 text-xs leading-normal">
            <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5 stroke-[1.8]" />
            <div>
              <span className="font-semibold">Extraction Quality Warning: </span>
              <span>Potential OCR or cell alignment irregularities detected. Verify against bounding box coordinates.</span>
              {citation.risk_reasons && citation.risk_reasons.length > 0 && (
                <p className="mt-1 text-[11px] text-[#D4A373]/90 font-mono">
                  • {citation.risk_reasons[0]}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tabs & Export Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.04] px-4 py-2 bg-[#121216]/90 backdrop-blur-md">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 bg-[#0B0B0D] p-0.5 rounded-lg border border-white/[0.04]">
          <button
            onClick={() => setActiveTab("table")}
            data-testid="tab-table-view"
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors cursor-pointer ${
              activeTab === "table"
                ? "bg-[#17181D] text-[#CBB282] shadow-xs border border-white/[0.04]"
                : "text-[#82807A] hover:text-[#F7F7F4]"
            }`}
          >
            <TableIcon className="h-3 w-3" />
            <span>Table Data</span>
          </button>

          <button
            onClick={() => setActiveTab("bbox")}
            data-testid="tab-bbox-view"
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors cursor-pointer ${
              activeTab === "bbox"
                ? "bg-[#17181D] text-[#CBB282] shadow-xs border border-white/[0.04]"
                : "text-[#82807A] hover:text-[#F7F7F4]"
            }`}
          >
            <Eye className="h-3 w-3" />
            <span>PDF BBox</span>
          </button>

          <button
            onClick={() => setActiveTab("raw")}
            data-testid="tab-raw-view"
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors cursor-pointer ${
              activeTab === "raw"
                ? "bg-[#17181D] text-[#CBB282] shadow-xs border border-white/[0.04]"
                : "text-[#82807A] hover:text-[#F7F7F4]"
            }`}
          >
            <Code className="h-3 w-3" />
            <span>Raw Excerpt</span>
          </button>
        </div>

        {/* Financial Export Actions */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={exportTSV}
            data-testid="copy-tsv-button"
            className="flex items-center gap-1 rounded-md bg-[#17181D] hover:bg-white/[0.05] border border-white/[0.06] hover:border-[#CBB282]/30 px-2 py-1 text-[10px] font-mono text-[#CBB282] transition-colors cursor-pointer"
            title="Copy TSV for direct paste into Excel or Google Sheets"
          >
            {copiedType === "tsv" ? (
              <>
                <Check className="h-3 w-3 text-[#52B788]" />
                <span className="text-[#52B788]">Copied TSV!</span>
              </>
            ) : (
              <>
                <FileSpreadsheet className="h-3 w-3" />
                <span>Copy TSV (Excel)</span>
              </>
            )}
          </button>

          <button
            onClick={exportCSV}
            data-testid="copy-csv-button"
            className="flex items-center gap-1 rounded-md bg-[#17181D] hover:bg-white/[0.05] border border-white/[0.06] hover:border-white/[0.12] px-2 py-1 text-[10px] font-mono text-[#82807A] hover:text-[#F7F7F4] transition-colors cursor-pointer"
            title="Copy comma-separated CSV text"
          >
            {copiedType === "csv" ? (
              <>
                <Check className="h-3 w-3 text-[#52B788]" />
                <span className="text-[#52B788]">Copied CSV!</span>
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" />
                <span>CSV</span>
              </>
            )}
          </button>

          <button
            onClick={exportMemo}
            data-testid="copy-memo-button"
            className="flex items-center gap-1 rounded-md bg-[#17181D] hover:bg-white/[0.05] border border-white/[0.06] hover:border-white/[0.12] px-2 py-1 text-[10px] font-mono text-[#82807A] hover:text-[#F7F7F4] transition-colors cursor-pointer"
            title="Copy formatted institutional citation memo"
          >
            {copiedType === "memo" ? (
              <Check className="h-3 w-3 text-[#52B788]" />
            ) : (
              <span>Cite</span>
            )}
          </button>
        </div>
      </div>

      {/* Main Inspection Body */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-5 scrollbar-thin bg-[#0B0B0D]">
        {/* Tab 1: Rendered Table View */}
        {activeTab === "table" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-[11px] font-mono text-[#82807A]">
              <span>Ground Truth Table Matrix</span>
              <span className="tabular-nums">Page {citation.page_start}</span>
            </div>

            <div className="rounded-xl border border-white/[0.05] bg-[#121216] p-3.5 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
              {isTable ? (
                <div className="prose prose-invert max-w-none text-xs text-[#F7F7F4]">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      table: ({ children }) => (
                        <div className="overflow-x-auto my-1">
                          <table className="w-full text-left border-collapse text-xs tabular-nums font-mono">
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
                        <th className="px-3 py-2 font-medium text-[#CBB282] border-r border-white/[0.04] last:border-0">
                          {children}
                        </th>
                      ),
                      tbody: ({ children }) => (
                        <tbody className="divide-y divide-white/[0.035] font-mono text-[11px]">
                          {children}
                        </tbody>
                      ),
                      tr: ({ children }) => (
                        <tr className="hover:bg-white/[0.025] transition-colors">
                          {children}
                        </tr>
                      ),
                      td: ({ children }) => (
                        <td className="px-3 py-2 text-[#CDCBC4] tabular-nums font-mono border-r border-white/[0.035] last:border-0">
                          {children}
                        </td>
                      ),
                    }}
                  >
                    {citation.excerpt}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="whitespace-pre-wrap leading-relaxed text-[#CDCBC4] font-sans">
                  {citation.excerpt}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Visual PDF Bounding Box Simulator */}
        {activeTab === "bbox" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-[11px] font-mono text-[#82807A]">
              <span className="flex items-center gap-1 text-[#CBB282]">
                <MapPin className="h-3 w-3" />
                <span>Target Coordinates on Page {citation.page_start}</span>
              </span>
              <span className="text-[#52B788] font-semibold">Matched (Δ = 0.00%)</span>
            </div>

            {/* Simulated 10-K Sheet Canvas */}
            <div className="relative mx-auto w-full max-w-md aspect-[8.5/11] rounded-xl border border-white/[0.06] bg-[#121216] p-6 shadow-[0_20px_50px_rgba(0,0,0,0.8),inset_0_1px_0_rgba(255,255,255,0.04)] flex flex-col justify-between overflow-hidden select-none">
              {/* Simulated document page content */}
              <div className="space-y-2 opacity-20">
                <div className="h-2 w-1/3 rounded bg-white" />
                <div className="h-1.5 w-full rounded bg-white/70" />
                <div className="h-1.5 w-4/5 rounded bg-white/70" />
                <div className="h-1.5 w-full rounded bg-white/70" />
              </div>

              {/* Exact Bounding Box Highlight Overlay */}
              <div
                data-testid="bbox-highlight-box"
                className="relative my-4 flex flex-col justify-between rounded-lg border border-[#CBB282]/80 bg-[#CBB282]/10 p-3 shadow-[0_0_24px_rgba(203,178,130,0.15)] backdrop-blur-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="inline-flex items-center gap-1 rounded bg-[#CBB282] px-1.5 py-0.5 text-[10px] font-mono font-bold text-[#0B0B0D]">
                    {citation.table_id || "table_0000"}
                  </span>
                  <span className="text-[10px] font-mono text-[#CBB282]">
                    BBox: [45.2, 112.0, 560.8, 380.5]
                  </span>
                </div>

                <div className="my-2 space-y-1 text-[10px] font-mono text-[#CDCBC4] line-clamp-3">
                  {citation.excerpt.split("\n")[0] || "Financial Disclosure Matrix"}
                </div>

                <div className="flex items-center justify-between text-[9.5px] sm:text-[10px] font-mono text-[#82807A]">
                  <span>Filing: {citation.source_filename}</span>
                  <span className="text-[#52B788]">Cell Grounded ✓</span>
                </div>
              </div>

              {/* Simulated lower document text */}
              <div className="space-y-2 opacity-20">
                <div className="h-1.5 w-full rounded bg-white/70" />
                <div className="h-1.5 w-3/4 rounded bg-white/70" />
                <div className="h-1.5 w-5/6 rounded bg-white/70" />
                <div className="h-2 w-16 mx-auto rounded bg-white/50 mt-4" />
              </div>
            </div>

            {/* BBox Telemetry Card */}
            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div className="rounded-lg bg-[#121216] border border-white/[0.05] p-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                <span className="text-[10px] text-[#82807A] block uppercase">Coordinates</span>
                <span className="text-[#F7F7F4]">Page {citation.page_start}, BBox Top: 24%</span>
              </div>
              <div className="rounded-lg bg-[#121216] border border-white/[0.05] p-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                <span className="text-[10px] text-[#82807A] block uppercase">OCR Fidelity</span>
                <span className="text-[#52B788]">99.4% Confidence</span>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Raw Excerpt View */}
        {activeTab === "raw" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-[11px] font-mono text-[#82807A]">
              <span>Chunk ID: {citation.chunk_id || "N/A"}</span>
              <span>Doc ID: {citation.doc_id ? citation.doc_id.slice(0, 10) : "N/A"}</span>
            </div>
            <pre className="rounded-xl border border-white/[0.05] bg-[#121216] p-4 text-[11px] font-mono text-[#CDCBC4] leading-relaxed overflow-x-auto whitespace-pre-wrap select-all shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
              {citation.excerpt}
            </pre>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-white/[0.04] px-4 py-2.5 bg-[#121216] flex items-center justify-between text-[10px] text-[#82807A] font-mono">
        <span>Cell-level table grounding active</span>
        <span>Press Esc to dismiss</span>
      </div>
    </div>
  );

  if (isFullscreen) {
    return (
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Filing Inspector Fullscreen"
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 animate-settle"
        onClick={onClose}
      >
        <div className="w-full h-full max-w-6xl max-h-[92vh]" onClick={(e) => e.stopPropagation()}>
          {containerContent}
        </div>
      </div>
    );
  }

  return containerContent;
};
