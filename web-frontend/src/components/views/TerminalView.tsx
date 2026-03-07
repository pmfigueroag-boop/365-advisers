"use client";

/**
 * TerminalView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Investment Terminal (v2.0) — Decision First layout.
 *
 * Layout:
 * ┌────────────────────────────────┬─────────────────────────────┐
 * │ OpportunityVerdict             │ SignalEnvironmentPanel       │
 * │ (score, verdict, allocation)   │ (CASE, regime, crowding)    │
 * ├────────────────────────────────┤                             │
 * │ QuickActionBar                 │ KeyCatalystsPanel           │
 * ├────────────────────────────────┤ RiskSnapshotPanel           │
 * │ TopSignalsList                 │                             │
 * ├────────────────────────────────┴─────────────────────────────┤
 * │ CoverageHeatmap (Watchlist)                                  │
 * └──────────────────────────────────────────────────────────────┘
 */

import { Activity, Zap, ShieldCheck, LineChart, Radio, Star, Search } from "lucide-react";
import OpportunityVerdict from "@/components/terminal/OpportunityVerdict";
import SignalEnvironmentPanel from "@/components/terminal/SignalEnvironmentPanel";
import KeyCatalystsPanel from "@/components/terminal/KeyCatalystsPanel";
import RiskSnapshotPanel from "@/components/terminal/RiskSnapshotPanel";
import QuickActionBar from "@/components/decision/QuickActionBar";
import TopSignalsList from "@/components/insight/TopSignalsList";
import SignalBadge from "@/components/shared/SignalBadge";
import type { CombinedState } from "@/hooks/useCombinedStream";
import type { SignalProfileResponse } from "@/hooks/useAlphaSignals";
import type { WatchlistItem } from "@/hooks/useWatchlist";
import type { CrowdingAssessment } from "@/hooks/useCrowding";

// ─── Types ────────────────────────────────────────────────────────────────────

interface TerminalViewProps {
    combined: CombinedState;
    alphaProfile: SignalProfileResponse | null;
    watchlistItems: WatchlistItem[];
    crowding?: CrowdingAssessment | null;
    onAnalyze: (ticker: string) => void;
    onNavigateAnalysis: () => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function TerminalView({
    combined,
    alphaProfile,
    watchlistItems,
    crowding,
    onAnalyze,
    onNavigateAnalysis,
}: TerminalViewProps) {
    const isIdle = combined.status === "idle";
    const isLoading = combined.status === "fetching_data" || combined.status === "fundamental" || combined.status === "technical" || combined.status === "decision";
    const isComplete = combined.status === "complete";
    const isError = combined.status === "error";

    // ── Empty state ──────────────────────────────────────────────────────────
    if (isIdle && watchlistItems.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center flex-1 text-center mesh-gradient rounded-2xl py-20 px-6"
                style={{ animation: "fadeSlideIn 0.4s ease both" }}>
                <div className="w-24 h-24 bg-[#161b22] rounded-3xl flex items-center justify-center mb-8 border border-[#d4af37]/15 glow-ring">
                    <Activity size={44} className="text-[#d4af37]/40 breathe" />
                </div>
                <h2 className="text-2xl font-black gold-gradient mb-3" style={{ fontFamily: "var(--font-insight)" }}>
                    Investment Intelligence Terminal
                </h2>
                <p className="text-gray-500 max-w-md mx-auto leading-relaxed text-sm mb-2">
                    Institutional-grade investment analysis. Type a ticker to convene the
                    Investment Committee and get your decision in seconds.
                </p>
                <p className="text-[#d4af37]/60 text-xs font-mono mb-8 blink-cursor">Search or type a ticker above</p>
                <div className="flex gap-3 text-xs font-mono text-gray-500 flex-wrap justify-center stagger-children">
                    <span className="flex items-center gap-1.5 glass-card px-3 py-1.5 border-[#30363d]"><ShieldCheck size={12} className="text-[#d4af37]/60" /> Fundamental</span>
                    <span className="flex items-center gap-1.5 glass-card px-3 py-1.5 border-[#30363d]"><LineChart size={12} className="text-[#60a5fa]/60" /> Technical</span>
                    <span className="flex items-center gap-1.5 glass-card px-3 py-1.5 border-[#30363d]"><Zap size={12} className="text-[#c084fc]/60" /> Combined</span>
                    <span className="flex items-center gap-1.5 glass-card px-3 py-1.5 border-[#30363d]"><Radio size={12} className="text-emerald-400/60" /> Alpha Signals</span>
                </div>
            </div>
        );
    }

