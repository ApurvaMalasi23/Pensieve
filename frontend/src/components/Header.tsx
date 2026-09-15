"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import { fetchHealth } from "@/lib/api";
import { HealthResponse } from "@/types/api";
import { WifiOff, Search } from "lucide-react";
import { PensieveLogo } from "./PensieveLogo";

interface HeaderProps {
  onHealthStatusChange?: (isHealthy: boolean, healthData?: HealthResponse) => void;
  onOpenCommandPalette?: () => void;
  onToggleSidebar?: () => void;
  isSidebarCollapsed?: boolean;
  isShowcaseMode?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onHealthStatusChange,
  onOpenCommandPalette,
  onToggleSidebar,
  isSidebarCollapsed = false,
  isShowcaseMode = false,
}) => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isConnected, setIsConnected] = useState<boolean | null>(null);

  useEffect(() => {
    let timer: NodeJS.Timeout;

    const check = async () => {
      try {
        const data = await fetchHealth();
        setHealth(data);
        setIsConnected(true);
        onHealthStatusChange?.(data.status === "ok", data);
      } catch (err) {
        setIsConnected(false);
        setHealth(null);
        onHealthStatusChange?.(false);
      }
    };

    check();
    timer = setInterval(check, 15000);
    return () => clearInterval(timer);
  }, [onHealthStatusChange]);

  return (
    <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between px-5 sm:px-6 border-b border-white/[0.04] bg-[#0B0B0D]/85 backdrop-blur-2xl shadow-[0_4px_30px_rgba(0,0,0,0.5)]">
      {/* Brand Identity: Jony Ive Precision Lockup */}
      <div className="flex items-center gap-3 sm:gap-4">
        <div className="flex items-center gap-2.5 group cursor-default">
          <div className="relative flex items-center justify-center">
            <div className="absolute inset-0 rounded-full bg-[#CBB282]/15 blur-sm -z-10" />
            <PensieveLogo size={21} color="#CBB282" strokeWidth={3.2} glow />
          </div>
          <span className="font-serif text-[15px] font-medium tracking-[0.14em] text-[#F7F7F4] uppercase">
            Pensieve
          </span>
        </div>
        <div className="h-3.5 w-px bg-white/[0.08] hidden sm:block" />
        <span className="text-[12px] text-[#82807A] italic font-serif hidden sm:inline tracking-wide">
          Financial Grounding & Numeric Verification
        </span>
      </div>

      {/* Backend & Qdrant Live Status: Quiet luxury telemetry */}
      <div className="flex items-center gap-2.5 sm:gap-3">
        {isConnected === false ? (
          <div
            data-testid="backend-disconnected-badge"
            className="flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] text-[#E06D6D] bg-[#E06D6D]/10 border border-[#E06D6D]/20 backdrop-blur-md"
          >
            <WifiOff className="h-3 w-3 text-[#E06D6D]" />
            <span className="font-medium">Backend Disconnected</span>
          </div>
        ) : health ? (
          <div
            data-testid="health-status-badge"
            className="inline-flex items-center gap-2 rounded-full border border-white/[0.06] bg-white/[0.02] px-3 py-1 text-[11px] backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
          >
            <span className="relative flex h-2 w-2">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-60 ${
                  health.status === "ok" ? "bg-[#52B788]" : "bg-[#D4A373]"
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  health.status === "ok"
                    ? "bg-[#52B788] shadow-[0_0_8px_#52B788]"
                    : "bg-[#D4A373] shadow-[0_0_8px_#D4A373]"
                }`}
              />
            </span>
            <span className="text-[11px] font-medium text-[#F7F7F4]/90">
              {health.status === "ok" ? "Operational" : "Degraded"}
            </span>
            <span className="text-white/20 text-[10px] hidden sm:inline">•</span>
            <span className="text-[11px] text-[#CDCBC4] tabular-nums font-mono hidden sm:inline">
              {health.points_count.toLocaleString()} Chunks Indexed
            </span>
            {(health.showcase_mode || isShowcaseMode) && (
              <>
                <span className="text-white/20 text-[10px] hidden md:inline">•</span>
                <span
                  data-testid="header-showcase-badge"
                  className="hidden md:inline-flex items-center gap-1 rounded-full bg-[#CBB282]/10 border border-[#CBB282]/25 px-2.5 py-0.5 text-[10px] font-mono tracking-wider uppercase text-[#CBB282]"
                >
                  Showcase Demo
                </span>
              </>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs text-[#82807A]">
            <span className="h-1.5 w-1.5 rounded-full bg-white/30 animate-pulse" />
            <span className="text-[11px]">Connecting...</span>
          </div>
        )}

        {/* Global Command Palette Spotlight Button */}
        {onOpenCommandPalette && (
          <button
            onClick={onOpenCommandPalette}
            data-testid="command-palette-trigger"
            className="group flex items-center gap-1.5 text-xs text-[#CDCBC4] hover:text-[#F7F7F4] bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.07] hover:border-[#CBB282]/40 px-3 py-1 rounded-full transition-all duration-200 cursor-pointer shadow-[0_2px_8px_rgba(0,0,0,0.3)]"
            title="Open Command Spotlight (⌘K)"
          >
            <Search className="h-3 w-3 text-[#CBB282] group-hover:scale-105 transition-transform" />
            <span className="hidden sm:inline text-[11px] font-normal">Spotlight</span>
            <kbd className="font-mono text-[10px] text-[#CBB282] font-semibold bg-[#CBB282]/10 px-1.5 py-0.5 rounded border border-[#CBB282]/20">
              ⌘K
            </kbd>
          </button>
        )}

        {/* Keyboard shortcut hint */}
        <div className="hidden lg:flex items-center gap-1.5 text-[10.5px] text-[#82807A] bg-white/[0.02] border border-white/[0.05] px-2.5 py-1 rounded-full">
          <span>Press</span>
          <kbd className="font-mono text-[10px] text-[#CBB282] font-medium bg-[#CBB282]/10 px-1.5 py-0.5 rounded border border-[#CBB282]/20">/</kbd>
          <span>to ask</span>
        </div>
      </div>
    </header>
  );
};
