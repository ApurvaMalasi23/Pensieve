"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Header } from "@/components/Header";
import { DocumentPanel } from "@/components/DocumentPanel";
import { ChatInterface } from "@/components/ChatInterface";
import { UploadModal } from "@/components/UploadModal";
import { CitationModal } from "@/components/CitationModal";
import { CommandPalette } from "@/components/CommandPalette";
import { FilingInspector } from "@/components/FilingInspector";
import { fetchDocuments } from "@/lib/api";
import { Citation, DocumentItem, HealthResponse } from "@/types/api";

export default function Home() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState(true);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isInspectorFullscreen, setIsInspectorFullscreen] = useState(false);
  const [injectedQuery, setInjectedQuery] = useState<string | null>(null);
  const [isShowcaseMode, setIsShowcaseMode] = useState<boolean>(() => {
    return process.env.NEXT_PUBLIC_SHOWCASE_MODE === "true";
  });

  const loadDocuments = useCallback(async () => {
    try {
      setIsLoadingDocs(true);
      const docs = await fetchDocuments();
      setDocuments(docs);
      setIsBackendConnected(true);
    } catch (err) {
      console.error("Error fetching documents:", err);
    } finally {
      setIsLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleHealthStatusChange = (isHealthy: boolean, healthData?: HealthResponse) => {
    setIsBackendConnected(isHealthy);
    if (healthData?.showcase_mode !== undefined) {
      setIsShowcaseMode(Boolean(healthData.showcase_mode));
    } else if (process.env.NEXT_PUBLIC_SHOWCASE_MODE === "true") {
      setIsShowcaseMode(true);
    }
  };

  // Global power-user shortcuts (Cmd+K, Cmd+\, Cmd+U)
  useEffect(() => {
    const handleGlobalShortcuts = (e: KeyboardEvent) => {
      const isCmdOrCtrl = e.metaKey || e.ctrlKey;

      // Cmd+K: Toggle Command Spotlight Palette
      if (isCmdOrCtrl && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }

      // Cmd+\: Toggle Sidebar Collapse
      if (isCmdOrCtrl && e.key === "\\") {
        e.preventDefault();
        setIsSidebarCollapsed((prev) => !prev);
      }

      // Cmd+U: Open Upload Modal (Disabled when in showcase mode)
      if (isCmdOrCtrl && e.key.toLowerCase() === "u") {
        e.preventDefault();
        if (!isShowcaseMode) {
          setIsUploadOpen(true);
        }
      }
    };

    window.addEventListener("keydown", handleGlobalShortcuts);
    return () => window.removeEventListener("keydown", handleGlobalShortcuts);
  }, [isShowcaseMode]);

  const handleDocumentDeleted = (deletedDocId: string) => {
    setDocuments((prev) => prev.filter((d) => d.doc_id !== deletedDocId));
    if (selectedDoc?.doc_id === deletedDocId) {
      setSelectedDoc(null);
    }
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#0A0B0E] text-[#F1F3F9] font-sans">
      {/* Top Header */}
      <Header
        onHealthStatusChange={handleHealthStatusChange}
        onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
        onToggleSidebar={() => setIsSidebarCollapsed((prev) => !prev)}
        isSidebarCollapsed={isSidebarCollapsed}
        isShowcaseMode={isShowcaseMode}
      />

      {/* Main Workspace Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Document Filter & Transparency Panel with smooth collapsible width */}
        <div
          className={`${
            isSidebarCollapsed ? "w-14" : "w-76 lg:w-84"
          } shrink-0 h-full border-r border-white/8 transition-all duration-200 ease-in-out`}
        >
          <DocumentPanel
            documents={documents}
            selectedDoc={selectedDoc}
            onSelectDoc={setSelectedDoc}
            onOpenUpload={() => setIsUploadOpen(true)}
            isLoading={isLoadingDocs}
            onDocumentDeleted={handleDocumentDeleted}
            isCollapsed={isSidebarCollapsed}
            onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
            isShowcaseMode={isShowcaseMode}
          />
        </div>

        {/* Hero Chat & Verification Interface */}
        <main className="flex-1 h-full min-w-0">
          <ChatInterface
            selectedDoc={selectedDoc}
            onSelectCitation={setActiveCitation}
            isBackendConnected={isBackendConnected}
            injectedQuery={injectedQuery}
            onInjectedQueryHandled={() => setInjectedQuery(null)}
            isShowcaseMode={isShowcaseMode}
          />
        </main>

        {/* Side-by-Side Co-Pilot Filing Inspector */}
        {activeCitation && !isInspectorFullscreen && (
          <div className="w-[420px] lg:w-[480px] xl:w-[540px] shrink-0 h-full border-l border-white/8 transition-all duration-200">
            <FilingInspector
              citation={activeCitation}
              onClose={() => setActiveCitation(null)}
              isFullscreen={false}
              onToggleFullscreen={() => setIsInspectorFullscreen(true)}
            />
          </div>
        )}
      </div>

      {/* Modals & Command Spotlight */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        documents={documents}
        selectedDoc={selectedDoc}
        onSelectDoc={setSelectedDoc}
        onOpenUpload={() => setIsUploadOpen(true)}
        onToggleSidebar={() => setIsSidebarCollapsed((prev) => !prev)}
        isSidebarCollapsed={isSidebarCollapsed}
        onSelectInquiry={(query) => setInjectedQuery(query)}
        isShowcaseMode={isShowcaseMode}
      />

      {/* Only render UploadModal when NOT in showcase mode */}
      {!isShowcaseMode && (
        <UploadModal
          isOpen={isUploadOpen}
          onClose={() => setIsUploadOpen(false)}
          onUploadSuccess={() => {
            loadDocuments();
          }}
        />
      )}

      {/* Fullscreen Inspector Mode */}
      {activeCitation && isInspectorFullscreen && (
        <FilingInspector
          citation={activeCitation}
          onClose={() => {
            setActiveCitation(null);
            setIsInspectorFullscreen(false);
          }}
          isFullscreen={true}
          onToggleFullscreen={() => setIsInspectorFullscreen(false)}
        />
      )}
    </div>
  );
}

