"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { askQuestion, formatFiscalYear } from "@/lib/api";
import { ChatMessageItem, Citation, DocumentItem } from "@/types/api";
import { ChatMessage } from "./ChatMessage";
import {
  Send,
  Loader2,
  Layers,
  WifiOff,
  Sparkles,
  ArrowRight,
  ArrowLeft,
} from "lucide-react";
import { PensieveLogo } from "./PensieveLogo";
import { ThinkingTelemetry } from "./ThinkingTelemetry";

interface ChatInterfaceProps {
  selectedDoc: DocumentItem | null;
  onSelectCitation: (citation: Citation) => void;
  isBackendConnected: boolean;
  injectedQuery?: string | null;
  onInjectedQueryHandled?: () => void;
  isShowcaseMode?: boolean;
}

interface InquiryItem {
  index: string;
  label: string;
  text: string;
  meta: string;
}

const ALL_FILINGS_INQUIRIES: InquiryItem[] = [
  {
    index: "01",
    label: "Cross Comparison",
    text: "Compare total revenue or income of Republic Bancorp in 2024 and Lux Industries in 2025-26",
    meta: "Multi-entity synthesis & programmatic delta",
  },
  {
    index: "02",
    label: "Capital & Reserves",
    text: "Which company maintains the highest cash reserves or capital expenditure commitments?",
    meta: "Cross-filing solvency & liquidity overview",
  },
  {
    index: "03",
    label: "Operating Margins",
    text: "Contrast operating profit margins between food services (Jubilant) and solar energy (Ravindra)",
    meta: "Cross-sector profitability analysis",
  },
  {
    index: "04",
    label: "Risk Audit",
    text: "Which filings exhibit the highest density of flagged OCR extraction risk tables?",
    meta: "Corpus-wide tabular risk flag audit",
  },
];

const JUBILANT_INQUIRIES: InquiryItem[] = [
  {
    index: "01",
    label: "Brand & Expansion",
    text: "What are Jubilant FoodWorks' primary growth initiatives for Domino's and Popeyes store networks?",
    meta: "Filing disclosures & store expansion review",
  },
  {
    index: "02",
    label: "Numeric Grounding",
    text: "What was the net revenue from operations and consolidated profit after tax for Jubilant in 2025-26?",
    meta: "P&L cell-matched table grounding",
  },
  {
    index: "03",
    label: "Channel Economics",
    text: "What is Jubilant FoodWorks' same-store sales growth (SSSG) and delivery versus dine-in revenue mix?",
    meta: "Operational disclosures & channel economics",
  },
  {
    index: "04",
    label: "Flagged Notes (p.84)",
    text: "What is the breakdown of lease liabilities and raw material cost inflation reported in the financial notes?",
    meta: "Flagged table with OCR anomaly check",
  },
];

const RAVINDRA_INQUIRIES: InquiryItem[] = [
  {
    index: "01",
    label: "Solar Projects",
    text: "What is Ravindra Energy's primary business model and execution status under the PM-KUSUM solar scheme?",
    meta: "Executive review & renewable projects",
  },
  {
    index: "02",
    label: "Numeric Grounding",
    text: "What was the total revenue from operations for Ravindra Energy in financial year 2024-25?",
    meta: "Income statement cell-matched verification",
  },
  {
    index: "03",
    label: "Segment Mix",
    text: "How does revenue from sale of electricity compare against trading of solar equipment and EPC contracts?",
    meta: "Segment reporting & revenue composition",
  },
  {
    index: "04",
    label: "Balance Sheet",
    text: "What are Ravindra Energy's total outstanding borrowings and disclosed contingent liabilities?",
    meta: "Balance sheet disclosures & debt analysis",
  },
];

