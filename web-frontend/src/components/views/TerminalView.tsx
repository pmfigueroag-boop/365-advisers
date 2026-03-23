"use client";

/**
 * TerminalView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Investment Terminal (v4.0) — Decision First layout.
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
import { SlideUp, ScaleIn, FadeIn, StaggerGroup, StaggerItem } from "@/components/shared/MotionWrappers";
import OpportunityVerdict from "@/components/terminal/OpportunityVerdict";
import SignalEnvironmentPanel from "@/components/terminal/SignalEnvironmentPanel";
import ConvergenceMap from "@/components/terminal/ConvergenceMap";
import KeyCatalystsPanel from "@/components/terminal/KeyCatalystsPanel";
import RiskSnapshotPanel from "@/components/terminal/RiskSnapshotPanel";
import QuickActionBar from "@/components/decision/QuickActionBar";
import TopSignalsList from "@/components/insight/TopSignalsList";
import SignalBadge from "@/components/shared/SignalBadge";
import CoverageBadge from "@/components/coverage/CoverageBadge";
import InfoTooltip from "@/components/shared/InfoTooltip";
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
        const trendingTickers = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA"];
        return (
            <div className="flex flex-col items-center justify-center flex-1 mesh-gradient-v2 rounded-2xl particles bg-grid"
                style={{ animation: "fadeSlideIn 0.4s ease both", minHeight: "60vh" }}>

                {/* Hero Section */}
                <div className="ambient-glow">
                    <div className="premium-card p-10 text-center max-w-lg mx-auto"
                        style={{ animation: "verdictReveal 0.6s ease both" }}>

                        {/* Icon */}
                        <div className="w-28 h-28 mx-auto mb-8 rounded-3xl flex items-center justify-center"
                            style={{
                                background: 'linear-gradient(135deg, rgba(22,27,34,0.9), rgba(13,17,26,0.95))',
                                border: '1px solid rgba(212,175,55,0.2)',
                                boxShadow: '0 0 40px -8px rgba(212,175,55,0.15), inset 0 1px 0 rgba(255,255,255,0.05)',
                            }}>
                            <Activity size={48} className="text-[#d4af37] breathe" />
                        </div>

                        {/* Title */}
                        <h2 className="text-3xl font-black gold-gradient mb-3"
                            style={{ fontFamily: "var(--font-insight)" }}>
                            Investment Intelligence Terminal
                        </h2>

                        <p className="text-gray-400 max-w-sm mx-auto leading-relaxed text-sm mb-3">
                            Institutional-grade multi-agent analysis. Type a ticker to convene the
                            Investment Committee and get your decision in seconds.
                        </p>

                        <p className="text-[#d4af37]/60 text-xs font-mono mb-8 blink-cursor">
                            Search or type a ticker above
                        </p>

                        {/* Capability badges */}
                        <div className="flex gap-2.5 text-xs font-mono text-gray-500 flex-wrap justify-center mb-8 stagger-children">
                            <span className="flex items-center gap-1.5 glass-card px-3.5 py-2 border-[#30363d]"><ShieldCheck size={12} className="text-[#d4af37]/70" /> Fundamental</span>
                            <span className="flex items-center gap-1.5 glass-card px-3.5 py-2 border-[#30363d]"><LineChart size={12} className="text-[#60a5fa]/70" /> Technical</span>
                            <span className="flex items-center gap-1.5 glass-card px-3.5 py-2 border-[#30363d]"><Zap size={12} className="text-[#c084fc]/70" /> Combined</span>
                            <span className="flex items-center gap-1.5 glass-card px-3.5 py-2 border-[#30363d]"><Radio size={12} className="text-emerald-400/70" /> Alpha Signals</span>
                        </div>

                        {/* Trending Tickers */}
                        <div>
                            <p className="text-[8px] font-black uppercase tracking-[0.2em] text-gray-600 mb-3">Trending</p>
                            <div className="flex flex-wrap gap-2 justify-center">
                                {trendingTickers.map((t, i) => (
                                    <button
                                        key={t}
                                        onClick={() => onAnalyze(t)}
                                        className="ticker-chip"
                                        style={{ animation: `fadeSlideIn 0.35s ease ${0.15 + i * 0.06}s both` }}
                                    >
                                        <span className="ticker-chip-icon" />
                                        {t}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // ── Coverage List (idle + has watchlist) ─────────────────────────────────
    if (isIdle && watchlistItems.length > 0) {
        return (
            <div className="space-y-5 bg-grid" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
                {/* Quick onboarding strip for users with < 3 assets */}
                {watchlistItems.length < 3 && (
                    <div className="flex items-center gap-3 px-4 py-3 rounded-xl"
                        style={{
                            background: 'linear-gradient(135deg, rgba(212,175,55,0.06), rgba(59,130,246,0.04))',
                            border: '1px solid rgba(212,175,55,0.12)',
                        }}>
                        <Zap size={14} className="text-[#d4af37] flex-shrink-0" />
                        <p className="text-[11px] text-gray-400">
                            <span className="text-[#d4af37] font-bold">Tip:</span> Type a ticker in the search bar above or explore
                            <span className="text-[#d4af37] font-bold"> Ideas</span> to discover opportunities across 200+ stocks.
                        </p>
                    </div>
                )}

                <div className="flex items-center justify-between">
                    <div>
                        <InfoTooltip text="Assets you are tracking. Select one to run the full Investment Committee analysis." position="bottom">
                            <h2 className="text-base font-black uppercase tracking-widest text-gray-300">Coverage List</h2>
                        </InfoTooltip>
                        <p className="text-xs text-gray-600 mt-0.5">Select an asset to convene the Investment Committee</p>
                    </div>
                    <span className="text-[10px] font-mono text-gray-500 glass-card border border-[#30363d] rounded-lg px-2.5 py-1.5"
                        style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)' }}>
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
                        const sigDotColor =
                            sig === "BUY" ? "#22c55e" : sig === "SELL" ? "#ef4444" : sig === "HOLD" ? "#eab308" : "#4b5563";

                        // Signal transition indicator
                        const prev = item.prevSignal;
                        const SIGNAL_RANK: Record<string, number> = { SELL: 0, HOLD: 1, BUY: 2 };
                        const hasTransition = prev && prev !== sig;
                        const isUpgrade = hasTransition && (SIGNAL_RANK[sig] ?? 1) > (SIGNAL_RANK[prev] ?? 1);
                        const isDowngrade = hasTransition && (SIGNAL_RANK[sig] ?? 1) < (SIGNAL_RANK[prev] ?? 1);

                        return (
                            <button
                                key={item.ticker}
                                onClick={() => onAnalyze(item.ticker)}
                                className="premium-card p-5 text-left group scan-lines"
                                style={{
                                    animation: `fadeSlideIn 0.35s ease ${i * 0.07}s both`,
                                    transition: 'transform 0.25s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.25s ease',
                                }}
                                onMouseEnter={(e) => {
                                    (e.currentTarget as HTMLElement).style.transform = 'translateY(-3px)';
                                    (e.currentTarget as HTMLElement).style.boxShadow = '0 12px 40px -8px rgba(212,175,55,0.15), 0 0 0 1px rgba(212,175,55,0.15)';
                                }}
                                onMouseLeave={(e) => {
                                    (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
                                    (e.currentTarget as HTMLElement).style.boxShadow = '';
                                }}
                            >
                                <div className="flex items-start justify-between mb-3">
                                    <div className="flex items-center gap-2">
                                        {/* Signal dot */}
                                        <span className="w-2 h-2 rounded-full flex-shrink-0"
                                            style={{ background: sigDotColor, boxShadow: `0 0 8px ${sigDotColor}60` }} />
                                        <div>
                                            <p className="text-lg font-black tracking-tight text-white" style={{ fontFamily: "var(--font-data)" }}>
                                                {item.ticker}
                                            </p>
                                            <p className="text-[10px] text-gray-600 truncate max-w-[140px]">{item.name ?? item.ticker}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-1.5 flex-shrink-0">
                                        {/* Signal transition indicator */}
                                        {hasTransition && (
                                            <span
                                                className={`text-[8px] font-mono ${isUpgrade ? "text-green-400" : "text-red-400"}`}
                                                title={`${prev} → ${sig}`}
                                            >
                                                {isUpgrade ? "▲" : "▼"} {prev}
                                            </span>
                                        )}
                                        {sig !== "—" && (
                                            <span className={`text-[9px] font-black px-2 py-1 rounded-md border uppercase ${sigColor}`}>
                                                {sig}
                                            </span>
                                        )}
                                    </div>
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
        <div className="space-y-5 bg-grid-dense">
            {/* Main Grid — Verdict + Environment */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {/* Left: Decision Column (2/3) */}
                <div className="lg:col-span-2 space-y-4">
                    {/* Opportunity Verdict + Coverage Badge */}
                    <ScaleIn delay={0.05}>
                        <OpportunityVerdict combined={combined} alphaProfile={alphaProfile} />
                    </ScaleIn>
                    {combined.sourceCoverage && (
                        <FadeIn delay={0.2}>
                            <div style={{ marginTop: -8, display: "flex", justifyContent: "flex-end" }}>
                                <CoverageBadge
                                    completeness={combined.sourceCoverage.analysis_completeness}
                                    label={combined.sourceCoverage.completeness_label}
                                />
                            </div>
                        </FadeIn>
                    )}

                    {/* Quick Actions */}
                    {isComplete && (
                        <SlideUp delay={0.15}>
                            <QuickActionBar
                                ticker={combined.ticker ?? ""}
                                onDeepAnalysis={onNavigateAnalysis}
                                onExport={() => {
                                    document.body.setAttribute("data-print-date", new Date().toLocaleString());
                                    window.print();
                                }}
                                onRefresh={() => onAnalyze(combined.ticker ?? "")}
                            />
                        </SlideUp>
                    )}

                    {isComplete && (
                        <SlideUp delay={0.25}>
                            <ConvergenceMap combined={combined} />
                        </SlideUp>
                    )}

                    {/* Top Signals */}
                    {isComplete && (
                        <SlideUp delay={0.35}>
                            <div className="glass-card p-5 border-[#30363d]">
                                <TopSignalsList
                                    signals={alphaProfile?.signals ?? []}
                                    totalFired={alphaProfile?.fired_signals}
                                    totalSignals={alphaProfile?.total_signals}
                                />
                            </div>
                        </SlideUp>
                    )}
                </div>

                {/* Right: Context Column (1/3) */}
                <StaggerGroup className="space-y-4">
                    <StaggerItem>
                        <SignalEnvironmentPanel alphaProfile={alphaProfile} alphaStack={combined.alphaStack} crowding={crowding} />
                    </StaggerItem>
                    <StaggerItem>
                        <KeyCatalystsPanel cioMemo={combined.decision?.cio_memo ?? null} />
                    </StaggerItem>
                    <StaggerItem>
                        <RiskSnapshotPanel
                            positionSizing={combined.positionSizing}
                            technical={combined.technical}
                            crowding={crowding}
                        />
                    </StaggerItem>
                </StaggerGroup>
            </div>

            {/* Coverage Heatmap */}
            {isComplete && watchlistItems.length > 0 && (
                <FadeIn delay={0.4}>
                    <div className="glass-card p-4 border-[#30363d]">
                        <div className="flex items-center gap-2 mb-3">
                            <Star size={11} className="text-[#d4af37]" />
                            <InfoTooltip text="Your watchlist of analyzed assets. Click any to switch and view its analysis." position="bottom">
                                <span className="text-[9px] font-black uppercase tracking-widest text-gray-500">Coverage List</span>
                            </InfoTooltip>
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
                </FadeIn>
            )}
        </div>
    );
}
