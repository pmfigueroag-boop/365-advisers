"use client";

/**
 * PortfolioView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Portfolio Intelligence — wraps PortfolioDashboard with allocation chart,
 * risk budget panel, and scenario analysis panel derived from analysis history.
 */

import { useMemo } from "react";
import PortfolioDashboard from "@/components/PortfolioDashboard";
import AllocationChart from "@/components/portfolio/AllocationChart";
import RiskBudgetPanel from "@/components/portfolio/RiskBudgetPanel";
import ScenarioAnalysisPanel from "@/components/portfolio/ScenarioAnalysisPanel";
import ErrorBoundary from "@/components/ErrorBoundary";
import type { HistoryEntry } from "@/hooks/useAnalysisHistory";

// ─── Types ────────────────────────────────────────────────────────────────────

interface PortfolioViewProps {
    historyEntries: HistoryEntry[];
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function PortfolioView({ historyEntries }: PortfolioViewProps) {
    // Derive portfolio metrics from analysis history
    const portfolioMetrics = useMemo(() => {
        const eligible = historyEntries.filter(
            (e) =>
                Number(e.fundamental_score) > 0 &&
                e.opportunity_score !== undefined &&
                e.position_sizing !== undefined
        );

        if (eligible.length === 0) return null;

        // Build allocation entries from position sizing data
        const allocEntries: { ticker: string; allocation: number; type: "core" | "satellite" }[] = [];
        let totalVol = 0;
        let volCount = 0;

        for (const entry of eligible) {
            const ps =
                typeof entry.position_sizing === "string"
                    ? JSON.parse(entry.position_sizing)
                    : entry.position_sizing;

            if (ps) {
                const allocation = ps.suggested_allocation ?? ps.target_weight ?? 0;
                const type: "core" | "satellite" =
                    (ps.role ?? ps.position_type ?? "").toLowerCase() === "satellite"
                        ? "satellite"
                        : (entry.opportunity_score ?? 0) >= 7
                            ? "core"
                            : "satellite";

                // Deduplicate: keep only the first (newest) entry per ticker
                if (!allocEntries.some((a) => a.ticker === entry.ticker)) {
                    allocEntries.push({ ticker: entry.ticker, allocation, type });
                }
            }

            if (entry.volatility_atr != null) {
                totalVol += entry.volatility_atr;
                volCount += 1;
            }
        }

        // Derive risk metrics from history
        const avgOpportunity =
            eligible.reduce((s, e) => s + (e.opportunity_score ?? 0), 0) / eligible.length;
        // volatility_atr is a fraction (0.024 = 2.4%); convert to percentage
        const avgVolFraction = volCount > 0 ? totalVol / volCount : undefined;
        const avgVolPct = avgVolFraction != null ? avgVolFraction * 100 : undefined;

        // Require at least 2 data points for risk metrics
        if (volCount < 2 || avgVolPct == null || avgVolPct < 0.01) {
            return {
                allocEntries,
                var95: undefined,
                maxDrawdown: undefined,
                sharpeEstimate: undefined,
                portfolioVolatility: undefined,
                bullReturn: 0,
                baseReturn: 0,
                bearReturn: 0,
            };
        }

        // Approximate scenario projections based on average opportunity score
        const baseReturn = avgOpportunity * 1.2 - 2; // simple heuristic
        const bullReturn = baseReturn + (avgOpportunity > 7 ? 8 : 5);
        const bearReturn = baseReturn - (avgVolPct * 1.5);

        // Approximate VaR and max drawdown (using % values)
        const var95 = avgVolPct * 1.65;
        const maxDrawdown = avgVolPct * 2.5;
        // Sharpe: clamp to [-5, 5] to prevent unrealistic display values
        const rawSharpe = baseReturn / avgVolPct;
        const sharpeEstimate = Math.max(-5, Math.min(5, rawSharpe));

        return {
            allocEntries,
            var95,
            maxDrawdown,
            sharpeEstimate,
            portfolioVolatility: avgVolPct,
            bullReturn,
            baseReturn,
            bearReturn,
        };
    }, [historyEntries]);

    return (
        <div className="space-y-6" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Intelligence Panels — always show grid, components handle their own empty states */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <ErrorBoundary>
                    <AllocationChart entries={portfolioMetrics?.allocEntries ?? []} />
                </ErrorBoundary>
                <ErrorBoundary>
                    <RiskBudgetPanel
                        var95={portfolioMetrics?.var95}
                        maxDrawdown={portfolioMetrics?.maxDrawdown}
                        sharpeEstimate={portfolioMetrics?.sharpeEstimate}
                        portfolioVolatility={portfolioMetrics?.portfolioVolatility}
                    />
                </ErrorBoundary>
                <ErrorBoundary>
                    <ScenarioAnalysisPanel
                        bullReturn={portfolioMetrics?.bullReturn ?? 0}
                        baseReturn={portfolioMetrics?.baseReturn ?? 0}
                        bearReturn={portfolioMetrics?.bearReturn ?? 0}
                    />
                </ErrorBoundary>
            </div>

            {/* Existing Portfolio Dashboard */}
            <ErrorBoundary>
                <PortfolioDashboard historyEntries={historyEntries} />
            </ErrorBoundary>
        </div>
    );
}
