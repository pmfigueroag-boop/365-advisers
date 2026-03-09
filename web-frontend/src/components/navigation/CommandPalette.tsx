"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
    Search,
    Monitor,
    Lightbulb,
    Microscope,
    Briefcase,
    Brain,
    Zap,
    Clock,
    Star,
    Map,
    FlaskConical,
    Store,
    Sparkles,
    Rocket,
} from "lucide-react";
import type { ViewId } from "./TopNav";

// ─── Types ────────────────────────────────────────────────────────────────────

interface CommandItem {
    id: string;
    label: string;
    sublabel?: string;
    icon: React.ReactNode;
    type: "view" | "ticker" | "action";
    action: () => void;
}

interface CommandPaletteProps {
    open: boolean;
    onClose: () => void;
    onNavigate: (view: ViewId) => void;
    onAnalyze: (ticker: string) => void;
    recentTickers: string[];
    watchlistTickers: string[];
}

// ─── Static Commands ──────────────────────────────────────────────────────────

function buildViewCommands(onNavigate: (v: ViewId) => void): CommandItem[] {
    return [
        { id: "v-terminal", label: "Terminal", sublabel: "Investment decisions", icon: <Monitor size={14} />, type: "view", action: () => onNavigate("terminal") },
        { id: "v-market", label: "Market Intelligence", sublabel: "Opportunity radar & regime", icon: <Map size={14} />, type: "view", action: () => onNavigate("market") },
        { id: "v-ideas", label: "Idea Explorer", sublabel: "Opportunity ranking", icon: <Lightbulb size={14} />, type: "view", action: () => onNavigate("ideas") },
        { id: "v-analysis", label: "Deep Analysis", sublabel: "Full evidence review", icon: <Microscope size={14} />, type: "view", action: () => onNavigate("analysis") },
        { id: "v-portfolio", label: "Portfolio Intelligence", sublabel: "Risk & allocation", icon: <Briefcase size={14} />, type: "view", action: () => onNavigate("portfolio") },
        { id: "v-system", label: "System Intelligence", sublabel: "Signal health monitor", icon: <Brain size={14} />, type: "view", action: () => onNavigate("system") },
        { id: "v-pilot", label: "Pilot Command Center", sublabel: "12-week paper trading validation", icon: <Rocket size={14} />, type: "view", action: () => onNavigate("pilot") },
        { id: "v-strategy-lab", label: "Strategy Lab", sublabel: "Bloomberg 4-panel workspace", icon: <FlaskConical size={14} />, type: "view", action: () => onNavigate("strategy-lab") },
        { id: "v-marketplace", label: "Marketplace", sublabel: "Pre-built strategies", icon: <Store size={14} />, type: "view", action: () => onNavigate("marketplace") },
        { id: "v-ai-assistant", label: "AI Assistant", sublabel: "Knowledge Graph chat", icon: <Sparkles size={14} />, type: "view", action: () => onNavigate("ai-assistant") },
    ];
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function CommandPalette({
    open,
    onClose,
    onNavigate,
    onAnalyze,
    recentTickers,
    watchlistTickers,
}: CommandPaletteProps) {
    const [query, setQuery] = useState("");
    const [selectedIdx, setSelectedIdx] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);

    // Reset on open
    useEffect(() => {
        if (open) {
            setQuery("");
            setSelectedIdx(0);
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [open]);

    // Build dynamic items
    const buildItems = useCallback((): CommandItem[] => {
        const items: CommandItem[] = [];
        const q = query.trim().toUpperCase();

        // If query looks like a ticker, offer analysis first
        if (q.length >= 1 && q.length <= 6 && /^[A-Z]+$/.test(q)) {
            items.push({
                id: `analyze-${q}`,
                label: `Analyze ${q}`,
                sublabel: "Run Investment Committee",
                icon: <Zap size={14} className="text-[#d4af37]" />,
                type: "ticker",
                action: () => { onAnalyze(q); onClose(); },
            });
        }

        // View commands
        const viewCmds = buildViewCommands((v) => { onNavigate(v); onClose(); });
        if (q) {
            items.push(
                ...viewCmds.filter((c) =>
                    c.label.toUpperCase().includes(q) || (c.sublabel?.toUpperCase().includes(q) ?? false)
                )
            );
        } else {
            items.push(...viewCmds);
        }

        // Recent tickers
        if (!q) {
            recentTickers.slice(0, 5).forEach((t) => {
                items.push({
                    id: `recent-${t}`,
                    label: t,
                    sublabel: "Recent",
                    icon: <Clock size={14} className="text-gray-500" />,
                    type: "ticker",
                    action: () => { onAnalyze(t); onClose(); },
                });
            });
        }

        // Watchlist tickers
        if (!q) {
            watchlistTickers.slice(0, 5).forEach((t) => {
                if (!recentTickers.includes(t)) {
                    items.push({
                        id: `watch-${t}`,
                        label: t,
                        sublabel: "Watchlist",
                        icon: <Star size={14} className="text-[#d4af37]" />,
                        type: "ticker",
                        action: () => { onAnalyze(t); onClose(); },
                    });
                }
            });
        }

        return items;
    }, [query, recentTickers, watchlistTickers, onAnalyze, onNavigate, onClose]);

    const items = buildItems();

    // Keyboard navigation
    useEffect(() => {
        if (!open) return;
        const handler = (e: KeyboardEvent) => {
            if (e.key === "Escape") { onClose(); return; }
            if (e.key === "ArrowDown") { e.preventDefault(); setSelectedIdx((i) => Math.min(i + 1, items.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setSelectedIdx((i) => Math.max(i - 1, 0)); }
            if (e.key === "Enter" && items[selectedIdx]) { items[selectedIdx].action(); }
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [open, items, selectedIdx, onClose]);

    // Clamp selected index
    useEffect(() => {
        setSelectedIdx((i) => Math.min(i, Math.max(items.length - 1, 0)));
    }, [items.length]);

    if (!open) return null;

    return (
        <div
            className="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh]"
            style={{ backgroundColor: "rgba(0,0,0,0.65)", backdropFilter: "blur(6px)" }}
            onClick={onClose}
        >
            <div
                className="w-full max-w-lg bg-[#0d1117] border border-[#30363d] rounded-2xl shadow-2xl overflow-hidden"
                style={{ animation: "fadeSlideIn 0.2s ease both" }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Search Input */}
                <div className="flex items-center gap-3 px-5 py-4 border-b border-[#30363d]">
                    <Search size={16} className="text-gray-500 flex-shrink-0" />
                    <input
                        ref={inputRef}
                        type="text"
                        placeholder="Search tickers, navigate views…"
                        className="flex-1 bg-transparent text-sm text-white placeholder:text-gray-600 focus:outline-none"
                        value={query}
                        onChange={(e) => { setQuery(e.target.value); setSelectedIdx(0); }}
                    />
                    <kbd className="text-[9px] font-mono text-gray-600 border border-[#30363d] rounded px-1.5 py-0.5">
                        ESC
                    </kbd>
                </div>

                {/* Results */}
                <div className="max-h-[360px] overflow-y-auto custom-scrollbar py-2">
                    {items.length === 0 ? (
                        <p className="text-center text-gray-600 text-sm py-8">No results</p>
                    ) : (
                        items.map((item, idx) => (
                            <button
                                key={item.id}
                                onClick={item.action}
                                onMouseEnter={() => setSelectedIdx(idx)}
                                className={`w-full flex items-center gap-3 px-5 py-2.5 text-left transition-colors ${idx === selectedIdx
                                    ? "bg-[#d4af37]/10 text-white"
                                    : "text-gray-400 hover:bg-white/[0.03]"
                                    }`}
                            >
                                <span className={`flex-shrink-0 ${idx === selectedIdx ? "text-[#d4af37]" : "text-gray-600"}`}>
                                    {item.icon}
                                </span>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold truncate">{item.label}</p>
                                    {item.sublabel && (
                                        <p className="text-[10px] text-gray-600 truncate">{item.sublabel}</p>
                                    )}
                                </div>
                                <span className="text-[8px] font-mono text-gray-700 uppercase flex-shrink-0">
                                    {item.type}
                                </span>
                            </button>
                        ))
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between px-5 py-2.5 border-t border-[#30363d] bg-[#0a0e15]">
                    <div className="flex gap-3 text-[9px] font-mono text-gray-700">
                        <span>↑↓ Navigate</span>
                        <span>↵ Select</span>
                        <span>ESC Close</span>
                    </div>
                    <span className="text-[8px] font-mono text-gray-700">Ctrl+K</span>
                </div>
            </div>
        </div>
    );
}