const REPUBLIC_INQUIRIES: InquiryItem[] = [
  {
    index: "01",
    label: "Lending Activities",
    text: "What are Republic Bancorp's primary lending activities and commercial real estate exposures?",
    meta: "Filing disclosures & credit portfolio",
  },
  {
    index: "02",
    label: "Numeric Grounding",
    text: "What were total traditional bank deposits as of December 31, 2024?",
    meta: "Cell-matched balance sheet table verification",
  },
  {
    index: "03",
    label: "Sensitivity (p.89)",
    text: "What is the impact of a 400 basis point rate change on net interest income?",
    meta: "Flagged table with OCR anomaly warning",
  },
  {
    index: "04",
    label: "Credit Quality",
    text: "What was Republic Bancorp's provision for credit losses and non-performing loans ratio for 2024?",
    meta: "Asset quality & allowance schedule",
  },
];

const LUX_INQUIRIES: InquiryItem[] = [
  {
    index: "01",
    label: "Brand Portfolio",
    text: "What is the performance and brand positioning of Lux Cozi, ONN, and Lyra in 2025-26?",
    meta: "Brand portfolio disclosures & market reach",
  },
  {
    index: "02",
    label: "Numeric Grounding",
    text: "What was the net revenue from operations and gross profit margin for Lux Industries in 2025-26?",
    meta: "Audited financial statement cell verification",
  },
  {
    index: "03",
    label: "Geographic Mix",
    text: "What percentage of total revenue came from domestic retail sales versus international export markets?",
    meta: "Geographic segment reporting",
  },
  {
    index: "04",
    label: "Working Capital",
    text: "How did cotton yarn inventory levels and working capital cycle days trend during FY 2025-26?",
    meta: "Balance sheet notes & working capital analysis",
  },
];

const NTPC_INQUIRIES: InquiryItem[] = [
  {
    index: "01",
    label: "Renewable Capacity",
    text: "What is NTPC Green Energy's operational renewable capacity and pipeline of solar/wind projects?",
    meta: "Renewable energy capacity disclosures",
  },
  {
    index: "02",
    label: "Numeric Grounding",
    text: "What was NTPC Green Energy's total income from operations and EBITDA margin for 2024?",
    meta: "Quarterly financial table cell grounding",
  },
  {
    index: "03",
    label: "Clean Energy Capex",
    text: "What was the capital expenditure incurred on developing solar parks and wind energy farms?",
    meta: "Cash flow statement & capex schedule",
  },
  {
    index: "04",
    label: "PPA Contracts",
    text: "What are the key terms and average realization tariffs for NTPC Green Energy's long-term PPAs?",
    meta: "Regulatory disclosures & PPA off-taker review",
  },
];