    // ── Coverage List (idle + has watchlist) ─────────────────────────────────
    if (isIdle && watchlistItems.length > 0) {
        return (
            <div className="space-y-5" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-base font-black uppercase tracking-widest text-gray-300">Coverage List</h2>
                        <p className="text-xs text-gray-600 mt-0.5">Select an asset to convene the Investment Committee</p>
                    </div>
                    <span className="text-[9px] font-mono text-gray-700 bg-[#161b22] border border-[#30363d] rounded-lg px-2 py-1">
                        {watchlistItems.length} asset{watchlistItems.length !== 1 ? "s" : ""} tracked
                    </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {watchlistItems.map((item, i) => {
                        const sig = item.lastSignal ?? "—";
                        const sigColor =
                            sig === "BUY" ? "text-green-400 border-green-500/30 bg-green-500/8" :
                                sig === "SELL" ? "text-red-400 border-red-500/30 bg-red-500/8" :
                                    sig === "HOLD" ? "text-yellow-400 border-yellow-500/30 bg-yellow-500/8" :
                                        "text-gray-500 border-[#30363d] bg-transparent";

                        return (
                            <button
                                key={item.ticker}
                                onClick={() => onAnalyze(item.ticker)}
                                className="glass-card p-5 border-[#30363d] text-left hover:border-[#d4af37]/40 hover:bg-[#d4af37]/3 transition-all group"
                                style={{ animation: `fadeSlideIn 0.35s ease ${i * 0.07}s both` }}
                            >
                                <div className="flex items-start justify-between mb-3">
                                    <div>
                                        <p className="text-lg font-black tracking-tight text-white" style={{ fontFamily: "var(--font-data)" }}>
                                            {item.ticker}
                                        </p>
                                        <p className="text-[10px] text-gray-600 truncate max-w-[140px]">{item.name ?? item.ticker}</p>
                                    </div>
                                    {sig !== "—" && (
                                        <span className={`text-[9px] font-black px-2 py-1 rounded-md border uppercase flex-shrink-0 ${sigColor}`}>
                                            {sig}
                                        </span>
                                    )}
                                </div>
                                <div className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-wider text-gray-600 group-hover:text-[#d4af37] transition-colors">
                                    <Zap size={10} />
                                    Run Committee
                                </div>
                            </button>
                        );
                    })}

                    <div className="glass-card p-5 border-[#30363d] border-dashed flex flex-col items-center justify-center gap-2 text-gray-700 min-h-[110px]">
                        <Search size={18} className="opacity-40" />
                        <p className="text-[10px] font-bold uppercase tracking-widest opacity-50">Analyze new asset</p>
                    </div>
                </div>
            </div>
        );
    }

    // ── Loading state ───────────────────────────────────────────────────────
    if (isLoading && !combined.fundamentalDataReady) {
        return (
            <div className="flex flex-col items-center justify-center flex-1 py-16">
                <div className="orbital-spinner mb-6">
                    <div className="orbital-ring orbital-ring-1" />
                    <div className="orbital-ring orbital-ring-2" />
                    <div className="orbital-ring orbital-ring-3" />
                    <Activity className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[#d4af37] breathe" size={22} />
                </div>
                <p className="text-[#d4af37] font-bold tracking-widest text-sm uppercase mb-3">
                    Fetching Market Data for {combined.ticker}…
                </p>
                <div className="flex items-center gap-2 text-[8px] font-mono uppercase tracking-widest">
                    <span className="text-[#d4af37]">Data</span>
                    <div className="w-3 h-px bg-[#d4af37]/30" />
                    <span className="text-gray-700">Analysts</span>
                    <div className="w-3 h-px bg-[#30363d]" />
                    <span className="text-gray-700">Technical</span>
                    <div className="w-3 h-px bg-[#30363d]" />
                    <span className="text-gray-700">CIO</span>
                </div>
            </div>
        );
    }

    // ── Error state ─────────────────────────────────────────────────────────
    if (isError) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-center">
                <Activity size={36} className="text-red-500 mb-3" />
                <p className="text-red-400 font-mono text-sm">{combined.error}</p>
            </div>
        );
    }

    // ── Active Terminal — Decision First layout ─────────────────────────────
    return (
        <div className="space-y-5" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Main Grid — Verdict + Environment */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {/* Left: Decision Column (2/3) */}
                <div className="lg:col-span-2 space-y-4">
                    {/* Opportunity Verdict */}
                    <OpportunityVerdict combined={combined} alphaProfile={alphaProfile} />

                    {/* Quick Actions */}
                    {isComplete && (
                        <QuickActionBar
                            ticker={combined.ticker ?? ""}
                            onDeepAnalysis={onNavigateAnalysis}
                            onExport={() => {
                                document.body.setAttribute("data-print-date", new Date().toLocaleString());
                                window.print();
                            }}
                            onRefresh={() => onAnalyze(combined.ticker ?? "")}
                        />
                    )}

                    {/* Top Signals */}
                    {isComplete && (
                        <div className="glass-card p-5 border-[#30363d]">
                            <TopSignalsList
                                signals={alphaProfile?.signals ?? []}
                                totalFired={alphaProfile?.fired_signals}
                                totalSignals={alphaProfile?.total_signals}
                            />
                        </div>
                    )}
                </div>

                {/* Right: Context Column (1/3) */}
                <div className="space-y-4">
                    <SignalEnvironmentPanel alphaProfile={alphaProfile} crowding={crowding} />
                    <KeyCatalystsPanel cioMemo={combined.decision?.cio_memo ?? null} />
                    <RiskSnapshotPanel
                        positionSizing={combined.positionSizing}
                        technical={combined.technical}
                        crowding={crowding}
                    />
                </div>
            </div>

            {/* Coverage Heatmap */}
            {isComplete && watchlistItems.length > 0 && (
                <div className="glass-card p-4 border-[#30363d]">
                    <div className="flex items-center gap-2 mb-3">
                        <Star size={11} className="text-[#d4af37]" />
                        <span className="text-[9px] font-black uppercase tracking-widest text-gray-500">Coverage List</span>
                    </div>
                    <div className="flex gap-2 flex-wrap">
                        {watchlistItems.map((item) => {
                            const isActive = item.ticker === combined.ticker;
                            return (
                                <button
                                    key={item.ticker}
                                    onClick={() => onAnalyze(item.ticker)}
                                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-[11px] font-bold transition-all ${isActive
                                        ? "bg-[#d4af37]/15 border border-[#d4af37]/40 text-[#d4af37]"
                                        : "bg-[#161b22] border border-[#30363d] text-gray-400 hover:border-[#d4af37]/30 hover:text-gray-200"
                                        }`}
                                >
                                    <span style={{ fontFamily: "var(--font-data)" }}>{item.ticker}</span>
                                    {item.lastSignal && <SignalBadge signal={item.lastSignal} size="xs" />}
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
