"use client";

/**
 * WatchlistPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Collapsible right-side watchlist panel for the Terminal view.
 * Extracted from the original page.tsx WatchlistSidebar + sidebar tabs.
 */

import { useState } from "react";
import {
    BookMarked,
    History,
    Lightbulb,
    ChevronLeft,
    ChevronRight,
    X,
    LayoutGrid,
    List,
} from "lucide-react";
import type { WatchlistItem } from "@/hooks/useWatchlist";
import type { HistoryEntry } from "@/hooks/useAnalysisHistory";
import HistoryPanel from "@/components/HistoryPanel";
import IdeasPanel from "@/components/IdeasPanel";
import { SignalBadge } from "@/components/AnalysisWidgets";

// ─── Types ────────────────────────────────────────────────────────────────────

interface WatchlistPanelProps {
    // Watchlist
    items: WatchlistItem[];
    onSelect: (ticker: string) => void;
    onRemove: (ticker: string) => void;
    activeTicker?: string;
    // History
    historyEntries: HistoryEntry[];
    onHistorySelect: (ticker: string) => void;
    onHistoryRemove: (id: string) => void;
    onHistoryClear: () => void;
    // Ideas
    ideas: any[];
    ideasScanStatus: "idle" | "scanning" | "done" | "error";
    ideasError: string | null;
    onIdeasScan: () => void;
    onIdeasAnalyze: (ticker: string) => void;
    onIdeasDismiss: (id: number) => void;
    // Panel state
    collapsed: boolean;
    onToggle: () => void;
}

type PanelTab = "watchlist" | "history" | "ideas";

// ─── Component ────────────────────────────────────────────────────────────────

export default function WatchlistPanel({
    items,
    onSelect,
    onRemove,
    activeTicker,
    historyEntries,
    onHistorySelect,
    onHistoryRemove,
    onHistoryClear,
    ideas,
    ideasScanStatus,
    ideasError,
    onIdeasScan,
    onIdeasAnalyze,
    onIdeasDismiss,
    collapsed,
    onToggle,
}: WatchlistPanelProps) {
    const [tab, setTab] = useState<PanelTab>("watchlist");
    const [viewMode, setViewMode] = useState<"list" | "heatmap">("list");

    if (collapsed) {
        return (
            <aside className="relative flex-shrink-0 w-10 hidden md:block">
                <button
                    onClick={onToggle}
                    className="flex flex-col items-center justify-center w-full h-full gap-4 text-gray-600 hover:text-[#d4af37] transition-colors glass-card border-[#30363d]"
                    title="Expand panel"
                >
                    <ChevronLeft size={14} />
                </button>
            </aside>
        );
    }

    return (
        <aside className="relative flex-shrink-0 w-60 hidden md:flex flex-col">
            <div className="glass-card border-[#30363d] flex flex-col h-full overflow-hidden">
                {/* Tab bar */}
                <div className="flex border-b border-[#30363d]">
                    {([
                        { id: "watchlist" as PanelTab, icon: <BookMarked size={11} />, label: "Watch", count: items.length },
                        { id: "history" as PanelTab, icon: <History size={11} />, label: "Hist", count: historyEntries.length },
                        { id: "ideas" as PanelTab, icon: <Lightbulb size={11} />, label: "Ideas", count: ideas.length },
                    ]).map((t) => (
                        <button
                            key={t.id}
                            onClick={() => setTab(t.id)}
                            className={`flex-1 flex items-center justify-center gap-1 py-3 text-[10px] font-black uppercase tracking-wider transition-all border-b-2 ${tab === t.id
                                ? "border-[#d4af37] text-[#d4af37] shadow-[0_2px_8px_-2px_rgba(212,175,55,0.5)]"
                                : "border-transparent text-gray-600 hover:text-gray-400"
                                }`}
                        >
                            {t.icon}
                            {t.label}
                            {t.count > 0 && (
                                <span className={`rounded-full px-1.5 py-0.5 text-[7px] font-mono ml-0.5 ${t.id === "ideas"
                                    ? "bg-[#d4af37]/20 text-[#d4af37]"
                                    : "bg-[#30363d] text-gray-400"
                                    }`}>
                                    {t.count}
                                </span>
                            )}
                        </button>
                    ))}
                    <button
                        onClick={onToggle}
                        className="px-2 text-gray-700 hover:text-gray-400 transition-colors"
                        title="Collapse panel"
                    >
                        <ChevronRight size={12} />
                    </button>
                </div>

                {/* Content */}
                <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
                    {tab === "watchlist" && (
                        <WatchlistList
                            items={items}
                            onSelect={onSelect}
                            onRemove={onRemove}
                            activeTicker={activeTicker}
                            viewMode={viewMode}
                            onViewModeChange={setViewMode}
                        />
                    )}
                    {tab === "history" && (
                        <HistoryPanel
                            entries={historyEntries}
                            onSelect={onHistorySelect}
                            onRemove={onHistoryRemove}
                            onClear={onHistoryClear}
                        />
                    )}
                    {tab === "ideas" && (
                        <IdeasPanel
                            ideas={ideas}
                            scanStatus={ideasScanStatus}
                            error={ideasError}
                            onScan={onIdeasScan}
                            onAnalyze={onIdeasAnalyze}
                            onDismiss={onIdeasDismiss}
                        />
                    )}
                </div>
            </div>
        </aside>
    );
}

