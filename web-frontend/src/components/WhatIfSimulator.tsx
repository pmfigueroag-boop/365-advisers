"use client";

import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { CopyPlus, Activity, TrendingUp, TrendingDown, RefreshCw, X } from "lucide-react";
import type { PortfolioRecommendationResult } from "../hooks/usePortfolioBuilder";
import { usePortfolioBuilder } from "../hooks/usePortfolioBuilder";
import { HistoryEntry } from "../hooks/useAnalysisHistory";

interface WhatIfSimulatorProps {
    baseResult: PortfolioRecommendationResult;
    basePositions: any[]; // The raw positions used to generate `baseResult`
    availableHistory: HistoryEntry[];
}

export default function WhatIfSimulator({ baseResult, basePositions, availableHistory }: WhatIfSimulatorProps) {
    const { buildPortfolio, result: simResult, isLoading, error, reset } = usePortfolioBuilder();
    const [injectedTickers, setInjectedTickers] = useState<string[]>([]);

    // Refs to hold latest values without triggering re-renders (fixes #12)
    const basePositionsRef = useRef(basePositions);
    basePositionsRef.current = basePositions;
    const historyRef = useRef(availableHistory);
    historyRef.current = availableHistory;
    const buildRef = useRef(buildPortfolio);
    buildRef.current = buildPortfolio;
    const resetRef = useRef(reset);
    resetRef.current = reset;

    // We only want candidates that have valid fundamental & position size data AND are not already in basePositions
    const baseTickerMap = useMemo(() => {
        return new Set(basePositions.map(p => p.ticker));
    }, [basePositions]);

    const candidatePositions = useMemo(() => {
        const unique = new Map<string, any>();
        for (const entry of availableHistory) {
            // Check viability
            if (Number(entry.fundamental_score) > 0 && entry.position_sizing) {
                if (!baseTickerMap.has(entry.ticker) && !injectedTickers.includes(entry.ticker)) {
                    if (!unique.has(entry.ticker)) {
                        unique.set(entry.ticker, {
                            ticker: entry.ticker,
                            sector: entry.sector || "Unknown",
                            opportunity_score: entry.opportunity_score as number,
                            dimensions: typeof entry.dimensions === "string" ? JSON.parse(entry.dimensions) : (entry.dimensions || {}),
                            position_sizing: typeof entry.position_sizing === "string" ? JSON.parse(entry.position_sizing) : entry.position_sizing,
                            volatility_atr: entry.volatility_atr,
                        });
                    }
                }
            }
        }
        return Array.from(unique.values());
    }, [availableHistory, baseTickerMap, injectedTickers]);

    // When we inject/remove a ticker, immediately rebuild — deps only on injectedTickers (stable)
    useEffect(() => {
        if (injectedTickers.length > 0) {
            const toInjectData = injectedTickers.map(t => {
                const entry = historyRef.current.find(e => e.ticker === t);
                return {
                    ticker: entry?.ticker,
                    sector: entry?.sector || "Unknown",
                    opportunity_score: entry?.opportunity_score as number,
                    dimensions: typeof entry?.dimensions === "string" ? JSON.parse(entry.dimensions) : (entry?.dimensions || {}),
                    position_sizing: typeof entry?.position_sizing === "string" ? JSON.parse(entry.position_sizing) : entry?.position_sizing,
                    volatility_atr: entry?.volatility_atr,
                };
            }).filter(d => Boolean(d.ticker));

            buildRef.current([...basePositionsRef.current, ...toInjectData]);
        } else {
            resetRef.current();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [injectedTickers]);

    const handleInject = (ticker: string) => {
        setInjectedTickers(prev => [...prev, ticker]);
    };

    const handleRemove = (ticker: string) => {
        setInjectedTickers(prev => prev.filter(t => t !== ticker));
    };

    // Calculate Deltas
    const deltas = useMemo(() => {
        if (!simResult) return [];
        const baseMap = new Map();
        baseResult.core_positions.forEach(p => baseMap.set(p.ticker, p.target_weight));
        baseResult.satellite_positions.forEach(p => baseMap.set(p.ticker, p.target_weight));

        const comparison = [];

        for (const p of [...simResult.core_positions, ...simResult.satellite_positions]) {
            const before = baseMap.get(p.ticker) || 0;
            const after = p.target_weight;
            const diff = after - before;
            comparison.push({
                ticker: p.ticker,
                role: p.role,
                before,
                after,
                diff
            });
        }

        // Also add removed items if a re-bucket discarded them (rare but possible)
        const simMap = new Map();
        simResult.core_positions.forEach(p => simMap.set(p.ticker, p.target_weight));
        simResult.satellite_positions.forEach(p => simMap.set(p.ticker, p.target_weight));

        for (const p of [...baseResult.core_positions, ...baseResult.satellite_positions]) {
            if (!simMap.has(p.ticker)) {
                comparison.push({
                    ticker: p.ticker,
                    role: p.role,
                    before: p.target_weight,
                    after: 0,
                    diff: -p.target_weight
                });
            }
        }

        // Return sorted by diff (new items first, then largest losers)
        return comparison.sort((a, b) => b.diff - a.diff);
    }, [baseResult, simResult]);

    return (
        <div className="mt-8 pt-8 border-t border-[#30363d] animate-[fadeSlideIn_0.4s_ease_both]">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <CopyPlus size={16} className="text-[#a855f7]" />
                    <h3 className="text-[12px] font-black uppercase tracking-widest text-[#a855f7]">What-If Sandbox Simulator</h3>
                </div>
                {isLoading && <RefreshCw size={14} className="text-[#a855f7] animate-spin" />}
            </div>

            <div className="glass-card border-dashed border-[#a855f7]/40 bg-[#a855f7]/5 p-5 mb-4">
                <p className="text-xs text-gray-400 mb-3">
                    Inject mock assets to see how Volatility Parity and Risk Limits re-weight your current portfolio limits in real-time.
                </p>

                {/* Injector Bar */}
                <div className="flex flex-wrap items-center gap-2 mb-4">
                    <span className="text-[10px] font-bold text-[#a855f7] uppercase tracking-wider">Candidate Bucket:</span>
                    {candidatePositions.length === 0 && (
                        <span className="text-[10px] text-gray-500 italic">No spare assets in local history.</span>
                    )}
                    {candidatePositions.map(cand => (
                        <button
                            key={cand.ticker}
                            onClick={() => handleInject(cand.ticker)}
                            className="bg-[#161b22] hover:bg-[#a855f7]/20 border border-[#30363d] hover:border-[#a855f7]/50 text-gray-400 hover:text-white text-[10px] font-mono px-3 py-1 rounded transition-colors"
                        >
                            + Add {cand.ticker}
                        </button>
                    ))}
                </div>

                {/* Injected Tokens */}
                {injectedTickers.length > 0 && (
                    <div className="pt-3 border-t border-[#a855f7]/20">
                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-2">Injected:</span>
                        <div className="flex gap-2">
                            {injectedTickers.map(t => (
                                <div key={t} className="flex items-center gap-1 bg-[#a855f7]/20 border border-[#a855f7] text-[#e9d5ff] text-[11px] font-black px-2 py-0.5 rounded">
                                    {t}
                                    <button onClick={() => handleRemove(t)} className="opacity-60 hover:opacity-100 ml-1">
                                        <X size={10} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* Delta Comparison Table */}
            {simResult && deltas.length > 0 && (
                <div className="glass-card overflow-hidden">
                    <div className="bg-[#161b22] px-4 py-3 flex items-center justify-between border-b border-[#30363d]">
                        <div className="flex items-center gap-2">
                            <Activity size={14} className="text-[#a855f7]" />
                            <span className="text-[10px] font-black uppercase tracking-widest text-white">Delta Shift Analysis</span>
                        </div>
                        <span className="text-[10px] font-mono text-[#a855f7]">Vol Parity Auto-Rebalance</span>
                    </div>
                    <div className="divide-y divide-[#30363d]/50">
                        {deltas.map(d => (
                            <div key={d.ticker} className={`px-4 py-2.5 flex items-center justify-between transition-colors ${d.diff > 0 ? "bg-green-500/5" : d.diff < 0 ? "bg-red-500/5" : ""}`}>
                                <div className="flex items-center gap-3 w-1/3">
                                    <span className="font-bold text-sm text-white w-12">{d.ticker}</span>
                                    <span className={`text-[8px] uppercase tracking-wider px-1.5 py-0.5 rounded ${d.role === "CORE" ? "bg-[#d4af37]/10 text-[#d4af37]" : "bg-[#60a5fa]/10 text-[#60a5fa]"}`}>
                                        {d.role}
                                    </span>
                                </div>
                                <div className="flex items-center justify-end gap-6 w-2/3">
                                    <div className="text-right">
                                        <p className="text-[8px] uppercase tracking-widest text-gray-500">Before</p>
                                        <p className="font-mono text-sm text-gray-400">{d.before > 0 ? d.before.toFixed(1) + "%" : "—"}</p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-[8px] uppercase tracking-widest text-gray-500">After</p>
                                        <p className="font-mono text-sm text-white">{d.after > 0 ? d.after.toFixed(1) + "%" : "—"}</p>
                                    </div>
                                    <div className={`flex items-center justify-end w-16 font-mono text-xs font-black ${d.diff > 0 ? "text-green-400" : d.diff < 0 ? "text-red-400" : "text-gray-600"}`}>
                                        {Math.abs(d.diff) < 0.1 ? "-" : (
                                            <>
                                                {d.diff > 0 ? <TrendingUp size={12} className="mr-1" /> : <TrendingDown size={12} className="mr-1" />}
                                                {d.diff > 0 ? "+" : ""}{d.diff.toFixed(1)}%
                                            </>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
