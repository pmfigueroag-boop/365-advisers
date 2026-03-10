"use client";

/**
 * IdeaExplorerView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Full-width Idea Explorer — promoted from the sidebar IdeasPanel
 * to its own primary view with ranking table, filters, and preview.
 */

import { useState, useMemo } from "react";
import {
    Lightbulb,
    Zap,
    X,
    Loader2,
    TrendingUp,
    Diamond,
    BarChart3,
    RefreshCw,
    Filter,
    Rocket,
    Shield,
    Activity,
    Search,
    AlertTriangle,
} from "lucide-react";
import type { IdeaItem } from "@/hooks/useIdeasEngine";

// ─── Config ───────────────────────────────────────────────────────────────────

const TYPE_CONFIG: Record<string, { label: string; color: string; bg: string; border: string; icon: React.ReactNode }> = {
    value: { label: "Value", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30", icon: <Diamond size={11} /> },
    quality: { label: "Quality", color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/30", icon: <Shield size={11} /> },
    growth: { label: "Growth", color: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/30", icon: <TrendingUp size={11} /> },
    momentum: { label: "Momentum", color: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/30", icon: <Rocket size={11} /> },
    reversal: { label: "Reversal", color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/30", icon: <Activity size={11} /> },
    event: { label: "Event", color: "text-cyan-400", bg: "bg-cyan-500/10", border: "border-cyan-500/30", icon: <AlertTriangle size={11} /> },
};

// ─── Types ────────────────────────────────────────────────────────────────────

interface IdeaExplorerViewProps {
    ideas: IdeaItem[];
    scanStatus: "idle" | "scanning" | "done" | "error";
    error: string | null;
    onScan: () => void;
    onAnalyze: (ticker: string) => void;
    onDismiss: (id: string) => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function IdeaExplorerView({
    ideas,
    scanStatus,
    error,
    onScan,
    onAnalyze,
    onDismiss,
}: IdeaExplorerViewProps) {
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [filterType, setFilterType] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [sortBy, setSortBy] = useState<"score" | "ticker">("score");

    // Filtered & sorted ideas
    const displayIdeas = useMemo(() => {
        let filtered = ideas;
        if (filterType) {
            filtered = filtered.filter((i) => i.idea_type === filterType);
        }
        if (searchQuery) {
            const q = searchQuery.toUpperCase();
            filtered = filtered.filter((i) => i.ticker.includes(q));
        }
        if (sortBy === "score") {
            filtered = [...filtered].sort((a, b) => b.signal_strength - a.signal_strength);
        } else {
            filtered = [...filtered].sort((a, b) => a.ticker.localeCompare(b.ticker));
        }
        return filtered;
    }, [ideas, filterType, searchQuery, sortBy]);

    const selectedIdea = selectedId != null ? ideas.find((i) => i.id === selectedId) : null;

    // Strategy counts
    const typeCounts = useMemo(() => {
        const counts: Record<string, number> = {};
        ideas.forEach((i) => { counts[i.idea_type] = (counts[i.idea_type] || 0) + 1; });
        return counts;
    }, [ideas]);

    return (
        <div className="flex gap-5 min-h-[60vh]" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* ── Left: Filters ── */}
            <div className="w-52 flex-shrink-0 space-y-5 hidden lg:block">
                <div className="glass-card p-4 border-[#30363d]">
                    <div className="flex items-center gap-2 mb-3">
                        <Filter size={12} className="text-gray-500" />
                        <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Filters</span>
                    </div>

                    {/* Scan button */}
                    <button
                        onClick={onScan}
                        disabled={scanStatus === "scanning"}
                        className="w-full bg-gradient-to-r from-[#d4af37] to-[#e8c84a] text-black font-bold px-4 py-2 rounded-xl hover:brightness-110 transition-all disabled:opacity-50 flex items-center justify-center gap-2 text-xs mb-4"
                    >
                        {scanStatus === "scanning" ? (
                            <><Loader2 size={12} className="animate-spin" /> Scanning…</>
                        ) : (
                            <><RefreshCw size={12} /> Scan Universe</>
                        )}
                    </button>

                    {/* Strategy filter */}
                    <p className="text-[9px] font-black uppercase tracking-wider text-gray-500 mb-2">Strategy</p>
                    <div className="space-y-1 mb-4">
                        <button
                            onClick={() => setFilterType(null)}
                            className={`w-full text-left text-[11px] px-2.5 py-1.5 rounded-lg transition-all ${!filterType ? "bg-[#d4af37]/10 text-[#d4af37]" : "text-gray-500 hover:text-gray-300"}`}
                        >
                            All ({ideas.length})
                        </button>
                        {Object.entries(TYPE_CONFIG).map(([key, cfg]) => (
                            <button
                                key={key}
                                onClick={() => setFilterType(filterType === key ? null : key)}
                                className={`w-full text-left text-[11px] px-2.5 py-1.5 rounded-lg transition-all flex items-center gap-2 ${filterType === key ? `${cfg.bg} ${cfg.color}` : "text-gray-500 hover:text-gray-300"}`}
                            >
                                {cfg.icon}
                                {cfg.label}
                                {typeCounts[key] ? <span className="ml-auto text-[9px] font-mono">{typeCounts[key]}</span> : null}
                            </button>
                        ))}
                    </div>

                    {/* Sort */}
                    <p className="text-[9px] font-black uppercase tracking-wider text-gray-500 mb-2">Sort by</p>
                    <div className="flex gap-1">
                        {(["score", "ticker"] as const).map((s) => (
                            <button
                                key={s}
                                onClick={() => setSortBy(s)}
                                className={`flex-1 text-[10px] font-bold uppercase py-1.5 rounded-lg transition-all ${sortBy === s ? "bg-[#30363d] text-white" : "text-gray-600 hover:text-gray-400"}`}
                            >
                                {s}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* ── Center: Ranking Table ── */}
            <div className="flex-1 min-w-0">
                <div className="glass-card border-[#30363d] overflow-hidden">
                    {/* Header */}
                    <div className="flex items-center justify-between px-5 py-4 border-b border-[#30363d]">
                        <div className="flex items-center gap-2">
                            <Lightbulb size={14} className="text-[#d4af37]" />
                            <span className="text-sm font-black uppercase tracking-widest text-gray-300">
                                Opportunity Ranking
                            </span>
                            <span className="text-[9px] font-mono text-gray-600 bg-[#161b22] rounded px-2 py-0.5 border border-[#30363d]">
                                {displayIdeas.length} ideas
                            </span>
                        </div>
                        <div className="relative w-40">
                            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-600" />
                            <input
                                type="text"
                                placeholder="Filter ticker…"
                                className="w-full bg-[#161b22] border border-[#30363d] pl-8 pr-3 py-1.5 rounded-lg text-[11px] focus:outline-none focus:border-[#d4af37]/40 transition-all placeholder:text-gray-700"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value.toUpperCase())}
                            />
                        </div>
                    </div>

                    {/* Table */}
                    <div className="overflow-x-auto">
                        {error && (
                            <div className="px-5 py-3 text-red-400 text-sm bg-red-500/5 border-b border-red-500/20">
                                ⚠ {error}
                            </div>
                        )}
                        {scanStatus === "scanning" && (
                            <div className="flex items-center justify-center gap-2 py-8 text-[#d4af37]">
                                <Loader2 size={16} className="animate-spin" />
                                <span className="text-sm font-bold">Scanning universe…</span>
                            </div>
                        )}
                        {displayIdeas.length === 0 && scanStatus !== "scanning" ? (
                            <div className="flex flex-col items-center justify-center py-16 text-center">
                                <Lightbulb size={28} className="text-gray-700 mb-3" />
                                <p className="text-gray-600 text-sm">No ideas found</p>
                                <p className="text-gray-700 text-xs mt-1">Run a scan to detect opportunities in your watchlist</p>
                            </div>
                        ) : (
                            <table className="w-full text-[11px]">
                                <thead>
                                    <tr className="border-b border-[#30363d] text-gray-600 text-[9px] font-black uppercase tracking-widest">
                                        <th className="text-left px-5 py-2.5 w-8">#</th>
                                        <th className="text-left px-3 py-2.5">Ticker</th>
                                        <th className="text-left px-3 py-2.5">Strategy</th>
                                        <th className="text-left px-3 py-2.5">Confidence</th>
                                        <th className="text-right px-3 py-2.5">Strength</th>
                                        <th className="text-right px-5 py-2.5">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {displayIdeas.map((idea, idx) => {
                                        const cfg = TYPE_CONFIG[idea.idea_type] ?? TYPE_CONFIG.value;
                                        const isSelected = selectedId === idea.id;

                                        return (
                                            <tr
                                                key={idea.id}
                                                onClick={() => setSelectedId(isSelected ? null : idea.id)}
                                                className={`border-b border-[#30363d]/50 cursor-pointer transition-colors ${isSelected ? "bg-[#d4af37]/5" : "hover:bg-white/[0.02]"}`}
                                            >
                                                <td className="px-5 py-3 text-gray-600 font-mono">{idx + 1}</td>
                                                <td className="px-3 py-3">
                                                    <div>
                                                        <span className="font-black text-white">{idea.ticker}</span>
                                                        <p className="text-[9px] text-gray-600 truncate max-w-[120px]">{idea.name}</p>
                                                    </div>
                                                </td>
                                                <td className="px-3 py-3">
                                                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold ${cfg.bg} ${cfg.color} border ${cfg.border}`}>
                                                        {cfg.icon} {cfg.label}
                                                    </span>
                                                </td>
                                                <td className="px-3 py-3">
                                                    <span className={`text-[9px] font-black uppercase ${idea.confidence === "high" ? "text-green-400" : idea.confidence === "medium" ? "text-yellow-400" : "text-gray-500"}`}>
                                                        {idea.confidence}
                                                    </span>
                                                </td>
                                                <td className="px-3 py-3 text-right font-mono font-bold text-white">
                                                    {(idea.signal_strength * 100).toFixed(0)}%
                                                </td>
                                                <td className="px-5 py-3 text-right">
                                                    <div className="flex items-center justify-end gap-2">
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); onAnalyze(idea.ticker); }}
                                                            className="text-[9px] font-bold text-[#d4af37] hover:text-[#e8c84a] transition-colors"
                                                        >
                                                            Analyze
                                                        </button>
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); onDismiss(idea.id); }}
                                                            className="text-gray-700 hover:text-red-400 transition-colors"
                                                        >
                                                            <X size={11} />
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>
            </div>

            {/* ── Right: Preview Panel ── */}
            {selectedIdea && (
                <div className="w-72 flex-shrink-0 hidden xl:block">
                    <div className="glass-card p-5 border-[#30363d] sticky top-4" style={{ animation: "fadeSlideIn 0.2s ease both" }}>
                        <div className="flex items-center justify-between mb-4">
                            <span className="text-lg font-black text-white">{selectedIdea.ticker}</span>
                            <button onClick={() => setSelectedId(null)} className="text-gray-600 hover:text-gray-400">
                                <X size={14} />
                            </button>
                        </div>

                        <div className="space-y-4">
                            {/* Name + Sector */}
                            <div>
                                <p className="text-xs text-gray-400">{selectedIdea.name}</p>
                                <p className="text-[9px] text-gray-600 mt-0.5">{selectedIdea.sector}</p>
                            </div>

                            {/* Strategy */}
                            <div>
                                <p className="text-[9px] uppercase text-gray-600 mb-1">Detected by</p>
                                {(() => {
                                    const cfg = TYPE_CONFIG[selectedIdea.idea_type] ?? TYPE_CONFIG.value;
                                    return (
                                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold ${cfg.bg} ${cfg.color} border ${cfg.border}`}>
                                            {cfg.icon} {cfg.label} Detector
                                        </span>
                                    );
                                })()}
                            </div>

                            {/* Strength */}
                            <div>
                                <p className="text-[9px] uppercase text-gray-600 mb-1">Signal Strength</p>
                                <p className="text-2xl font-black text-[#d4af37]">
                                    {(selectedIdea.signal_strength * 100).toFixed(0)}%
                                </p>
                            </div>

                            {/* Confidence */}
                            <div>
                                <p className="text-[9px] uppercase text-gray-600 mb-1">Confidence</p>
                                <span className={`text-xs font-black uppercase ${selectedIdea.confidence === "high" ? "text-green-400" : selectedIdea.confidence === "medium" ? "text-yellow-400" : "text-gray-500"}`}>
                                    {selectedIdea.confidence}
                                </span>
                            </div>

                            {/* Signals */}
                            {selectedIdea.signals && selectedIdea.signals.length > 0 && (
                                <div>
                                    <p className="text-[9px] uppercase text-gray-600 mb-2">Key Signals</p>
                                    <div className="space-y-1.5">
                                        {selectedIdea.signals.slice(0, 4).map((sig, i) => (
                                            <div key={i} className="flex items-center gap-2">
                                                <TrendingUp size={9} className={sig.strength === "strong" ? "text-green-400" : sig.strength === "moderate" ? "text-yellow-400" : "text-gray-500"} />
                                                <span className="text-[10px] text-gray-400 truncate flex-1">{sig.name}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* CTA */}
                            <button
                                onClick={() => onAnalyze(selectedIdea.ticker)}
                                className="w-full bg-gradient-to-r from-[#d4af37] to-[#e8c84a] text-black font-bold py-2.5 rounded-xl hover:brightness-110 transition-all flex items-center justify-center gap-2 text-sm"
                            >
                                <Zap size={14} /> Run Full Analysis
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
