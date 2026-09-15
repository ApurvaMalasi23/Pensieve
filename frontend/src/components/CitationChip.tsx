"use client";

import React, { useState, useRef, useEffect } from "react";
import { Citation } from "@/types/api";
import { formatFiscalYear } from "@/lib/api";
import { ShieldAlert, Table, FileText, ExternalLink, ChevronRight } from "lucide-react";

interface CitationChipProps {
  citation: Citation;
  onClick: (citation: Citation) => void;
}

export const CitationChip: React.FC<CitationChipProps> = ({ citation, onClick }) => {
  const [isOpen, setIsOpen] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const isTable = Boolean(citation.table_id || citation.excerpt.includes("|"));
  const isFlagged = Boolean(citation.risk_flag);

  const handleMouseEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setIsOpen(true);
    }, 120);
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setIsOpen(false);
    }, 150);
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        onClick={() => onClick(citation)}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setIsOpen(false)}
        data-testid={`citation-chip-${citation.marker.replace(/[^a-zA-Z0-9]/g, "")}`}
        className={`group inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition-all cursor-pointer select-none ${
          isFlagged
            ? "border-[#D4A373]/35 bg-[#D4A373]/10 text-[#D4A373] hover:bg-[#D4A373]/18"
            : isOpen
            ? "border-[#CBB282]/45 bg-[#17181D] text-[#F7F7F4] shadow-[0_0_16px_rgba(203,178,130,0.18)]"
            : "border-white/8 bg-[#121216] text-[#F7F7F4] hover:bg-[#17181D] hover:border-white/16"
        }`}
        title="Hover for instant source excerpt or click to open full table modal"
      >
        <span className="font-mono text-[#CBB282] font-semibold text-[11px]">{citation.marker}</span>
        <span className="font-normal text-[#F7F7F4] truncate max-w-[170px] text-[11.5px]">
          {citation.company_name || citation.source_filename.replace(/\.pdf$/i, "")}
        </span>
        {citation.fiscal_year && (
          <span className="text-[10px] text-[#82807A] tabular-nums font-mono">{formatFiscalYear(citation.fiscal_year)}</span>
        )}
        <span className="text-[10px] text-[#82807A] tabular-nums font-mono">p.{citation.page_start}</span>

        {isFlagged ? (
          <span className="inline-flex items-center gap-1 rounded bg-[#D4A373]/20 px-1 py-0.2 text-[10px] font-medium text-[#D4A373]">
            <ShieldAlert className="h-2.5 w-2.5 stroke-[1.8]" /> Flagged
          </span>
        ) : isTable ? (
          <Table className="h-3 w-3 text-[#82807A] stroke-[1.5]" />
        ) : (
          <FileText className="h-3 w-3 text-[#82807A] stroke-[1.5]" />
        )}
      </button>

      {/* Instant Provenance Popover (Rich Black elevation) */}
      {isOpen && (
        <div
          role="tooltip"
          className="absolute bottom-full left-0 mb-2 w-80 rounded-xl rich-modal p-3.5 shadow-2xl z-40 animate-settle pointer-events-none"
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[#CBB282] font-bold text-xs">
                {citation.marker}
              </span>
              <div>
                <span className="font-medium text-xs text-[#F7F7F4] block leading-tight">
                  {citation.company_name || citation.source_filename}
                </span>
                <div className="text-[10px] text-[#82807A] flex items-center gap-1.5 font-mono">
                  <span>p.{citation.page_start}</span>
                  {citation.table_id && <span>• {citation.table_id}</span>}
                </div>
              </div>
            </div>

            {/* Type badge */}
            {isTable ? (
              <span className="inline-flex items-center gap-1 rounded bg-[#CBB282]/10 border border-[#CBB282]/20 px-1.5 py-0.5 text-[10px] font-mono text-[#CBB282]">
                <Table className="h-2.5 w-2.5" /> Table
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded bg-white/6 border border-white/6 px-1.5 py-0.5 text-[10px] font-mono text-[#82807A]">
                <FileText className="h-2.5 w-2.5" /> Narrative
              </span>
            )}
          </div>

          {/* Anomaly banner if flagged */}
          {isFlagged && (
            <div className="mb-2 flex items-center gap-1.5 rounded-lg border border-[#D4A373]/30 bg-[#D4A373]/10 px-2 py-1 text-[10px] text-[#D4A373]">
              <ShieldAlert className="h-3 w-3 shrink-0" />
              <span className="font-mono">
                {citation.risk_reasons?.[0] || "Flagged OCR / structure irregularity."}
              </span>
            </div>
          )}

          {/* Clean Source Excerpt Snippet */}
          <div className="mb-3 max-h-32 overflow-y-auto rounded-lg bg-[#121216] border border-white/6 p-2.5 text-[11px] font-mono leading-relaxed text-[#CDCBC4] scrollbar-thin">
            <p className="whitespace-pre-wrap line-clamp-4 select-text">
              {citation.excerpt.trim()}
            </p>
          </div>

          {/* Interactive Modal Action */}
          <button
            onClick={() => {
              setIsOpen(false);
              onClick(citation);
            }}
            className="flex w-full items-center justify-between rounded-lg bg-white/4 hover:bg-[#CBB282]/15 hover:text-[#CBB282] border border-white/6 hover:border-[#CBB282]/30 px-2.5 py-1.5 text-[11px] text-[#82807A] transition-all cursor-pointer"
          >
            <span className="flex items-center gap-1.5 font-medium">
              <ExternalLink className="h-3 w-3" /> Inspect full table & bounding box
            </span>
            <ChevronRight className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
};
