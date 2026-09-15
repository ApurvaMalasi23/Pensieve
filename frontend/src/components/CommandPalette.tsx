"use client";

import React, { useState, useEffect, useRef } from "react";
import { DocumentItem } from "@/types/api";
import {
  Search,
  Layers,
  FileText,
  PanelLeftClose,
  PanelLeftOpen,
  ArrowRight,
  TrendingUp,
  ShieldAlert,
  Trash2,
  CornerDownLeft,
  X,
} from "lucide-react";

export interface CommandItem {
  id: string;
  category: "Scope" | "Inquiry" | "System";
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  shortcut?: string;
  onSelect: () => void;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  documents: DocumentItem[];
  selectedDoc: DocumentItem | null;
  onSelectDoc: (doc: DocumentItem | null) => void;
  onOpenUpload?: () => void;
  onToggleSidebar: () => void;
  isSidebarCollapsed: boolean;
  onSelectInquiry: (queryText: string) => void;
  onClearChat?: () => void;
  isShowcaseMode?: boolean;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  documents,
  selectedDoc,
  onSelectDoc,
  onOpenUpload,
  onToggleSidebar,
  isSidebarCollapsed,
  onSelectInquiry,
  onClearChat,
  isShowcaseMode = true,
}) => {
  const [search, setSearch] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setSearch("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Construct all actions
  const items: CommandItem[] = [
    // Scope items
    {
      id: "scope-all",
      category: "Scope",
      title: "All Ingested Filings",
      subtitle: `Cross-comparison scope (${documents.length} filings indexed)`,
      icon: <Layers className="h-4 w-4 text-[#E59500]" />,
      shortcut: "Scope",
      onSelect: () => {
        onSelectDoc(null);
        onClose();
      },
    },
    ...documents.map((doc) => ({
      id: `scope-doc-${doc.doc_id}`,
      category: "Scope" as const,
      title: `${doc.company_name} (FY ${doc.fiscal_year})`,
      subtitle: `${doc.num_pages} pages • ${doc.table_chunks} tables (${doc.table_chunks_flagged} flagged)`,
      icon: <FileText className="h-4 w-4 text-[#8C93A5]" />,
      onSelect: () => {
        onSelectDoc(doc);
        onClose();
      },
    })),

    // Inquiries
    {
      id: "inq-01",
      category: "Inquiry",
      title: "Narrative Disclosures & Lending Activities",
      subtitle: "What are Republic Bancorp's primary lending activities?",
      icon: <FileText className="h-4 w-4 text-[#E59500]" />,
      shortcut: "Inquiry",
      onSelect: () => {
        onSelectInquiry("What are Republic Bancorp's primary lending activities?");
        onClose();
      },
    },
    {
      id: "inq-02",
      category: "Inquiry",
      title: "Numeric Grounding: Traditional Bank Deposits",
      subtitle: "What were total traditional bank deposits as of December 31, 2024?",
      icon: <TrendingUp className="h-4 w-4 text-[#10B981]" />,
      shortcut: "Inquiry",
      onSelect: () => {
        onSelectInquiry("What were total traditional bank deposits as of December 31, 2024?");
        onClose();
      },
    },
    {
      id: "inq-03",
      category: "Inquiry",
      title: "Extraction Audit: OCR Flags & Rate Sensitivity",
      subtitle: "What is the impact of a 400 basis point rate change on net interest income?",
      icon: <ShieldAlert className="h-4 w-4 text-[#F59E0B]" />,
      shortcut: "Inquiry",
      onSelect: () => {
        onSelectInquiry("What is the impact of a 400 basis point rate change on net interest income?");
        onClose();
      },
    },
    {
      id: "inq-04",
      category: "Inquiry",
      title: "Cross-Entity Comparison: Revenue & Net Income",
      subtitle: "Compare total revenue or income of Republic Bancorp in 2024 and Lux Industries in 2025-26",
      icon: <Layers className="h-4 w-4 text-[#E59500]" />,
      shortcut: "Inquiry",
      onSelect: () => {
        onSelectInquiry("Compare total revenue or income of Republic Bancorp in 2024 and Lux Industries in 2025-26");
        onClose();
      },
    },

    // System actions
    {
      id: "sys-toggle-sidebar",
      category: "System",
      title: isSidebarCollapsed ? "Expand Catalog Sidebar" : "Collapse Catalog Sidebar",
      subtitle: "Toggle document list to expand analytical canvas",
      icon: isSidebarCollapsed ? (
        <PanelLeftOpen className="h-4 w-4 text-[#8E8D8A]" />
      ) : (
        <PanelLeftClose className="h-4 w-4 text-[#8E8D8A]" />
      ),
      shortcut: "⌘\\",
      onSelect: () => {
        onToggleSidebar();
        onClose();
      },
    },
    ...(onClearChat
      ? [
          {
            id: "sys-clear",
            category: "System" as const,
            title: "Clear Current Conversation",
            subtitle: "Reset chat messages back to initial state",
            icon: <Trash2 className="h-4 w-4 text-[#E26D6D]" />,
            onSelect: () => {
              onClearChat();
              onClose();
            },
          },
        ]
      : []),
  ];

  // Filter based on query
  const filtered = items.filter((item) => {
    const q = search.toLowerCase();
    return (
      item.title.toLowerCase().includes(q) ||
      (item.subtitle && item.subtitle.toLowerCase().includes(q)) ||
      item.category.toLowerCase().includes(q)
    );
  });

  // Clamp selection index
  useEffect(() => {
    setSelectedIndex(0);
  }, [search]);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filtered.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % Math.max(1, filtered.length));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtered[selectedIndex]) {
        filtered[selectedIndex].onSelect();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command Palette"
      className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] p-4 bg-black/80 backdrop-blur-md animate-settle"
      onClick={onClose}
    >
      <div
        data-testid="command-palette-modal"
        className="rich-modal relative flex max-h-[75vh] w-full max-w-2xl flex-col rounded-2xl bg-[#181C28]/95 border border-white/[0.12] text-[#F1F3F9] shadow-[0_24px_70px_rgba(0,0,0,0.95),0_0_0_1px_rgba(255,255,255,0.06)] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 border-b border-white/[0.08] px-4 py-3.5 bg-[#13161F]">
          <Search className="h-4 w-4 shrink-0 text-[#E59500]" />
          <input
            ref={inputRef}
            data-testid="command-palette-input"
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Type a command, filing company, or inquiry..."
            className="flex-1 bg-transparent text-sm text-[#F1F3F9] placeholder-[#8C93A5] outline-none font-sans"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="text-[#8C93A5] hover:text-[#F1F3F9] text-xs p-1"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <kbd className="hidden sm:inline-flex items-center gap-1 rounded bg-white/6 border border-white/10 px-1.5 py-0.5 text-[10px] font-mono text-[#8C93A5]">
            ESC to close
          </kbd>
        </div>

        {/* Results List */}
        <div
          ref={listRef}
          className="max-h-[55vh] overflow-y-auto p-2 divide-y divide-transparent scrollbar-thin"
        >
          {filtered.length === 0 ? (
            <div className="py-12 text-center text-xs text-[#8C93A5]">
              No commands or filings matching <span className="text-[#F1F3F9]">"{search}"</span>
            </div>
          ) : (
            filtered.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.id}
                  data-testid={`command-item-${item.id}`}
                  onClick={() => item.onSelect()}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`group flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-xs transition-all cursor-pointer ${
                    isSelected
                      ? "bg-[#13161F] border border-[#E59500]/30 shadow-[0_0_16px_rgba(229,149,0,0.12)]"
                      : "border border-transparent hover:bg-white/[0.03]"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border transition-colors ${
                        isSelected
                          ? "bg-[#E59500]/15 border-[#E59500]/30 text-[#E59500]"
                          : "bg-white/4 border-white/6 text-[#8C93A5]"
                      }`}
                    >
                      {item.icon}
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-[#F1F3F9] truncate">
                          {item.title}
                        </span>
                        <span className="text-[10px] uppercase font-mono tracking-wider px-1.5 py-0.2 rounded bg-white/6 text-[#8C93A5]">
                          {item.category}
                        </span>
                      </div>
                      {item.subtitle && (
                        <p className="text-[11px] text-[#8C93A5] truncate mt-0.5 font-sans">
                          {item.subtitle}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {item.shortcut && (
                      <kbd className="hidden sm:inline-block rounded bg-white/6 border border-white/8 px-1.5 py-0.5 text-[10px] font-mono text-[#8C93A5]">
                        {item.shortcut}
                      </kbd>
                    )}
                    {isSelected && (
                      <span className="text-[#E59500] flex items-center gap-1 text-[10px] font-mono">
                        <CornerDownLeft className="h-3 w-3" /> Select
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer info bar */}
        <div className="flex items-center justify-between border-t border-white/[0.08] bg-[#13161F]/60 px-4 py-2 text-[10px] text-[#8C93A5] font-mono">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="bg-white/6 border border-white/10 px-1 py-0.2 rounded">↑</kbd>
              <kbd className="bg-white/6 border border-white/10 px-1 py-0.2 rounded ml-1">↓</kbd> to navigate
            </span>
            <span>
              <kbd className="bg-white/6 border border-white/10 px-1 py-0.2 rounded">↵</kbd> to execute
            </span>
          </div>
          <span>Pensieve Command Spotlight</span>
        </div>
      </div>
    </div>
  );
};
