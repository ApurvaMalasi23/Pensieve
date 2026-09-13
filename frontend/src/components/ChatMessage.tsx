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
          <div className="rounded-2xl rounded-tr-xs bg-gradient-to-br from-[#181C28] to-[#13161F] border border-white/[0.09] px-4.5 py-3 text-sm text-[#F1F3F9] shadow-[0_10px_25px_rgba(0,0,0,0.45),inset_0_1px_0_rgba(255,255,255,0.08)]">
            <p className="whitespace-pre-wrap leading-relaxed font-light">{message.content}</p>
          </div>
          <span className="mt-1.5 text-[10px] text-[#8C93A5] tabular-nums font-mono">
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
          <div className="rounded-2xl rounded-tl-xs bg-[#EF4444]/10 border border-[#EF4444]/25 p-4 text-xs text-[#EF4444] backdrop-blur-md">
            <div className="flex items-center gap-1.5 font-semibold text-[#EF4444] mb-1">
              <AlertCircle className="h-4 w-4 stroke-[1.8]" />
              <span>Request Error</span>
            </div>
            <p className="whitespace-pre-wrap leading-relaxed">{message.errorMessage || message.content}</p>
          </div>
          <span className="mt-1.5 text-[10px] text-[#8C93A5] tabular-nums font-mono">
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
          <div className="animate-settle rounded-2xl rounded-tl-xs bg-[#13161F]/80 backdrop-blur-2xl border border-white/[0.06] p-5.5 space-y-4 shadow-[0_16px_40px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.04)]">
            {/* No context found callout */}
            {payload?.no_context_found ? (
              <div
                data-testid="no-context-callout"
                className="flex items-start gap-3 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 text-xs text-[#8C93A5]"
              >
                <HelpCircle className="h-4 w-4 shrink-0 text-[#8C93A5] mt-0.5 stroke-[1.5]" />
                <div>
                  <span className="font-semibold text-[#F1F3F9] block text-sm">
                    No matching context found
                  </span>
                  <p className="mt-1 leading-relaxed text-[#8C93A5] font-light">
                    Pensieve declined to answer because no relevant sections or financial tables were found
                    matching your query in the currently ingested filings.
                  </p>
                </div>
              </div>
            ) : (
              /* Financial-Grade Markdown Surface with strict tabular lining numerals */
              <div className="text-[13.5px] sm:text-sm leading-[1.68] text-[#F1F3F9] font-sans">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => (
                      <p className="mb-3.5 last:mb-0 leading-[1.68] text-[#F1F3F9] font-normal">{children}</p>
                    ),
                    strong: ({ children }) => (
                      <strong className="font-semibold text-[#FFFFFF]">{children}</strong>
                    ),
                    ul: ({ children }) => (
                      <ul className="mb-3.5 list-disc pl-5 space-y-1.5 text-[#C2C7D4] font-normal">{children}</ul>
                    ),
                    ol: ({ children }) => (
                      <ol className="mb-3.5 list-decimal pl-5 space-y-1.5 text-[#C2C7D4] font-normal">{children}</ol>
                    ),
                    li: ({ children }) => <li className="leading-[1.68]">{children}</li>,
                    table: ({ children }) => (
                      <div className="my-4 overflow-x-auto rounded-xl border border-white/[0.08] bg-[#0A0B0E]/80 p-1 shadow-inner">
                        <table className="w-full border-collapse text-left text-xs tabular-nums font-mono">
                          {children}
                        </table>
                      </div>
                    ),
                    thead: ({ children }) => (
                      <thead className="border-b border-white/[0.08] bg-white/[0.02] text-[10px] font-mono tracking-wider uppercase text-[#8C93A5]">
                        {children}
                      </thead>
                    ),
                    th: ({ children }) => (
                      <th className="px-3.5 py-2 font-semibold text-[#E59500]">
                        {children}
                      </th>
                    ),
                    tbody: ({ children }) => (
                      <tbody className="divide-y divide-white/6 font-mono text-xs tabular-nums">
                        {children}
                      </tbody>
                    ),
                    tr: ({ children }) => (
                      <tr className="hover:bg-white/[0.02] transition-colors">
                        {children}
                      </tr>
                    ),
                    td: ({ children }) => (
                      <td className="px-3.5 py-2 text-[#C2C7D4] font-mono text-xs tabular-nums">
                        {children}
                      </td>
                    ),
                    code: ({ inline, children, ...props }: any) =>
                      inline ? (
                        <code
                          className="rounded bg-white/6 px-1.5 py-0.5 font-mono text-xs text-[#E59500]"
                          {...props}
                        >
                          {children}
                        </code>
                      ) : (
                        <pre className="my-3 overflow-x-auto rounded-lg bg-[#0A0B0E] p-3 font-mono text-xs text-[#C2C7D4] border border-white/8">
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
              <div className="pt-2 border-t border-white/6">
                <VerificationBadge
                  status={payload.verification.status}
                  reason={payload.verification.reason}
                />
              </div>
            )}

            {/* Citations list */}
            {payload?.citations && payload.citations.length > 0 && (
              <div className="pt-2.5 border-t border-white/6">
                <span className="text-[11px] font-medium text-[#8C93A5] block mb-1.5 font-sans">
                  Source citations ({payload.citations.length}):
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

            <div className="flex items-center justify-between pt-1 text-[10.5px] text-[#8C93A5]">
              <span>
                Intent: <strong className="text-[#F1F3F9] font-medium">{payload?.intent || "narrative"}</strong>
              </span>
              <span className="tabular-nums font-mono text-[10px]">{message.timestamp}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
