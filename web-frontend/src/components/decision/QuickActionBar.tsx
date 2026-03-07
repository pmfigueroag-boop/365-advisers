"use client";

/**
 * QuickActionBar.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Compact horizontal action bar for the Terminal view — add to portfolio,
 * compare, export, refresh. Designed for institutional density.
 */

import {
    Briefcase,
    ArrowLeftRight,
    Download,
    RefreshCw,
    ExternalLink,
} from "lucide-react";

interface QuickActionBarProps {
    ticker?: string | null;
    onAddToPortfolio?: () => void;
    onCompare?: () => void;
    onExport?: () => void;
    onRefresh?: () => void;
    onDeepAnalysis?: () => void;
    isRefreshing?: boolean;
}

export default function QuickActionBar({
    ticker,
    onAddToPortfolio,
    onCompare,
    onExport,
    onRefresh,
    onDeepAnalysis,
    isRefreshing,
}: QuickActionBarProps) {
    if (!ticker) return null;

    const actions = [
        { icon: <Briefcase size={12} />, label: "Add to Portfolio", onClick: onAddToPortfolio, visible: !!onAddToPortfolio },
        { icon: <ArrowLeftRight size={12} />, label: "Compare", onClick: onCompare, visible: !!onCompare },
        { icon: <Download size={12} />, label: "Export Report", onClick: onExport, visible: !!onExport },
        { icon: <RefreshCw size={12} className={isRefreshing ? "animate-spin" : ""} />, label: "Refresh", onClick: onRefresh, visible: !!onRefresh },
        { icon: <ExternalLink size={12} />, label: "Deep Analysis", onClick: onDeepAnalysis, visible: !!onDeepAnalysis },
    ].filter((a) => a.visible);

    return (
        <div className="flex items-center gap-1.5 flex-wrap">
            {actions.map((action) => (
                <button
                    key={action.label}
                    onClick={action.onClick}
                    disabled={isRefreshing && action.label === "Refresh"}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[9px] font-bold uppercase tracking-wider text-gray-500 border border-[#30363d] hover:border-[#d4af37]/40 hover:text-[#d4af37] hover:bg-[#d4af37]/5 transition-all disabled:opacity-40"
                    title={action.label}
                >
                    {action.icon}
                    <span className="hidden sm:inline">{action.label}</span>
                </button>
            ))}
        </div>
    );
}
