"use client";

/**
 * PortfolioView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Portfolio Intelligence — enhanced wrapper around the existing
 * PortfolioDashboard with better structure and future extensibility.
 */

import PortfolioDashboard from "@/components/PortfolioDashboard";
import type { HistoryEntry } from "@/hooks/useAnalysisHistory";

// ─── Types ────────────────────────────────────────────────────────────────────

interface PortfolioViewProps {
    historyEntries: HistoryEntry[];
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function PortfolioView({ historyEntries }: PortfolioViewProps) {
    return (
        <div style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            <PortfolioDashboard historyEntries={historyEntries} />
        </div>
    );
}
