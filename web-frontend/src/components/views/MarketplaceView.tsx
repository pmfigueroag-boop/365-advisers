"use client";

/**
 * MarketplaceView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Strategy Marketplace — Discover and import strategies.
 * Shows strategy leaderboard, strategy cards, and filtering.
 */

import { useState } from "react";
import {
    Trophy,
    Star,
    TrendingUp,
    Download,
    Search,
    Filter,
    ArrowUpDown,
    BarChart3,
    Clock,
    Zap,
} from "lucide-react";

// ─── Sample strategies (predefined templates) ─────────────────────────────

interface MarketplaceStrategy {
    id: string;
    name: string;
    category: string;
    description: string;
    sharpe: number;
    annReturn: number;
    maxDrawdown: number;
    winRate: number;
    horizon: string;
    tags: string[];
}

const SAMPLE_STRATEGIES: MarketplaceStrategy[] = [
    {
        id: "mom-quality-v2",
        name: "Momentum Quality v2",
        category: "momentum",
        description: "Multi-factor strategy combining momentum signals with quality filters and regime-aware sizing.",
        sharpe: 2.1,
        annReturn: 24.3,
        maxDrawdown: -12.3,
        winRate: 82,
        horizon: "Medium",
        tags: ["momentum", "quality", "regime-aware"],
    },
    {
        id: "value-contrarian-v3",
        name: "Value Contrarian v3",
        category: "value",
        description: "Deep value approach with mean-reversion signals and fundamental safety gates.",
        sharpe: 1.8,
        annReturn: 18.7,
        maxDrawdown: -15.1,
        winRate: 68,
        horizon: "Long",
        tags: ["value", "contrarian", "mean-reversion"],
    },
    {
        id: "ai-infrastructure",
        name: "AI Infrastructure Thematic",
        category: "thematic",
        description: "Concentrated thematic exposure to AI compute, networking, and datacenter infrastructure.",
        sharpe: 1.7,
        annReturn: 31.2,
        maxDrawdown: -18.5,
        winRate: 75,
        horizon: "Long",
        tags: ["thematic", "AI", "infrastructure"],
    },
    {
        id: "low-vol-yield",
        name: "Low Volatility Yield",
        category: "low_vol",
        description: "Defensive strategy focused on low-beta equities with consistent dividend yields.",
        sharpe: 1.5,
        annReturn: 12.4,
        maxDrawdown: -8.2,
        winRate: 71,
        horizon: "Long",
        tags: ["low-vol", "dividend", "defensive"],
    },
    {
        id: "event-catalyst",
        name: "Event Catalyst Hunter",
        category: "event_driven",
        description: "Event-driven signals around earnings, M&A, and corporate restructurings.",
        sharpe: 1.4,
        annReturn: 21.5,
        maxDrawdown: -14.8,
        winRate: 64,
        horizon: "Short",
        tags: ["event-driven", "catalyst", "earnings"],
    },
    {
        id: "sector-rotation",
        name: "Sector Rotation Alpha",
        category: "multi_factor",
        description: "Dynamic sector allocation based on macro regime signals and momentum breadth.",
        sharpe: 1.6,
        annReturn: 16.8,
        maxDrawdown: -11.4,
        winRate: 69,
        horizon: "Medium",
        tags: ["multi-factor", "rotation", "macro"],
    },
];

// ─── Medal icons ──────────────────────────────────────────────────────────

const MEDALS = ["🥇", "🥈", "🥉"];

