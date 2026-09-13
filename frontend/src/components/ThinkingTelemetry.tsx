"use client";

import React, { useState, useEffect } from "react";
import { Check, Loader2, Sparkles, ChevronDown, ChevronUp, Cpu, Database, Table, Scale, ShieldCheck } from "lucide-react";
import { PensieveLogo } from "./PensieveLogo";

interface TelemetryStage {
  id: string;
  title: string;
  detail: string;
  icon: React.ReactNode;
}

const STAGES: TelemetryStage[] = [
  {
    id: "vector-retrieval",
    title: "Semantic Vector Space Retrieval",
    detail: "Scanning Qdrant collection for high-similarity narrative & table chunks",
    icon: <Database className="h-3.5 w-3.5" />,
  },
  {
    id: "table-audit",
    title: "Tabular Matrix & OCR Crosscheck",
    detail: "Parsing row headers, period boundaries, and checking extraction risk flags",
    icon: <Table className="h-3.5 w-3.5" />,
  },
  {
    id: "numeric-verification",
    title: "Cell-Level Mathematical Grounding",
    detail: "Executing zero-discrepancy cell matching against primary financial disclosures",
    icon: <Scale className="h-3.5 w-3.5" />,
  },
  {
    id: "provenance-synthesis",
    title: "Grounded Synthesis & Provenance Assembly",
    detail: "Synthesizing answer with verified citations and bounding box coordinates",
    icon: <ShieldCheck className="h-3.5 w-3.5" />,
  },
];

export const ThinkingTelemetry: React.FC = () => {
  const [activeStageIndex, setActiveStageIndex] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [isTraceExpanded, setIsTraceExpanded] = useState(true);

  // Real-time stopwatch
  useEffect(() => {
    const start = Date.now();
    const interval = setInterval(() => {
      setElapsedMs(Date.now() - start);
    }, 100);
    return () => clearInterval(interval);
  }, []);

  // Stage progression simulation (progresses realistically across a 15-20s query lifecycle)
  useEffect(() => {
    const t1 = setTimeout(() => setActiveStageIndex(1), 1800);
    const t2 = setTimeout(() => setActiveStageIndex(2), 5200);
    const t3 = setTimeout(() => setActiveStageIndex(3), 10500);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, []);

  const elapsedSeconds = (elapsedMs / 1000).toFixed(1);

  return (
    <div
      data-testid="thinking-telemetry"
      className="animate-settle mb-6 w-full rounded-2xl rounded-tl-xs bg-[#13161F] border border-white/[0.08] p-5 space-y-4 shadow-xl text-[#F1F3F9]"
    >
      {/* Telemetry Header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
        <div className="flex items-center gap-2.5">
          <div className="relative flex h-6 w-6 items-center justify-center rounded-lg bg-[#E59500]/15 border border-[#E59500]/25 text-[#E59500]">
            <span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-[#E59500] opacity-75" />
            <PensieveLogo size={14} color="#E59500" strokeWidth={2} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-[#F1F3F9] tracking-tight">
                Thinking & Verification Pipeline
              </span>
              <span className="inline-flex items-center gap-1 rounded bg-[#E59500]/10 border border-[#E59500]/20 px-1.5 py-0.5 text-[10px] font-mono text-[#E59500] uppercase font-semibold">
                Active Protocol
              </span>
            </div>
            <p className="text-[11px] text-[#8C93A5] mt-0.5">
              Cell-matched grounding & source provenance in progress
            </p>
          </div>
        </div>

        {/* Telemetry Controls & Stopwatch */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-xs font-mono tabular-nums text-[#E59500] bg-[#181C28] border border-white/[0.08] px-2.5 py-1 rounded-lg">
            <Loader2 className="h-3 w-3 animate-spin text-[#E59500]" />
            <span>{elapsedSeconds}s</span>
          </div>

          <button
            onClick={() => setIsTraceExpanded(!isTraceExpanded)}
            className="text-[11px] text-[#8C93A5] hover:text-[#F1F3F9] transition-colors cursor-pointer flex items-center gap-1"
          >
            <span>{isTraceExpanded ? "Hide Trace" : "Show Trace"}</span>
            {isTraceExpanded ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </button>
        </div>
      </div>

      {/* Multi-Stage Stepper Trace */}
      {isTraceExpanded && (
        <div className="space-y-3 pt-1 animate-settle">
          {STAGES.map((stage, idx) => {
            const isDone = idx < activeStageIndex;
            const isActive = idx === activeStageIndex;
            const isPending = idx > activeStageIndex;

            return (
              <div
                key={stage.id}
                data-testid={`telemetry-stage-${stage.id}`}
                className={`flex items-start gap-3 rounded-xl p-2.5 transition-all ${
                  isActive
                    ? "bg-[#181C28] border border-[#E59500]/30 shadow-[0_0_20px_rgba(229,149,0,0.08)]"
                    : isDone
                    ? "bg-white/[0.015] border border-white/[0.06]"
                    : "opacity-40 border border-transparent"
                }`}
              >
                {/* Status Beacon Indicator */}
                <div className="mt-0.5 shrink-0">
                  {isDone ? (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/30">
                      <Check className="h-3 w-3 stroke-[2.5]" />
                    </div>
                  ) : isActive ? (
                    <div className="relative flex h-5 w-5 items-center justify-center rounded-full bg-[#E59500]/20 text-[#E59500] border border-[#E59500]/40">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#E59500] opacity-50" />
                      <Loader2 className="h-3 w-3 animate-spin" />
                    </div>
                  ) : (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-white/5 border border-white/10 text-[#585E70]">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#585E70]" />
                    </div>
                  )}
                </div>

                {/* Stage Description */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-medium truncate ${
                          isActive
                            ? "text-[#F1F3F9] font-semibold"
                            : isDone
                            ? "text-[#C2C7D4]"
                            : "text-[#8C93A5]"
                        }`}
                      >
                        {stage.title}
                      </span>
                    </div>

                    <span className="text-[10px] font-mono uppercase tracking-wider shrink-0 text-[#8C93A5]">
                      {isDone ? (
                        <span className="text-[#10B981]">Done</span>
                      ) : isActive ? (
                        <span className="text-[#E59500]">Running...</span>
                      ) : (
                        <span>Queued</span>
                      )}
                    </span>
                  </div>

                  <p className="text-[11px] text-[#8C93A5] mt-0.5 leading-relaxed font-sans">
                    {stage.detail}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Grounding Engine Metadata Footer */}
      <div className="flex items-center justify-between border-t border-white/[0.06] pt-2.5 text-[10px] text-[#8C93A5] font-mono">
        <span className="flex items-center gap-1.5">
          <Cpu className="h-3 w-3 text-[#E59500]" />
          <span>Execution Engine: Qdrant Vector Search + rapidOCR table parity</span>
        </span>
        <span className="tabular-nums">Stage {activeStageIndex + 1} of 4</span>
      </div>
    </div>
  );
};
