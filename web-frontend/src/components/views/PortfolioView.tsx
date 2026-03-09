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
        const avgVol = volCount > 0 ? totalVol / volCount : undefined;

        // Approximate scenario projections based on average opportunity score
        const baseReturn = avgOpportunity * 1.2 - 2; // simple heuristic
        const bullReturn = baseReturn + (avgOpportunity > 7 ? 8 : 5);
        const bearReturn = baseReturn - (avgVol ? avgVol * 1.5 : 6);

        // Approximate VaR and max drawdown
        const var95 = avgVol ? avgVol * 1.65 : undefined;
        const maxDrawdown = avgVol ? avgVol * 2.5 : undefined;
        const sharpeEstimate =
            avgVol && avgVol > 0 ? baseReturn / avgVol : undefined;

        return {
            allocEntries,
            var95,
            maxDrawdown,
            sharpeEstimate,
            portfolioVolatility: avgVol,
            bullReturn,
            baseReturn,
            bearReturn,
        };
    }, [historyEntries]);

    return (
        <div className="space-y-6" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Intelligence Panels — shown when we have history data */}
            <div>
                {portfolioMetrics && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
                        <ErrorBoundary>
                            <AllocationChart entries={portfolioMetrics.allocEntries} />
                        </ErrorBoundary>
                        <ErrorBoundary>
                            <RiskBudgetPanel
                                var95={portfolioMetrics.var95}
                                maxDrawdown={portfolioMetrics.maxDrawdown}
                                sharpeEstimate={portfolioMetrics.sharpeEstimate}
                                portfolioVolatility={portfolioMetrics.portfolioVolatility}
                            />
                        </ErrorBoundary>
                        <ErrorBoundary>
                            <ScenarioAnalysisPanel
                                bullReturn={portfolioMetrics.bullReturn}
                                baseReturn={portfolioMetrics.baseReturn}
                                bearReturn={portfolioMetrics.bearReturn}
                            />
                        </ErrorBoundary>
                    </div>
                )}
            </div>

            {/* Existing Portfolio Dashboard */}
            <ErrorBoundary>
                <PortfolioDashboard historyEntries={historyEntries} />
            </ErrorBoundary>
        </div>
    );
}