// ─── Watchlist List Sub-component ─────────────────────────────────────────────

function WatchlistList({
    items,
    onSelect,
    onRemove,
    activeTicker,
    viewMode,
    onViewModeChange,
}: {
    items: WatchlistItem[];
    onSelect: (ticker: string) => void;
    onRemove: (ticker: string) => void;
    activeTicker?: string;
    viewMode: "list" | "heatmap";
    onViewModeChange: (mode: "list" | "heatmap") => void;
}) {
    return (
        <div className="flex flex-col h-full">
            {/* View mode toggle */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-[#30363d]/50">
                <span className="text-[9px] text-gray-600 font-mono uppercase">{items.length} tracked</span>
                <div className="flex bg-[#161b22] border border-[#30363d] rounded p-0.5">
                    <button
                        onClick={() => onViewModeChange("list")}
                        className={`p-1 rounded ${viewMode === "list" ? "bg-[#30363d] text-white" : "text-gray-500 hover:text-gray-300"}`}
                    >
                        <List size={10} />
                    </button>
                    <button
                        onClick={() => onViewModeChange("heatmap")}
                        className={`p-1 rounded ${viewMode === "heatmap" ? "bg-[#30363d] text-white" : "text-gray-500 hover:text-gray-300"}`}
                    >
                        <LayoutGrid size={10} />
                    </button>
                </div>
            </div>

            {/* Items */}
            <div className={`flex-1 overflow-y-auto custom-scrollbar p-2 ${viewMode === "heatmap" ? "grid grid-cols-2 gap-2 content-start" : "flex flex-col gap-0.5"}`}>
                {items.length === 0 ? (
                    <div className="col-span-full flex flex-col items-center justify-center h-full px-4 py-8 text-center gap-2">
                        <BookMarked size={24} className="text-[#30363d]" />
                        <p className="text-[10px] text-gray-600 leading-relaxed">
                            Add a ticker with ★ to track it here
                        </p>
                    </div>
                ) : (
                    items.map((item) => {
                        const isActive = item.ticker === activeTicker;
                        const scoreDelta = (item.lastScore !== undefined && item.prevScore !== undefined) ? item.lastScore - item.prevScore : 0;
                        const hasDelta = item.lastScore !== undefined && item.prevScore !== undefined && item.lastScore !== item.prevScore;

                        if (viewMode === "heatmap") {
                            const heatBg = !hasDelta ? "bg-[#161b22] border-[#30363d]"
                                : scoreDelta > 0 ? "bg-green-500/10 border-green-500/30"
                                    : "bg-red-500/10 border-red-500/30";
                            return (
                                <div
                                    key={item.ticker}
                                    className={`group relative flex flex-col items-center justify-center p-3 rounded-lg cursor-pointer transition-all border ${heatBg} hover:opacity-80`}
                                    onClick={() => onSelect(item.ticker)}
                                >
                                    <span className={`text-[12px] font-black ${isActive ? "text-[#d4af37]" : "text-gray-200"}`}>
                                        {item.ticker}
                                    </span>
                                    {hasDelta && (
                                        <span className={`text-[9px] font-mono font-black mt-1 ${scoreDelta > 0 ? "text-green-400" : "text-red-400"}`}>
                                            {scoreDelta > 0 ? "+" : ""}{scoreDelta.toFixed(1)}
                                        </span>
                                    )}
                                </div>
                            );
                        }

                        return (
                            <div
                                key={item.ticker}
                                className={`group relative flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all ${isActive
                                    ? "bg-[#d4af37]/10 border border-[#d4af37]/30"
                                    : "hover:bg-[#161b22] border border-transparent"
                                    }`}
                                onClick={() => onSelect(item.ticker)}
                            >
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center justify-between gap-1">
                                        <span className={`text-[12px] font-black ${isActive ? "text-[#d4af37]" : "text-gray-200"}`}>
                                            {item.ticker}
                                        </span>
                                        {item.lastSignal && <SignalBadge signal={item.lastSignal} />}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <p className="text-[9px] text-gray-500 truncate">{item.name}</p>
                                        {hasDelta && (
                                            <span className={`text-[8px] font-mono font-black flex-shrink-0 ${scoreDelta > 0 ? "text-green-400" : "text-red-400"}`}>
                                                {scoreDelta > 0 ? "+" : ""}{scoreDelta.toFixed(1)}
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <button
                                    onClick={(e) => { e.stopPropagation(); onRemove(item.ticker); }}
                                    className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-600 hover:text-red-400 p-0.5 flex-shrink-0"
                                    title="Remove"
                                >
                                    <X size={10} />
                                </button>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}
