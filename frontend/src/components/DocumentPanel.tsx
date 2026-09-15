"use client";

import React, { useState } from "react";
import { DocumentItem } from "@/types/api";
import { deleteDocument, formatFiscalYear } from "@/lib/api";
import {
  FileText,
  Layers,
  Calendar,
  Trash2,
  AlertCircle,
  ShieldAlert,
  Check,
  Loader2,
  X,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
} from "lucide-react";

interface DocumentPanelProps {
  documents: DocumentItem[];
  selectedDoc: DocumentItem | null;
  onSelectDoc: (doc: DocumentItem | null) => void;
  onOpenUpload?: () => void;
  isLoading: boolean;
  onDocumentDeleted?: (docId: string) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  isShowcaseMode?: boolean;
}

export const DocumentPanel: React.FC<DocumentPanelProps> = ({
  documents,
  selectedDoc,
  onSelectDoc,
  onOpenUpload,
  onDocumentDeleted,
  isLoading,
  isCollapsed = false,
  onToggleCollapse,
  isShowcaseMode = true,
}) => {
  const [docToDelete, setDocToDelete] = useState<DocumentItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const filteredDocuments = documents.filter((d) =>
    searchQuery.trim() === ""
      ? true
      : d.company_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (d.fiscal_year && d.fiscal_year.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const handleDeleteConfirm = async () => {
    if (!docToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);

    try {
      const res = await deleteDocument(docToDelete.doc_id);
      if (res.deleted) {
        // Reset scope if the deleted doc was currently selected
        if (selectedDoc?.doc_id === docToDelete.doc_id) {
          onSelectDoc(null);
        }
        onDocumentDeleted?.(docToDelete.doc_id);
        setDocToDelete(null);
      } else {
        setDeleteError("Deletion did not return a success confirmation.");
      }
    } catch (err: any) {
      setDeleteError(err.message || "Failed to delete document from backend.");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      {isCollapsed ? (
        <aside
          data-testid="document-panel-collapsed"
          className="flex h-full w-full flex-col items-center justify-between bg-[#0D0F14] py-4 px-1.5 border-r border-white/[0.06] text-[#F1F3F9]"
        >
          <div className="flex flex-col items-center gap-3 w-full">
            {/* Expand toggle */}
            {onToggleCollapse && (
              <button
                onClick={onToggleCollapse}
                data-testid="expand-sidebar-button"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-[#8C93A5] hover:text-[#F1F3F9] hover:bg-white/[0.06] transition-colors cursor-pointer"
                title="Expand catalog sidebar (⌘\)"
              >
                <PanelLeftOpen className="h-4 w-4" />
              </button>
            )}

            {/* Fixed Catalog Indicator */}
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#CBB282]/30 bg-[#CBB282]/10 text-[#CBB282]"
              title="Showcase Mode (Fixed Catalog)"
            >
              <Layers className="h-4 w-4" />
            </div>

            <div className="h-px w-6 bg-white/10 my-0.5" />

            {/* All filings scope icon button */}
            <button
              onClick={() => onSelectDoc(null)}
              data-testid="filter-all-collapsed"
              className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors cursor-pointer border ${
                selectedDoc === null
                  ? "bg-[#CBB282]/15 text-[#CBB282] border-[#CBB282]/30 shadow-[0_0_12px_rgba(203,178,130,0.18)]"
                  : "border-transparent text-[#82807A] hover:bg-white/[0.06] hover:text-[#F7F7F4]"
              }`}
              title="Search all filings (Cross-comparison)"
            >
              <Layers className="h-4 w-4" />
            </button>

            {/* Document list initials icons */}
            <div className="flex flex-col items-center gap-1.5 w-full mt-1">
              {documents.map((doc) => {
                const isSelected = selectedDoc?.doc_id === doc.doc_id;
                const initials = doc.company_name.substring(0, 2).toUpperCase();
                return (
                  <button
                    key={doc.doc_id}
                    onClick={() => onSelectDoc(doc)}
                    data-testid={`document-item-collapsed-${doc.doc_id}`}
                    className={`flex h-8 w-8 items-center justify-center rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer border ${
                      isSelected
                        ? "bg-[#CBB282]/20 text-[#CBB282] border-[#CBB282]/40 shadow-[0_0_12px_rgba(203,178,130,0.22)]"
                        : "border-white/[0.06] bg-white/[0.02] text-[#82807A] hover:bg-white/[0.06] hover:text-[#F7F7F4]"
                    }`}
                    title={`${doc.company_name} (FY ${doc.fiscal_year})`}
                  >
                    {initials}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Bottom count indicator */}
          <div
            className="text-[10px] font-mono text-[#8C93A5] tabular-nums select-none"
            title={`${documents.length} filings indexed`}
          >
            {documents.length}
          </div>
        </aside>
      ) : (
        <aside
          data-testid="document-panel"
          className="flex h-full w-full flex-col bg-[#0B0B0D]/94 backdrop-blur-2xl p-4 border-r border-white/[0.04] text-[#F7F7F4]"
        >
          {/* Header & Status */}
          <div className="flex items-center justify-between border-b border-white/[0.04] pb-3.5">
            <div>
              <h2 className="font-serif text-[15px] tracking-[0.02em] font-medium text-[#F7F7F4]">
                Filings Catalog
              </h2>
              <span className="text-[10px] text-[#82807A] font-mono tracking-wider uppercase tabular-nums">
                {documents.length} {documents.length === 1 ? "dossier" : "dossiers"} indexed
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span
                data-testid="showcase-catalog-badge"
                className="rounded-full bg-[#CBB282]/10 border border-[#CBB282]/25 px-2.5 py-0.5 text-[10px] font-mono tracking-wider uppercase text-[#CBB282]"
              >
                Showcase Catalog
              </span>
              {onToggleCollapse && (
                <button
                  onClick={onToggleCollapse}
                  data-testid="collapse-sidebar-button"
                  className="rounded-lg p-1.5 text-[#82807A] hover:bg-white/[0.06] hover:text-[#F7F7F4] transition-colors cursor-pointer"
                  title="Collapse Sidebar"
                >
                  <PanelLeftClose className="h-3.5 w-3.5 stroke-[1.8]" />
                </button>
              )}
            </div>
          </div>

          {/* Search Box */}
          <div className="pt-3 pb-1">
            <div className="relative flex items-center">
              <Search className="absolute left-3 h-3.5 w-3.5 text-[#82807A]/70 pointer-events-none stroke-[1.5]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search catalog filings..."
                data-testid="search-catalog-input"
                className="w-full rounded-xl border border-white/[0.05] bg-white/[0.02] pl-8.5 pr-8 py-1.5 text-xs text-[#F7F7F4] placeholder-[#4A4944] transition-all duration-200 focus:border-[#CBB282]/40 focus:bg-white/[0.04] focus:shadow-[0_0_16px_rgba(203,178,130,0.12)] outline-none font-sans"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 text-[#82807A] hover:text-[#F7F7F4] p-0.5"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>

          {/* Scope Filter Controls */}
          <div className="py-2.5">
            <button
              onClick={() => onSelectDoc(null)}
              data-testid="filter-all-documents"
              className={`flex w-full items-center justify-between rounded-xl px-3.5 py-2.5 text-xs transition-all duration-200 cursor-pointer border ${
                selectedDoc === null
                  ? "bg-gradient-to-r from-[#CBB282]/15 to-[#CBB282]/5 text-[#F7F7F4] font-medium border-[#CBB282]/30 shadow-[0_0_16px_rgba(203,178,130,0.12),inset_0_1px_0_rgba(255,255,255,0.06)]"
                  : "border-white/[0.04] bg-white/[0.02] text-[#82807A] hover:bg-white/[0.05] hover:text-[#F7F7F4]"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <Layers className="h-3.5 w-3.5 text-[#CBB282]" />
                <span className="tracking-wide">All filings (Cross-compare)</span>
              </span>
              {selectedDoc === null && (
                <span className="text-[10px] bg-[#CBB282]/20 text-[#CBB282] px-2 py-0.5 rounded-full font-mono tracking-widest uppercase border border-[#CBB282]/30 font-semibold">
                  Active
                </span>
              )}
            </button>
          </div>

          {/* Inline Error Banner if Deletion Failed */}
          {deleteError && (
            <div className="mb-3 rounded-xl border border-[#EF4444]/30 bg-[#EF4444]/10 p-2.5 text-xs text-[#EF4444] flex items-start justify-between gap-2">
              <div className="flex items-center gap-1.5">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{deleteError}</span>
              </div>
              <button onClick={() => setDeleteError(null)} className="text-[#EF4444]/70 hover:text-[#EF4444]">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {/* Document List */}
          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
            {isLoading && documents.length === 0 ? (
              <div className="py-8 text-center text-xs text-[#8C93A5] animate-skeleton font-serif italic">
                Chargement des rapports...
              </div>
            ) : documents.length === 0 ? (
              <div
                data-testid="empty-catalog-state"
                className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 p-6 text-center text-[#8C93A5] mt-4 bg-white/[0.02]"
              >
                <FileText className="h-6 w-6 text-[#585E70] mb-2 stroke-[1.5]" />
                <p className="font-serif text-sm font-medium text-[#F1F3F9]">No filings found</p>
                <p className="text-[11px] text-[#8C93A5] mt-1 font-light">
                  Showcase catalog is currently connecting to index.
                </p>
              </div>
            ) : (
              filteredDocuments.map((doc) => {
                const isSelected = selectedDoc?.doc_id === doc.doc_id;

                return (
                  <div
                    key={doc.doc_id}
                    onClick={() => onSelectDoc(isSelected ? null : doc)}
                    data-testid={`document-item-${doc.doc_id.slice(0, 8)}`}
                    className={`group relative cursor-pointer rounded-2xl border p-4 transition-all duration-200 ${
                      isSelected
                        ? "border-[#CBB282]/40 bg-gradient-to-br from-[#1A1812] via-[#141419] to-[#101014] shadow-[inset_0_0_24px_rgba(203,178,130,0.08),0_6px_24px_rgba(0,0,0,0.6)]"
                        : "border-white/[0.04] bg-[#121216]/60 hover:border-white/[0.10] hover:bg-[#17181D]/80 shadow-[0_4px_16px_rgba(0,0,0,0.3)]"
                    }`}
                  >
                    {/* Active jewel left blade */}
                    {isSelected && (
                      <div className="absolute left-0 top-3.5 bottom-3.5 w-1 rounded-r-full bg-[#CBB282] shadow-[0_0_10px_#CBB282]" />
                    )}

                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-serif text-[13.5px] font-medium text-[#F7F7F4] group-hover:text-[#CBB282] transition-colors line-clamp-1 tracking-[0.01em]">
                        {doc.company_name}
                      </h4>
                      
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-[10px] font-mono text-[#CDCBC4] tabular-nums border border-white/[0.05]">
                          {formatFiscalYear(doc.fiscal_year)}
                        </span>

                        {/* Quiet Destructive Delete Affordance (Hover/Focus Only - Hidden in Showcase Mode) */}
                        {!isShowcaseMode && (
                          <button
                            type="button"
                            data-testid={`delete-doc-button-${doc.doc_id.slice(0, 8)}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setDocToDelete(doc);
                            }}
                            className="opacity-0 group-hover:opacity-100 focus:opacity-100 rounded p-1 text-[#8C93A5] hover:bg-[#EF4444]/15 hover:text-[#EF4444] transition-all cursor-pointer"
                            title={`Delete ${doc.company_name} filing`}
                            aria-label={`Delete ${doc.company_name}`}
                          >
                            <Trash2 className="h-3.5 w-3.5 stroke-[1.5]" />
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="mt-2.5 flex items-center gap-2 text-[11px] text-[#8C93A5] font-light">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3 text-[#585E70] stroke-[1.5]" />
                        <span className="tabular-nums font-mono text-[10px]">{doc.num_pages} pages</span>
                      </span>
                      <span className="text-white/10">•</span>
                      <span className="tabular-nums font-mono text-[10px]">{doc.table_chunks} tables</span>
                    </div>

                    {/* Refined Extraction Risk Indicator (Complication Sub-Dial Style) */}
                    <div className="mt-2.5 pt-2 border-t border-white/[0.04] flex items-center justify-between text-[11px]">
                      {doc.table_chunks_flagged > 0 ? (
                        <span
                          data-testid={`flagged-indicator-${doc.doc_id.slice(0, 8)}`}
                          className="inline-flex items-center gap-1.5 text-[#D4A373] font-mono text-[10px] tabular-nums"
                          title={`${doc.table_chunks_flagged} of ${doc.table_chunks} tables flagged during extraction.`}
                        >
                          <ShieldAlert className="h-3 w-3 shrink-0 stroke-[1.8]" />
                          <span>
                            {doc.table_chunks_flagged} of {doc.table_chunks} tables flagged
                          </span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-[#52B788] font-mono text-[10px] tabular-nums">
                          <Check className="h-3 w-3 shrink-0 stroke-[2]" />
                          <span>All {doc.table_chunks} tables clean</span>
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

        {/* Scope Footer */}
        <div className="border-t border-white/[0.06] pt-3 text-[11px] text-[#82807A]">
          {selectedDoc ? (
            <div className="flex items-center justify-between">
              <span className="truncate">
                Scoped: <strong className="text-[#F7F7F4] font-medium">{selectedDoc.company_name}</strong>
              </span>
              <button
                onClick={() => onSelectDoc(null)}
                className="text-[#CBB282] hover:underline shrink-0 ml-1 cursor-pointer font-medium"
              >
                Clear
              </button>
            </div>
          ) : (
            <span className="text-[#82807A]/80">Cross-document catalog scope</span>
          )}

          {isShowcaseMode && (
            <div
              data-testid="showcase-corpus-notice"
              className="mt-2.5 pt-2.5 border-t border-white/[0.04] text-[10px] text-[#82807A]/75 leading-relaxed"
            >
              <span className="text-[#CBB282] font-medium">Fixed Demo Catalog:</span>{" "}
              Pre-ingested 5-filing corporate corpus. Live PDF upload and deletion are disabled in this public deployment.
            </div>
          )}
        </div>
      </aside>
      )}

      {/* Irreversible Delete Confirmation Dialog (Never rendered in Showcase Mode) */}
      {docToDelete && !isShowcaseMode && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4 animate-settle"
          onClick={() => !isDeleting && setDocToDelete(null)}
          onKeyDown={(e) => {
            if (e.key === "Escape" && !isDeleting) setDocToDelete(null);
          }}
        >
          <div
            className="rich-modal relative w-full max-w-md rounded-2xl bg-[#181C28] p-6 space-y-4 border border-white/[0.08]"
            onClick={(e) => e.stopPropagation()}
            data-testid="delete-confirmation-dialog"
          >
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#EF4444]/15 text-[#EF4444] border border-[#EF4444]/20">
                <Trash2 className="h-4 w-4 stroke-[1.8]" />
              </div>
              <div className="space-y-1">
                <h3 id="delete-dialog-title" className="text-sm font-semibold text-[#F1F3F9]">
                  Delete Ingested Filing
                </h3>
                <p className="text-xs text-[#8C93A5] leading-relaxed">
                  You are about to permanently remove{" "}
                  <strong className="text-[#F1F3F9] font-medium">
                    {docToDelete.company_name} ({formatFiscalYear(docToDelete.fiscal_year) || "N/A"})
                  </strong>
                  .
                </p>
              </div>
            </div>

            <div className="rounded-xl border border-white/[0.06] bg-[#13161F] p-3 text-xs text-[#8C93A5] space-y-1.5 leading-relaxed">
              <div className="flex justify-between tabular-nums text-[11px]">
                <span>Document ID:</span>
                <span className="font-mono text-[#F1F3F9]">{docToDelete.doc_id.slice(0, 12)}...</span>
              </div>
              <div className="flex justify-between tabular-nums text-[11px]">
                <span>Indexed Points:</span>
                <span className="text-[#F1F3F9]">{docToDelete.table_chunks + docToDelete.narrative_chunks} chunks</span>
              </div>
              <p className="pt-1.5 border-t border-white/[0.06] text-[11px] text-[#EF4444]">
                This action cannot be undone. All Qdrant vector embeddings, extracted tables, and disk records will be permanently purged.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setDocToDelete(null)}
                className="rounded-lg border border-white/10 px-3.5 py-1.5 text-xs text-[#8C93A5] hover:bg-white/5 hover:text-[#F1F3F9] transition-colors cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDeleting}
                data-testid="confirm-delete-button"
                onClick={handleDeleteConfirm}
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#E26D6D] px-4 py-1.5 text-xs font-medium text-white hover:bg-[#C95959] transition-colors cursor-pointer disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Permanently Delete</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