export default function MarketplaceView() {
    const [search, setSearch] = useState("");
    const [selected, setSelected] = useState<string | null>(null);
    const [sortBy, setSortBy] = useState<"sharpe" | "return" | "winRate">("sharpe");

    const filtered = SAMPLE_STRATEGIES
        .filter((s) =>
            s.name.toLowerCase().includes(search.toLowerCase()) ||
            s.category.includes(search.toLowerCase()) ||
            s.tags.some((t) => t.includes(search.toLowerCase()))
        )
        .sort((a, b) => {
            if (sortBy === "sharpe") return b.sharpe - a.sharpe;
            if (sortBy === "return") return b.annReturn - a.annReturn;
            return b.winRate - a.winRate;
        });

    const selectedStrategy = filtered.find((s) => s.id === selected);

    return (
        <div className="space-y-5" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-base font-black uppercase tracking-widest text-gray-300">
                        Strategy Marketplace
                    </h2>
                    <p className="text-xs text-gray-600 mt-0.5">
                        Discover and import institutional strategies
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600" size={13} />
                        <input
                            type="text"
                            placeholder="Search strategies..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="bg-[#161b22] border border-[#30363d] pl-9 pr-3 py-1.5 rounded-lg text-xs focus:outline-none focus:border-[#d4af37]/40 transition-all w-48"
                        />
                    </div>
                    <div className="flex gap-1 glass-card px-1 py-0.5 border-[#30363d] rounded-lg">
                        {(["sharpe", "return", "winRate"] as const).map((key) => (
                            <button
                                key={key}
                                onClick={() => setSortBy(key)}
                                className={`text-[9px] font-bold uppercase px-2 py-1 rounded-md transition-all ${sortBy === key
                                        ? "bg-[#d4af37]/15 text-[#d4af37]"
                                        : "text-gray-600 hover:text-gray-400"
                                    }`}
                            >
                                {key === "sharpe" ? "Sharpe" : key === "return" ? "Return" : "Win%"}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Leaderboard */}
            <div className="glass-card p-4 border-[#30363d]">
                <div className="flex items-center gap-2 mb-3">
                    <Trophy size={12} className="text-[#d4af37]" />
                    <span className="text-[9px] font-black uppercase tracking-widest text-gray-500">
                        Strategy Leaderboard
                    </span>
                </div>
                <div className="space-y-2">
                    {filtered.slice(0, 3).map((s, i) => (
                        <button
                            key={s.id}
                            onClick={() => setSelected(s.id)}
                            className={`w-full flex items-center gap-4 p-3 rounded-lg text-left transition-all ${selected === s.id
                                    ? "bg-[#d4af37]/10 border border-[#d4af37]/30"
                                    : "bg-[#161b22] border border-[#30363d] hover:border-[#d4af37]/20"
                                }`}
                        >
                            <span className="text-xl">{MEDALS[i]}</span>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-bold text-gray-200 truncate">{s.name}</p>
                                <p className="text-[10px] text-gray-600 capitalize">{s.category}</p>
                            </div>
                            <div className="flex gap-4 text-right">
                                <div>
                                    <p className="text-[9px] text-gray-600 font-bold uppercase">Sharpe</p>
                                    <p className="text-sm font-bold text-emerald-400" style={{ fontFamily: "var(--font-data)" }}>
                                        {s.sharpe.toFixed(1)}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[9px] text-gray-600 font-bold uppercase">Return</p>
                                    <p className="text-sm font-bold text-[#d4af37]" style={{ fontFamily: "var(--font-data)" }}>
                                        {s.annReturn.toFixed(1)}%
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[9px] text-gray-600 font-bold uppercase">Win%</p>
                                    <p className="text-sm font-bold text-blue-400" style={{ fontFamily: "var(--font-data)" }}>
                                        {s.winRate}%
                                    </p>
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            {/* Strategy Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filtered.map((s) => (
                    <button
                        key={s.id}
                        onClick={() => setSelected(s.id)}
                        className={`glass-card p-4 border-[#30363d] text-left transition-all group ${selected === s.id ? "border-[#d4af37]/40 bg-[#d4af37]/5" : "hover:border-[#d4af37]/20"
                            }`}
                    >
                        <div className="flex items-start justify-between mb-2">
                            <div>
                                <p className="text-sm font-bold text-gray-200">{s.name}</p>
                                <p className="text-[9px] text-gray-600 capitalize">{s.category} · {s.horizon}</p>
                            </div>
                            <div className="flex items-center gap-1 text-[#d4af37]">
                                <Star size={10} fill="currentColor" />
                                <span className="text-xs font-bold" style={{ fontFamily: "var(--font-data)" }}>
                                    {s.sharpe.toFixed(1)}
                                </span>
                            </div>
                        </div>
                        <p className="text-[10px] text-gray-500 leading-relaxed mb-3 line-clamp-2">
                            {s.description}
                        </p>
                        <div className="flex gap-3 text-[9px] font-mono text-gray-600">
                            <span className="text-emerald-400">{s.annReturn.toFixed(1)}% ann.</span>
                            <span className="text-red-400">{s.maxDrawdown.toFixed(1)}% dd</span>
                            <span className="text-blue-400">{s.winRate}% win</span>
                        </div>
                        <div className="flex gap-1 mt-2 flex-wrap">
                            {s.tags.map((tag) => (
                                <span
                                    key={tag}
                                    className="text-[8px] font-bold uppercase tracking-wider text-gray-600 bg-[#161b22] px-1.5 py-0.5 rounded"
                                >
                                    {tag}
                                </span>
                            ))}
                        </div>
                    </button>
                ))}
            </div>
        </div>
    );
}
