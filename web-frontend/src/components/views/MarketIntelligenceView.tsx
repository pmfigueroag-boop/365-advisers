"use client";

/**
 * MarketIntelligenceView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Market Intelligence Map — bird's eye view of the investment landscape.
 *
 * Layout:
 * ┌──────────────────┬──────────────────────────────────────┐
 * │ Market Regime     │ Top Opportunities                   │
 * │ Sector Heatmap    │                                     │
 * │ Risk Signals      │ Signal Clusters                     │
 * └──────────────────┴──────────────────────────────────────┘
 */

import { useEffect } from "react";
import { Map, RefreshCw, Loader2 } from "lucide-react";
import MarketRegimePanel from "@/components/market/MarketRegimePanel";
import SectorHeatmap from "@/components/market/SectorHeatmap";
import TopOpportunitiesList from "@/components/market/TopOpportunitiesList";
import SignalClusterPanel from "@/components/market/SignalClusterPanel";
import MarketRiskSignals from "@/components/market/MarketRiskSignals";
import ErrorBoundary from "@/components/ErrorBoundary";
import InfoTooltip from "@/components/shared/InfoTooltip";
import { useMarketRadar } from "@/hooks/useMarketRadar";
import { useCrowding } from "@/hooks/useCrowding";
import { useMonitoringAlerts } from "@/hooks/useMonitoringAlerts";

interface MarketIntelligenceViewProps {
    onSelectTicker: (ticker: string) => void;
    /** Set to true after a Scan Universe + ranking compute completes */
    rankingReady?: boolean;
}

export default function MarketIntelligenceView({ onSelectTicker, rankingReady }: MarketIntelligenceViewProps) {
    const radar = useMarketRadar();
    const crowding = useCrowding();
    const monitoring = useMonitoringAlerts();

    // Only fetch ranking data after a Scan Universe has been run this session
    useEffect(() => {
        if (rankingReady) {
            radar.refreshAll();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [rankingReady]);

    // Fetch monitoring alerts on mount
    useEffect(() => {
        monitoring.fetchAlerts({ limit: 20 });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Fetch crowding for top tickers when ranking is available
    useEffect(() => {
        if (radar.topOpportunities.length > 0) {
            const tickers = radar.topOpportunities.slice(0, 10).map((t) => t.ticker);
            crowding.assessBatch(tickers);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [radar.topOpportunities]);

    const isLoading = radar.status === "loading";

    return (
        <div className="space-y-6" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <Map size={16} className="text-[#d4af37]" />
                        <InfoTooltip text="Bird's-eye view of the market: current regime, top opportunities, risk alerts, and signal clusters across your asset universe." position="bottom">
                            <h2 className="text-base font-black uppercase tracking-widest text-gray-300">
                                Market Intelligence
                            </h2>
                        </InfoTooltip>
                    </div>
                    <p className="text-xs text-gray-600">
                        Bird&apos;s-eye view of the investment landscape — opportunities, risks, and signal clusters.
                    </p>
                </div>
                <button
                    onClick={() => radar.refreshAll()}
                    disabled={isLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-wider text-gray-400 hover:text-[#d4af37] bg-[#161b22] border border-[#30363d] hover:border-[#d4af37]/30 transition-all disabled:opacity-50"
                >
                    {isLoading ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
                    Refresh
                </button>
            </div>

            <div className="separator-gold" />

            {/* Show panels only when we have ranking data */}
            {radar.globalRanking.length > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                    {/* Left Column — Context (1/3) */}
                    <div className="space-y-4">
                        <ErrorBoundary>
                            <MarketRegimePanel
                                universeSize={radar.universeSize}
                                computedAt={radar.computedAt}
                            />
                        </ErrorBoundary>
                        <ErrorBoundary>
                            <SectorHeatmap globalRanking={radar.globalRanking} />
                        </ErrorBoundary>
                        <ErrorBoundary>
                            <MarketRiskSignals
                                alerts={monitoring.alerts}
                                crowdingAssessments={crowding.assessments}
                            />
                        </ErrorBoundary>
                    </div>

                    {/* Right Column — Opportunities (2/3) */}
                    <div className="lg:col-span-2 space-y-4">
                        <ErrorBoundary>
                            <TopOpportunitiesList
                                items={radar.topOpportunities.length > 0 ? radar.topOpportunities : radar.globalRanking}
                                onSelect={onSelectTicker}
                            />
                        </ErrorBoundary>
                        <ErrorBoundary>
                            <SignalClusterPanel ranking={radar.globalRanking} />
                        </ErrorBoundary>
                    </div>
                </div>
            ) : (
                /* Clean neutral state — no scan has been run yet */
                <div className="flex flex-col items-center justify-center py-16">
                    <MarketRegimePanel regime="neutral" universeSize={0} computedAt={null} className="w-full max-w-sm mb-8" />
                    <Map size={40} className="text-gray-700 mb-4" />
                    <p className="text-sm font-bold text-gray-400 mb-1">No Market Data Available</p>
                    <p className="text-xs text-gray-600 text-center max-w-md">
                        Run a <span className="text-[#d4af37] font-bold">Scan Universe</span> from the Ideas tab to populate the Market Intelligence dashboard with opportunities, sector analysis, and signal clusters.
                    </p>
                </div>
            )}

            {/* Error */}
            {radar.status === "error" && (
                <div className="text-center py-8">
                    <p className="text-red-400 text-sm font-mono">{radar.error}</p>
                </div>
            )}
        </div>
    );
}
