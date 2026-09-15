"use client";

import React from "react";
import { ChatMessageItem, Citation } from "@/types/api";
import { VerificationBadge } from "./VerificationBadge";
import { CitationChip } from "./CitationChip";
import { ComparisonView } from "./ComparisonView";
import { AlertCircle, HelpCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatMessageProps {
  message: ChatMessageItem;
  onSelectCitation: (citation: Citation) => void;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  onSelectCitation,
}) => {
  const isUser = message.role === "user";
  const payload = message.responsePayload;

  if (isUser) {
    return (
      <div className="flex justify-end mb-6">
        <div className="flex max-w-[85%] sm:max-w-[70%] flex-col items-end">
          <div className="rounded-2xl rounded-tr-xs bg-[#17181D]/90 border border-white/[0.07] px-4.5 py-3 text-sm text-[#F7F7F4] shadow-[0_8px_24px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.06)]">
            <p className="whitespace-pre-wrap leading-relaxed font-light">{message.content}</p>
          </div>
          <span className="mt-1.5 text-[10px] text-[#82807A] tabular-nums font-mono">
            {message.timestamp}
          </span>
        </div>
      </div>
    );
  }

  // Error message
  if (message.isError) {
    return (
      <div className="flex justify-start mb-6">
        <div className="flex max-w-[90%] sm:max-w-[80%] flex-col">
          <div className="rounded-2xl rounded-tl-xs bg-[#E06D6D]/10 border border-[#E06D6D]/25 p-4 text-xs text-[#E06D6D] backdrop-blur-md">
            <div className="flex items-center gap-1.5 font-semibold text-[#E06D6D] mb-1">
              <AlertCircle className="h-4 w-4 stroke-[1.8]" />
              <span>Request Error</span>
            </div>
            <p className="whitespace-pre-wrap leading-relaxed">{message.errorMessage || message.content}</p>
          </div>
          <span className="mt-1.5 text-[10px] text-[#82807A] tabular-nums font-mono">
            {message.timestamp}
          </span>
        </div>
      </div>
    );
  }

  // Assistant message with signature motion moment (animate-settle)
  return (
    <div className="flex justify-start mb-8 w-full" data-testid="assistant-message">
      <div className="w-full space-y-3">
        {payload?.comparison ? (
          <ComparisonView response={payload} onSelectCitation={onSelectCitation} />
        ) : (
          <div className="animate-settle rounded-2xl rounded-tl-xs bg-[#121216]/75 backdrop-blur-2xl border border-white/[0.05] p-5.5 space-y-4 shadow-[0_16px_40px_rgba(0,0,0,0.6),inset_0_1px_0_rgba(255,255,255,0.05)]">
            {/* No context found callout */}
            {payload?.no_context_found ? (
              <div
                data-testid="no-context-callout"
                className="flex items-start gap-3 rounded-2xl border border-white/[0.05] bg-white/[0.015] p-4 text-xs text-[#82807A]"
              >
                <HelpCircle className="h-4 w-4 shrink-0 text-[#82807A] mt-0.5 stroke-[1.5]" />
                <div>
                  <span className="font-semibold text-[#F7F7F4] block text-sm">
                    No matching context found
                  </span>
                  <p className="mt-1 leading-relaxed text-[#82807A] font-light">
                    Pensieve declined to answer because no relevant sections or financial tables were found
                    matching your query in the currently ingested filings.
                  </p>
                </div>
              </div>
            ) : (
              /* Financial-Grade Markdown Surface with strict tabular lining numerals */
              <div className="text-[13.5px] sm:text-sm leading-[1.68] text-[#F7F7F4] font-sans">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => (
                      <p className="mb-3.5 last:mb-0 leading-[1.68] text-[#F7F7F4] font-normal">{children}</p>
                    ),
                    strong: ({ children }) => (
                      <strong className="font-semibold text-[#FFFFFF]">{children}</strong>
                    ),
                    ul: ({ children }) => (
                      <ul className="mb-3.5 list-disc pl-5 space-y-1.5 text-[#CDCBC4] font-normal">{children}</ul>
                    ),
                    ol: ({ children }) => (
                      <ol className="mb-3.5 list-decimal pl-5 space-y-1.5 text-[#CDCBC4] font-normal">{children}</ol>
                    ),
                    li: ({ children }) => <li className="leading-[1.68]">{children}</li>,
                    table: ({ children }) => (
                      <div className="my-4 luxury-ledger-container">
                        <table className="luxury-ledger">
                          {children}
                        </table>
                      </div>
                    ),
                    thead: ({ children }) => <thead>{children}</thead>,
                    th: ({ children }) => <th>{children}</th>,
                    tbody: ({ children }) => <tbody>{children}</tbody>,
                    tr: ({ children }) => <tr>{children}</tr>,
                    td: ({ children }) => <td>{children}</td>,
                    code: ({ inline, children, ...props }: any) =>
                      inline ? (
                        <code
                          className="rounded bg-[#CBB282]/10 border border-[#CBB282]/20 px-1.5 py-0.5 font-mono text-xs text-[#CBB282]"
                          {...props}
                        >
                          {children}
                        </code>
                      ) : (
                        <pre className="my-3 overflow-x-auto rounded-lg bg-[#0B0B0D] p-3 font-mono text-xs text-[#CDCBC4] border border-white/[0.05]">
                          <code>{children}</code>
                        </pre>
                      ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            )}

            {/* Verification Badge with Micro-Audit Accordion */}
            {payload?.verification && payload.verification.status !== "not_applicable" && (
              <div className="pt-2 border-t border-white/[0.04]">
                <VerificationBadge
                  status={payload.verification.status}
                  reason={payload.verification.reason}
                />
              </div>
            )}

            {/* Citations list */}
            {payload?.citations && payload.citations.length > 0 && (
              <div className="pt-2.5 border-t border-white/[0.04]">
                <span className="text-[10.5px] font-mono uppercase tracking-wider text-[#82807A] block mb-1.5">
                  Source Citations ({payload.citations.length}):
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {payload.citations.map((cit, idx) => (
                    <CitationChip
                      key={idx}
                      citation={cit}
                      onClick={onSelectCitation}
                    />
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-1 text-[10.5px] text-[#82807A]">
              <span>
                Intent: <strong className="text-[#F7F7F4] font-medium">{payload?.intent || "narrative"}</strong>
              </span>
              <span className="tabular-nums font-mono text-[10px]">{message.timestamp}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