function getInquiriesForScope(doc: DocumentItem | null): InquiryItem[] {
  if (!doc) {
    return ALL_FILINGS_INQUIRIES;
  }

  const name = (doc.company_name || "").toLowerCase();
  if (name.includes("jubilant")) {
    return JUBILANT_INQUIRIES;
  }
  if (name.includes("ravindra")) {
    return RAVINDRA_INQUIRIES;
  }
  if (name.includes("republic")) {
    return REPUBLIC_INQUIRIES;
  }
  if (name.includes("lux")) {
    return LUX_INQUIRIES;
  }
  if (name.includes("ntpc")) {
    return NTPC_INQUIRIES;
  }

  const company = doc.company_name;
  const fy = formatFiscalYear(doc.fiscal_year);
  return [
    {
      index: "01",
      label: "Narrative RAG",
      text: `What are ${company}'s principal operating activities and executive highlights for ${fy}?`,
      meta: "Filing disclosures & executive review",
    },
    {
      index: "02",
      label: "Numeric Grounding",
      text: `What was the total revenue from operations and net profit reported by ${company} in ${fy}?`,
      meta: "Cell-matched financial table verification",
    },
    {
      index: "03",
      label: "Capital Structure",
      text: `What are ${company}'s total assets, borrowings, and cash balances for ${fy}?`,
      meta: "Balance sheet financial notes verification",
    },
    {
      index: "04",
      label: "Risk & Audit",
      text: `What material risk factors or auditor notes are disclosed in ${company}'s ${fy} filing?`,
      meta: "Disclosures & extraction crosscheck",
    },
  ];
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  selectedDoc,
  onSelectCitation,
  isBackendConnected,
  injectedQuery,
  onInjectedQueryHandled,
  isShowcaseMode = false,
}) => {
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [inputQuery, setInputQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const activeRequestIdRef = useRef<number>(0);

  const currentInquiries = useMemo(() => getInquiriesForScope(selectedDoc), [selectedDoc]);

  const handleBackToDefaultQuestions = useCallback(() => {
    activeRequestIdRef.current += 1;
    setMessages([]);
    setIsLoading(false);
    setInputQuery("");
  }, []);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, scrollToBottom]);

  // Handle injected query from Command Palette
  useEffect(() => {
    if (injectedQuery) {
      setInputQuery(injectedQuery);
      inputRef.current?.focus();
      onInjectedQueryHandled?.();
    }
  }, [injectedQuery, onInjectedQueryHandled]);

  // Global keyboard shortcut: Jump focus on '/' when not typing in another input
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (
        e.key === "/" &&
        document.activeElement?.tagName !== "INPUT" &&
        document.activeElement?.tagName !== "TEXTAREA"
      ) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, []);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const query = inputQuery.trim();
    if (!query || isLoading) return;

    const requestId = ++activeRequestIdRef.current;

    const userMessage: ChatMessageItem = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputQuery("");
    setIsLoading(true);

    try {
      const response = await askQuestion({
        query,
        company_name: selectedDoc?.company_name,
        fiscal_year: selectedDoc?.fiscal_year,
      });

      if (activeRequestIdRef.current !== requestId) return;

      const assistantMessage: ChatMessageItem = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: response.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        responsePayload: response,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      if (activeRequestIdRef.current !== requestId) return;

      const errorMessage: ChatMessageItem = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: "Error processing query.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        isError: true,
        errorMessage: err.message || "Could not connect to Pensieve backend.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      if (activeRequestIdRef.current === requestId) {
        setIsLoading(false);
        setTimeout(() => inputRef.current?.focus(), 100);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex h-full flex-col bg-[#0A0B0E] text-[#F1F3F9]">
      {/* Backend Disconnected Alert Banner */}
      {!isBackendConnected && (
        <div
          data-testid="backend-error-banner"
          className="flex items-center gap-2.5 border-b border-[#EF4444]/30 bg-[#EF4444]/10 px-6 py-2.5 text-xs text-[#EF4444]"
        >
          <WifiOff className="h-4 w-4 shrink-0" />
          <span>
            <strong>Cannot connect to Pensieve backend.</strong> Please verify FastAPI (port 8000) and Qdrant are operational.
          </span>
        </div>
      )}

      {/* Scope Subheader */}
      <div className="flex items-center justify-between border-b border-white/[0.05] bg-[#0A0B0E]/70 backdrop-blur-md px-6 py-2 text-xs text-[#8C93A5]">
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button
              type="button"
              data-testid="back-to-default-questions-button"
              onClick={handleBackToDefaultQuestions}
              className="group flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium text-[#E59500] hover:text-white bg-[#E59500]/10 hover:bg-[#E59500]/20 border border-[#E59500]/25 transition-all duration-150 cursor-pointer shadow-xs mr-1"
              title="Return to default questions"
            >
              <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 text-[#E59500]" />
              <span className="hidden sm:inline">Back to questions</span>
              <span className="sm:hidden">Back</span>
            </button>
          )}
          <Layers className="h-3.5 w-3.5 text-[#E59500]" />
          <span>
            Scope:{" "}
            {selectedDoc ? (
              <span className="font-medium text-[#F1F3F9]">
                {selectedDoc.company_name} ({formatFiscalYear(selectedDoc.fiscal_year)})
              </span>
            ) : (
              <span className="font-medium text-[#F1F3F9]">
                All ingested filings (Cross-comparison enabled)
              </span>
            )}
          </span>
        </div>
        {messages.length > 0 && (
          <button
            onClick={handleBackToDefaultQuestions}
            className="text-[11px] text-[#8C93A5] hover:text-[#F1F3F9] transition-colors cursor-pointer"
          >
            Clear conversation
          </button>
        )}
      </div>

      {/* Hero Chat Feed Area (Centered Single Column) */}
      <div className="flex-1 overflow-y-auto px-4 pt-3 sm:pt-4 pb-8">
        <div className="mx-auto max-w-3xl">
          {messages.length === 0 ? (
            <div className="relative flex flex-col items-center justify-center text-center pt-2 sm:pt-4 pb-10 sm:pb-14">
              {/* Atmospheric Cinematic Radial Aura */}
              <div 
                aria-hidden="true"
                className="pointer-events-none absolute -top-12 left-1/2 -translate-x-1/2 h-[480px] w-[800px] rounded-full bg-[radial-gradient(ellipse_at_center,rgba(229,149,0,0.18),rgba(229,149,0,0.04)_45%,transparent_70%)] blur-3xl -z-10" 
              />

              {/* Jony Ive Ambient Watermark (Etched faintly in canvas background) */}
              <div
                aria-hidden="true"
                className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-[0.035] -z-10 select-none"
              >
                <PensieveLogo size={520} strokeWidth={1.2} color="#E59500" />
              </div>

              {/* Apple-style sleek kicker with pulsating micro-beacon */}
              <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full border border-[#E59500]/25 bg-[#13161F]/85 backdrop-blur-xl mb-5 shadow-[0_0_30px_rgba(229,149,0,0.16)]">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#E59500] opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#E59500]" />
                </span>
                <span className="font-mono text-[10px] sm:text-[11px] tracking-[0.28em] uppercase font-semibold text-[#E59500]">
                  Pensieve Intelligence
                </span>
                <span className="text-white/20 text-xs">•</span>
                <span className="text-[10px] sm:text-[11px] tracking-wider uppercase text-[#8C93A5] font-mono">
                  Ground Truth Engine
                </span>
              </div>

              {/* Grand Keynote Display Headline (Calibrated Golden Proportion) */}
              <h1 className="font-sans text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-[-0.04em] leading-[0.98] bg-gradient-to-b from-[#FFFFFF] via-[#F1F3F9] to-[#8C93A5] bg-clip-text text-transparent drop-shadow-[0_20px_40px_rgba(0,0,0,0.8)]">
                Ask Pensieve.
              </h1>

              {/* Authoritative Supporting Copy with Optical Golden Ratio */}
              <p className="mt-4 text-sm sm:text-base text-[#8C93A5] max-w-xl leading-relaxed font-normal tracking-[-0.01em] font-sans">
                Interrogate corporate filings with <span className="text-[#F1F3F9] font-medium">cell-level mathematical verification</span> and unbreakable source provenance.
              </p>

              {/* Bespoke Inquiry Ledger: Smoked Crystal Slab Architecture */}
              <div className="mt-9 w-full text-left">
                <div className="flex items-center justify-between mb-2.5 px-1">
                  <span className="text-[11px] font-mono uppercase tracking-widest text-[#8C93A5]">
                    {selectedDoc ? `${selectedDoc.company_name} Inquiries` : "Recommended Inquiries"}
                  </span>
                  <span className="text-[10px] font-mono text-[#585E70] uppercase tracking-wider">
                    Click to query
                  </span>
                </div>

                <div className="rounded-2xl border border-white/[0.06] bg-[#13161F]/60 backdrop-blur-2xl divide-y divide-white/[0.04] shadow-[0_20px_50px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.05)] overflow-hidden">
                  {currentInquiries.map((item) => (
                    <button
                      key={item.index}
                      type="button"
                      onClick={() => {
                        setInputQuery(item.text);
                        inputRef.current?.focus();
                      }}
                      className="group relative flex w-full items-start gap-4 p-4 text-left transition-all duration-200 hover:bg-white/[0.03] cursor-pointer"
                    >
                      {/* Interactive gold hairline blade reveal */}
                      <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-[#E59500] opacity-0 group-hover:opacity-100 transition-opacity duration-200 shadow-[0_0_8px_#E59500]" />
                      
                      <span className="font-mono text-[11px] sm:text-[11.5px] font-semibold text-[#E59500]/80 group-hover:text-[#E59500] pt-0.5 tabular-nums shrink-0 transition-colors">
                        {item.index}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium tracking-wide bg-white/[0.04] text-[#C2C7D4] group-hover:text-[#E59500] group-hover:bg-[#E59500]/10 transition-colors border border-white/[0.04]">
                            {item.label}
                          </span>
                          <span className="text-white/10 text-[9px]">•</span>
                          <span className="text-[10px] font-mono text-[#585E70] truncate">
                            {item.meta}
                          </span>
                        </div>
                        <p className="text-[13px] sm:text-sm text-[#C2C7D4] group-hover:text-white transition-colors leading-relaxed font-normal">
                          {item.text}
                        </p>
                      </div>
                      <ArrowRight className="h-3.5 w-3.5 text-[#585E70] group-hover:text-[#E59500] group-hover:translate-x-1 transition-all mt-1 shrink-0" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                onSelectCitation={onSelectCitation}
              />
            ))
          )}

          {/* Staged Thinking & Mathematical Verification Telemetry Pipeline */}
          {isLoading && messages.length > 0 && <ThinkingTelemetry />}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Monolithic Floating Input Dock */}
      <div className="relative px-4 pb-6 pt-2 bg-gradient-to-t from-[#0A0B0E] via-[#0A0B0E]/95 to-transparent">
        <form
          onSubmit={handleSubmit}
          className="relative mx-auto flex max-w-3xl items-end rounded-2xl border border-white/[0.08] bg-[#13161F]/85 backdrop-blur-2xl px-4 py-3.5 shadow-[0_20px_50px_rgba(0,0,0,0.8),inset_0_1px_0_rgba(255,255,255,0.08)] transition-all duration-300 focus-within:border-[#E59500]/40 focus-within:shadow-[0_20px_50px_rgba(0,0,0,0.9),0_0_24px_rgba(229,149,0,0.14),inset_0_1px_0_rgba(255,255,255,0.12)]"
        >
          <textarea
            ref={inputRef}
            rows={1}
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              selectedDoc
                ? `Query ${selectedDoc.company_name} filings (Press / to focus)...`
                : "Ask a financial question or cross-compare filings (Press / to focus)..."
            }
            className="flex-1 resize-none bg-transparent text-sm text-[#F1F3F9] placeholder-[#585E70] border-0 outline-none focus:outline-none focus:ring-0 ring-0 max-h-32 leading-relaxed font-light"
          />
          <button
            type="submit"
            disabled={!inputQuery.trim() || isLoading}
            data-testid="send-query-button"
            className={`ml-3 flex h-8.5 w-8.5 shrink-0 items-center justify-center rounded-xl transition-all duration-200 active:scale-95 ${
              inputQuery.trim() && !isLoading
                ? "bg-[#E59500] text-[#0A0B0E] hover:bg-[#F3A712] shadow-[0_0_16px_rgba(229,149,0,0.35)] cursor-pointer"
                : "bg-white/[0.04] text-[#585E70] cursor-not-allowed border border-white/[0.05]"
            }`}
            title="Submit query"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4 stroke-[2]" />
            )}
          </button>
        </form>
        {isShowcaseMode && (
          <div
            data-testid="showcase-input-notice"
            className="mt-2.5 text-center text-[10px] text-[#8C93A5]/70 font-mono tracking-wider"
          >
            Showcase Catalog: Fixed corporate corpus • Cell-level numeric grounding & verification active
          </div>
        )}
      </div>
    </div>
  );
};
