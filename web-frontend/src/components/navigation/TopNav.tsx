"use client";

import {
    TrendingUp,
    Search,
    Zap,
    HelpCircle,
    Star,
    Download,
    RefreshCw,
    Loader2,
    Monitor,
    Lightbulb,
    Microscope,
    Briefcase,
    Brain,
    Command,
    Map,
    FlaskConical,
    Store,
    Sparkles,
    Rocket,
    Activity,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

export type ViewId = "terminal" | "market" | "ideas" | "analysis" | "portfolio" | "system" | "pilot" | "strategy-lab" | "marketplace" | "ai-assistant" | "alpha-engine";

interface TopNavProps {
    activeView: ViewId;
    onViewChange: (view: ViewId) => void;
    // Search
    ticker: string;
    onTickerChange: (value: string) => void;
    onAnalyze: () => void;
    isLoading: boolean;
    // Toolbar actions
    showCacheBadge: boolean;
    cachedAt?: string | null;
    onForceRefresh?: () => void;
    showExport: boolean;
    onExport?: () => void;
    showWatchlistToggle: boolean;
    inWatchlist: boolean;
    onToggleWatchlist?: () => void;
    onOpenHelp: () => void;
    onOpenCommandPalette: () => void;
    // Analysis status badge
    analysisScore?: number | null;
    analysisLoading?: boolean;
}

// ─── Tab Config ───────────────────────────────────────────────────────────────

const TABS: { id: ViewId; label: string; icon: React.ReactNode; title: string }[] = [
    { id: "terminal", label: "Terminal", icon: <Monitor size={13} />, title: "Investment decisions — score, verdict, allocation" },
    { id: "market", label: "Market", icon: <Map size={13} />, title: "Market regime, sector heatmap, signal clusters" },
    { id: "ideas", label: "Ideas", icon: <Lightbulb size={13} />, title: "AI-ranked investment opportunities" },
    { id: "analysis", label: "Analysis", icon: <Microscope size={13} />, title: "Full fundamental + technical evidence" },
    { id: "portfolio", label: "Portfolio", icon: <Briefcase size={13} />, title: "Risk analysis & position sizing" },
    { id: "system", label: "System", icon: <Brain size={13} />, title: "Signal health, drift alerts, providers" },
    { id: "pilot", label: "Pilot", icon: <Rocket size={13} />, title: "12-week paper trading validation" },
    { id: "strategy-lab", label: "Strategy Lab", icon: <FlaskConical size={13} />, title: "Bloomberg-style research workspace" },
    { id: "marketplace", label: "Marketplace", icon: <Store size={13} />, title: "Pre-built institutional strategies" },
    { id: "ai-assistant", label: "AI Assistant", icon: <Sparkles size={13} />, title: "Knowledge Graph conversational AI" },
    { id: "alpha-engine", label: "Alpha Engine", icon: <Activity size={13} />, title: "8-factor quantitative alpha scoring and ranking" },
];

// ─── Component ────────────────────────────────────────────────────────────────

export default function TopNav({
    activeView,
    onViewChange,
    ticker,
    onTickerChange,
    onAnalyze,
    isLoading,
    showCacheBadge,
    cachedAt,
    onForceRefresh,
    showExport,
    onExport,
    showWatchlistToggle,
    inWatchlist,
    onToggleWatchlist,
    onOpenHelp,
    onOpenCommandPalette,
    analysisScore,
    analysisLoading,
}: TopNavProps) {
    return (
        <header className="flex flex-col gap-3" style={{ position: 'sticky', top: 0, zIndex: 50 }}>
            {/* ── Row 1: Logo + Search + Actions ── */}
            <div className="flex flex-col md:flex-row justify-between items-center gap-4"
                style={{
                    background: 'rgba(6, 9, 19, 0.85)',
                    backdropFilter: 'blur(20px) saturate(1.3)',
                    WebkitBackdropFilter: 'blur(20px) saturate(1.3)',
                    borderRadius: '16px',
                    padding: '12px 16px',
                    border: '1px solid rgba(212, 175, 55, 0.06)',
                    boxShadow: '0 8px 32px -8px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)',
                }}>
                <div className="flex items-center gap-3">
                    <div className="relative bg-gradient-to-br from-[#d4af37] to-[#b8962e] p-2.5 rounded-xl shadow-[0_0_24px_-4px_rgba(212,175,55,0.4)] breathe">
                        <TrendingUp size={22} className="text-black" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-black gold-gradient tracking-tighter leading-none">
                            365 ADVISERS
                        </h1>
                        <p className="text-[8px] font-mono text-gray-600 uppercase tracking-[0.2em] mt-0.5">
                            Investment Intelligence Terminal
                        </p>
                    </div>
                </div>

                <div className="flex gap-2 w-full md:w-auto items-center">
                    {/* Search */}
                    <div className="relative flex-1 md:w-64">
                        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" size={15} />
                        <input
                            type="text"
                            id="ticker-input"
                            placeholder="Ticker (e.g. NVDA)"
                            className="w-full bg-[#161b22] border border-[#30363d] pl-10 pr-4 py-2 rounded-2xl text-sm focus:outline-none focus:border-[#d4af37] focus:ring-2 focus:ring-[#d4af37]/15 transition-all placeholder:text-gray-600"
                            value={ticker}
                            onChange={(e) => onTickerChange(e.target.value.toUpperCase())}
                            onKeyDown={(e) => e.key === "Enter" && onAnalyze()}
                        />
                    </div>

                    {/* Analyze */}
                    <button
                        id="analyze-btn"
                        onClick={onAnalyze}
                        disabled={isLoading}
                        className="bg-gradient-to-r from-[#d4af37] to-[#e8c84a] text-black font-bold px-5 py-2.5 rounded-2xl hover:brightness-110 active:scale-95 transition-all disabled:opacity-50 flex items-center gap-2 text-sm"
                        style={{
                            boxShadow: '0 0 24px -4px rgba(212,175,55,0.45), 0 4px 12px -2px rgba(212,175,55,0.2)',
                        }}
                    >
                        {isLoading ? (
                            <><Loader2 className="animate-spin" size={14} /><span>Analyzing…</span></>
                        ) : (
                            <><Zap size={14} /><span>Analyze</span></>
                        )}
                    </button>

                    {/* Toolbar */}
                    <div className="flex items-center gap-1 glass-card px-2 py-1 border-[#30363d] rounded-2xl">
                        {showCacheBadge && cachedAt && onForceRefresh && (
                            <button
                                onClick={onForceRefresh}
                                disabled={isLoading}
                                title="Force fresh analysis"
                                className="p-1.5 rounded-xl text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10 transition-all disabled:opacity-40"
                            >
                                <RefreshCw size={13} />
                            </button>
                        )}
                        {showExport && (
                            <button
                                onClick={onExport}
                                title="Export Report"
                                className="p-1.5 rounded-xl text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10 transition-all"
                            >
                                <Download size={13} />
                            </button>
                        )}
                        {showWatchlistToggle && (
                            <button
                                onClick={onToggleWatchlist}
                                title={inWatchlist ? "Remove from watchlist" : "Add to watchlist"}
                                className={`p-1.5 rounded-xl transition-all ${inWatchlist
                                    ? "text-[#d4af37] hover:text-red-400"
                                    : "text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10"
                                    }`}
                            >
                                {inWatchlist ? <Star size={14} fill="currentColor" /> : <Star size={14} />}
                            </button>
                        )}

                        {/* Command Palette trigger */}
                        <button
                            onClick={onOpenCommandPalette}
                            title="Command Palette (Ctrl+K)"
                            className="p-1.5 rounded-xl text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10 transition-all"
                        >
                            <Command size={13} />
                        </button>

                        {/* Help */}
                        <button
                            id="help-btn"
                            onClick={onOpenHelp}
                            title="Help Center (Shift+?)"
                            className="p-1.5 rounded-xl text-gray-500 hover:text-[#d4af37] hover:bg-[#d4af37]/10 transition-all"
                        >
                            <HelpCircle size={13} />
                        </button>
                    </div>
                </div>
            </div>

            {/* ── Row 2: Tab Navigation ── */}
            <div className="flex gap-1 p-1 glass-card border-[#30363d] rounded-2xl w-full overflow-x-auto scan-lines">
                {TABS.map((tab) => {
                    const isActive = activeView === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => onViewChange(tab.id)}
                            aria-current={isActive ? "page" : undefined}
                            title={tab.title}
                            className={`relative flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all whitespace-nowrap ${isActive
                                ? "tab-active"
                                : "text-gray-500 tab-inactive"
                                }`}
                        >
                            {/* Active dot indicator */}
                            {isActive && (
                                <span
                                    className="absolute -top-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-[#d4af37]"
                                    style={{ boxShadow: '0 0 6px 1px rgba(212,175,55,0.6)' }}
                                />
                            )}
                            {tab.icon}
                            {tab.label}
                            {tab.id === "analysis" && analysisLoading && (
                                <Loader2 size={9} className="animate-spin" />
                            )}
                            {tab.id === "analysis" && analysisScore != null && !analysisLoading && (
                                <span className="bg-[#d4af37]/20 text-[#d4af37] rounded-md px-1.5 text-[8px] font-mono font-bold">
                                    {analysisScore.toFixed(1)}
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>

            {/* Separator */}
            <div className="separator-gold" />
        </header>
    );
}
