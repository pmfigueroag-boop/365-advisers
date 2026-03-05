"use client";

import { PieChart, List, FileWarning, RefreshCw, Briefcase, Plus, ShieldAlert, Activity, Save } from "lucide-react";
import { useState, useMemo, useEffect } from "react";
import type { PortfolioRecommendationResult, PortfolioPositionOutput } from "../hooks/usePortfolioBuilder";
import { usePortfolioBuilder } from "../hooks/usePortfolioBuilder";
import { HistoryEntry } from "../hooks/useAnalysisHistory";
import WhatIfSimulator from "./WhatIfSimulator";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface SavedPortfolio {
    id: number;
    name: string;
    strategy: string;
    risk_level: string;
    total_allocation: number;
    created_at: string;
}

interface PortfolioDashboardProps {
    historyEntries: HistoryEntry[];
}

export default function PortfolioDashboard({ historyEntries }: PortfolioDashboardProps) {
    const { buildPortfolio, result, isLoading, error, reset } = usePortfolioBuilder();
    const [savedLoading, setSavedLoading] = useState(false);
    const [savedPorts, setSavedPorts] = useState<SavedPortfolio[]>([]);

    const fetchSavedPortfolios = async () => {
        try {
            const res = await fetch(`${BACKEND_URL}/portfolio`);
            if (res.ok) {
                const data = await res.json();
                setSavedPorts(data);
            }
        } catch (e) { }
    };

    useEffect(() => {
        fetchSavedPortfolios();
    }, []);

    const handleSavePortfolio = async () => {
        if (!result) return;
        setSavedLoading(true);
        try {
            const payload = {
                name: `Institutional Core-Satellite ${new Date().toLocaleDateString()}`,
                strategy: "Institutional Risk Parity",
                risk_level: result.risk_level,
                total_allocation: result.total_allocation,
                positions: [
                    ...result.core_positions.map(p => ({ ...p, role: "CORE" })),
                    ...result.satellite_positions.map(p => ({ ...p, role: "SATELLITE" }))
                ]
            };
            const res = await fetch(`${BACKEND_URL}/portfolio`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                await fetchSavedPortfolios();
            }
        } catch (err) {
            console.error(err);
        } finally {
            setSavedLoading(false);
        }
    };

    // We only consider history entries that have finished successfully and generated position_sizing data
    const eligiblePositions = useMemo(() => {
        return historyEntries
            .filter(e => Number(e.fundamental_score) > 0 && e.opportunity_score !== undefined && e.position_sizing !== undefined)
            .map(e => ({
                ticker: e.ticker,
                sector: e.sector || "Unknown",
                opportunity_score: e.opportunity_score as number,
                dimensions: typeof e.dimensions === "string" ? JSON.parse(e.dimensions) : (e.dimensions || {}),
                position_sizing: typeof e.position_sizing === "string" ? JSON.parse(e.position_sizing) : e.position_sizing,
                volatility_atr: e.volatility_atr,
                date: e.timestamp
            }));
    }, [historyEntries]);

    // Ensure we send unique tickers to the builder (keep only the newest)
    const uniquePositionsToBuild = useMemo(() => {
        const map = new Map();
        for (const pos of eligiblePositions) {
            // Because historyEntries is sorted newest first, the first time we see a ticker it's the newest one
            if (!map.has(pos.ticker)) {
                map.set(pos.ticker, pos);
            }
        }
        return Array.from(map.values());
    }, [eligiblePositions]);

    const handleBuild = () => {
        if (uniquePositionsToBuild.length === 0) return;
        buildPortfolio(uniquePositionsToBuild);
    };

    return (
        <div className="space-y-6" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            {/* Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <Briefcase size={14} className="text-[#60a5fa]" />
                        <h2 className="text-[9px] font-black uppercase tracking-[0.2em] text-gray-500">Portfolio Construction Engine</h2>
                    </div>
                </div>

                <div className="flex gap-2">
                    <button
                        onClick={handleBuild}
                        disabled={isLoading || uniquePositionsToBuild.length === 0}
                        className="flex items-center gap-1.5 text-[8px] font-bold bg-[#60a5fa]/10 text-[#60a5fa] border border-[#60a5fa]/30 hover:bg-[#60a5fa]/20 px-3 py-1.5 rounded transition-colors tracking-wider uppercase disabled:opacity-50"
                    >
                        {isLoading ? <RefreshCw size={10} className="animate-spin" /> : <Plus size={10} />}
                        Build Portfolio ({uniquePositionsToBuild.length} Assets)
                    </button>
                    {result && (
                        <>
                            <button
                                onClick={handleSavePortfolio}
                                disabled={savedLoading}
                                className="flex items-center gap-1.5 text-[8px] font-bold bg-[#d4af37]/10 text-[#d4af37] border border-[#d4af37]/30 hover:bg-[#d4af37]/20 px-3 py-1.5 rounded transition-colors tracking-wider uppercase disabled:opacity-50"
                            >
                                {savedLoading ? <RefreshCw size={10} className="animate-spin" /> : <Save size={10} />}
                                Save Session
                            </button>
                            <button
                                onClick={reset}
                                className="flex items-center gap-1.5 text-[8px] font-bold text-gray-500 hover:text-white px-3 py-1.5 border border-[#30363d] rounded transition-colors tracking-wider uppercase"
                            >
                                Reset
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Empty State */}
            {uniquePositionsToBuild.length === 0 && !result && (
                <div className="glass-card p-12 flex flex-col items-center justify-center text-center border-dashed border-[#30363d]">
                    <PieChart size={32} className="text-[#30363d] mb-4" />
                    <p className="text-sm font-bold text-gray-400 mb-2">No Assets in Memory</p>
                    <p className="text-[10px] text-gray-500 max-w-sm leading-relaxed">
                        Analyze symbols first. The Portfolio Engine will use your Analysis History to construct a Risk-Adjusted Core-Satellite Portfolio automatically.
                    </p>
                </div>
            )}

            {/* Error */}
            {error && (
                <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded flex items-start gap-3">
                    <ShieldAlert size={14} className="mt-0.5 flex-shrink-0" />
                    <p className="text-xs">{error}</p>
                </div>
            )}

            {/* Pre-Build Warning */}
            {uniquePositionsToBuild.length > 0 && !result && !isLoading && !error && (
                <div className="glass-card p-6 border-l-2 border-l-[#60a5fa]">
                    <div className="flex items-center gap-3 mb-4">
                        <Activity size={16} className="text-[#60a5fa]" />
                        <h3 className="text-sm font-black text-white">Ready to Construct</h3>
                    </div>
                    <p className="text-xs text-gray-400 mb-4 leading-relaxed">
                        The engine found {uniquePositionsToBuild.length} unique analyzed assets in your history. Click "Build Portfolio" to automatically categorize them into Core/Satellite buckets, apply risk volatility limits, and optimize sector exposures.
                    </p>
                    <div className="flex flex-wrap gap-2">
                        {uniquePositionsToBuild.map(p => (
                            <span key={p.ticker} className="bg-[#161b22] border border-[#30363d] text-gray-400 text-[9px] font-mono px-2 py-1 rounded">
                                {p.ticker}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Results */}
            {result && (
                <div className="space-y-6" style={{ animation: "fadeSlideIn 0.5s ease both" }}>

                    {/* Top Stats */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="glass-card p-4 border-[#30363d]">
                            <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1">Total Allocated</p>
                            <p className="text-2xl font-black text-white font-mono">{result.total_allocation.toFixed(1)}%</p>
                        </div>
                        <div className="glass-card p-4 border border-[#d4af37]/30 bg-[#d4af37]/5">
                            <p className="text-[9px] font-black uppercase tracking-widest text-[#d4af37] mb-1">Core Block</p>
                            <p className="text-2xl font-black text-[#d4af37] font-mono">{result.core_allocation_total.toFixed(1)}%</p>
                        </div>
                        <div className="glass-card p-4 border border-[#60a5fa]/30 bg-[#60a5fa]/5">
                            <p className="text-[9px] font-black uppercase tracking-widest text-[#60a5fa] mb-1">Satellite Block</p>
                            <p className="text-2xl font-black text-[#60a5fa] font-mono">{result.satellite_allocation_total.toFixed(1)}%</p>
                        </div>
                        <div className="glass-card p-4 border-[#30363d]">
                            <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1">Risk Profile</p>
                            <p className={`text-xl mt-1 font-black uppercase ${result.risk_level === "ELEVATED" ? "text-orange-400" : "text-green-400"}`}>
                                {result.risk_level}
                            </p>
                        </div>
                    </div>

                    {/* Violations */}
                    {result.violations_detected.length > 0 && (
                        <div className="bg-orange-500/10 border border-orange-500/20 p-4 rounded-xl">
                            <div className="flex items-center gap-2 mb-2">
                                <FileWarning size={14} className="text-orange-400" />
                                <p className="text-[10px] font-black uppercase tracking-widest text-orange-400">System Adjustments</p>
                            </div>
                            <ul className="space-y-1 pl-6 list-disc text-[11px] text-orange-200/80">
                                {result.violations_detected.map((v, i) => (
                                    <li key={i}>{v}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Positions Split */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* CORE */}
                        <div className="glass-card p-5 border-t-2 border-[#d4af37]">
                            <div className="flex items-center justify-between mb-4 pb-2 border-b border-[#30363d]">
                                <h3 className="text-xs font-black uppercase tracking-widest text-[#d4af37]">Core Positions</h3>
                                <span className="text-[10px] bg-[#d4af37]/10 text-[#d4af37] px-2 py-0.5 rounded font-mono">{result.core_positions.length}</span>
                            </div>
                            <div className="space-y-2">
                                {result.core_positions.length === 0 ? (
                                    <p className="text-[10px] text-gray-500 italic">No assets qualified for CORE categorization.</p>
                                ) : (
                                    result.core_positions.map(p => (
                                        <div key={p.ticker} className="flex items-center justify-between bg-[#0d1117]/50 px-3 py-2 rounded">
                                            <div className="flex items-center gap-3">
                                                <span className="font-bold text-white text-sm w-12">{p.ticker}</span>
                                                <span className="text-[9px] uppercase tracking-wider text-gray-500 hidden sm:inline">{p.sector}</span>
                                            </div>
                                            <span className="font-mono text-sm font-black text-[#d4af37]">{p.target_weight.toFixed(1)}%</span>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>

                        {/* SATELLITE */}
                        <div className="glass-card p-5 border-t-2 border-[#60a5fa]">
                            <div className="flex items-center justify-between mb-4 pb-2 border-b border-[#30363d]">
                                <h3 className="text-xs font-black uppercase tracking-widest text-[#60a5fa]">Satellite Positions</h3>
                                <span className="text-[10px] bg-[#60a5fa]/10 text-[#60a5fa] px-2 py-0.5 rounded font-mono">{result.satellite_positions.length}</span>
                            </div>
                            <div className="space-y-2">
                                {result.satellite_positions.length === 0 ? (
                                    <p className="text-[10px] text-gray-500 italic">No assets qualified for SATELLITE categorization.</p>
                                ) : (
                                    result.satellite_positions.map(p => (
                                        <div key={p.ticker} className="flex items-center justify-between bg-[#0d1117]/50 px-3 py-2 rounded">
                                            <div className="flex items-center gap-3">
                                                <span className="font-bold text-white text-sm w-12">{p.ticker}</span>
                                                <span className="text-[9px] uppercase tracking-wider text-gray-500 hidden sm:inline">{p.sector}</span>
                                            </div>
                                            <span className="font-mono text-sm font-black text-[#60a5fa]">{p.target_weight.toFixed(1)}%</span>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>

                    {/* WhatIfSimulator Component */}
                    <WhatIfSimulator
                        baseResult={result}
                        basePositions={uniquePositionsToBuild}
                        availableHistory={historyEntries}
                    />

                </div>
            )}

            {/* Saved Portfolios List */}
            {savedPorts.length > 0 && !result && !isLoading && (
                <div className="mt-8 pt-8 border-t border-[#30363d] animate-[fadeSlideIn_0.4s_ease_both]">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                            <Save size={14} className="text-gray-400" />
                            <h3 className="text-[10px] font-black uppercase tracking-widest text-gray-400">Database Persistence (Phase 2.5)</h3>
                        </div>
                        <span className="text-[10px] font-mono text-gray-500">{savedPorts.length} Saved Profiles</span>
                    </div>

                    <div className="space-y-3">
                        {savedPorts.map(sp => (
                            <div key={sp.id} className="glass-card hover:bg-white/5 transition-colors p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between cursor-pointer group border-[#30363d]">
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <h4 className="text-sm font-bold text-white group-hover:text-[#60a5fa] transition-colors">{sp.name}</h4>
                                        <span className={`text-[8px] px-1.5 py-0.5 rounded uppercase font-black tracking-wider ${sp.risk_level === "ELEVATED" ? "bg-orange-500/10 text-orange-400" : "bg-green-500/10 text-green-400"}`}>
                                            {sp.risk_level}
                                        </span>
                                    </div>
                                    <div className="flex gap-4 text-[10px] text-gray-500 font-mono">
                                        <span>Strategy: {sp.strategy}</span>
                                        <span>Capacity: {sp.total_allocation.toFixed(1)}%</span>
                                    </div>
                                </div>
                                <div className="text-right mt-2 sm:mt-0">
                                    <span className="text-[9px] text-gray-600 font-mono">
                                        {new Date(sp.created_at).toLocaleString()}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
