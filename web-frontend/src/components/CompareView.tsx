"use client";

import { Loader2, CheckCircle2, AlertCircle, Zap, Trophy } from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface CompareAgent {
    agent_name: string;
    signal: string;
    confidence: number;
    analysis: string;
}

export interface CompareDalio {
    final_verdict: string;
    dalio_response?: {
        verdict?: string;
        risk_score?: number;
        summary_table?: string;
    };
}

export interface CompareResult {
    ticker: string;
    name?: string;
    price?: number;
    from_cache?: boolean;
    agents: CompareAgent[];
    fundamental_metrics?: Record<string, Record<string, unknown>>;
    dalio: CompareDalio;
    error?: string | null;
}

export type CompareStatus = "idle" | "loading" | "done" | "error";

export interface CompareState {
    status: CompareStatus;
    results: CompareResult[];
    error?: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function signalColor(signal?: string) {
    const s = (signal ?? "").toUpperCase();
    if (s.includes("BUY") || s === "AGGRESSIVE") return "text-green-400";
    if (s.includes("SELL") || s === "DEFENSIVE") return "text-red-400";
    return "text-gray-400";
}

function signalBg(signal?: string) {
    const s = (signal ?? "").toUpperCase();
    if (s.includes("BUY") || s === "AGGRESSIVE") return "bg-green-500/10 border-green-500/30";
    if (s.includes("SELL") || s === "DEFENSIVE") return "bg-red-500/10 border-red-500/30";
    return "bg-gray-500/10 border-gray-500/30";
}

function dalioSignal(dalio?: CompareDalio): string {
    const verdict = dalio?.dalio_response?.verdict ?? dalio?.final_verdict ?? "";
    if (verdict.toUpperCase().includes("BUY")) return "BUY";
    if (verdict.toUpperCase().includes("SELL")) return "SELL";
    return "HOLD";
}

/** Count BUY signals among agents for a result */
function countBuys(result: CompareResult): number {
    return result.agents.filter((a) => {
        const s = a.signal?.toUpperCase() ?? "";
        return s.includes("BUY") || s === "AGGRESSIVE";
    }).length;
}

const KEY_FUNDAMENTALS = [
    { key: "pe_ratio", label: "P/E Ratio", category: "valuation" },
    { key: "profit_margin", label: "Profit Margin", category: "profitability" },
    { key: "roe", label: "ROE", category: "profitability" },
    { key: "debt_to_equity", label: "D/E Ratio", category: "leverage" },
];

function getFundamental(metrics: Record<string, Record<string, unknown>> | undefined, category: string, key: string): string {
    const val = metrics?.[category]?.[key];
    if (val === undefined || val === null || val === "DATA_INCOMPLETE") return "–";
    if (typeof val === "number") {
        return Math.abs(val) > 1 ? val.toFixed(2) : (val * 100).toFixed(1) + "%";
    }
    return String(val);
}

const AGENT_ORDER = ["Lynch", "Buffett", "Marks", "Icahn", "Bollinger", "RSI", "MACD", "Gann"];

// ─── Main Component ───────────────────────────────────────────────────────────

export default function CompareView({ state }: { state: CompareState }) {
    const { status, results, error } = state;

    if (status === "idle") return null;

    if (status === "loading") {
        return (
            <div className="flex flex-col items-center justify-center py-24 gap-4">
                <Loader2 size={36} className="text-[#d4af37] animate-spin" />
                <p className="text-[#d4af37] font-bold uppercase tracking-widest text-sm animate-pulse">
                    Running parallel analysis...
                </p>
                <p className="text-xs text-gray-600">Tickers already in cache will appear first</p>
            </div>
        );
    }

    if (status === "error") {
        return (
            <div className="flex flex-col items-center justify-center py-24 gap-3">
                <AlertCircle size={32} className="text-red-500" />
                <p className="text-red-400 text-sm font-mono">{error}</p>
            </div>
        );
    }

    if (!results.length) return null;

    // Determine winner: most BUY signals (ties → first ticker wins)
    const buysCounts = results.map(countBuys);
    const maxBuys = Math.max(...buysCounts);
    const winnerIdx = maxBuys > 0 ? buysCounts.indexOf(maxBuys) : -1;

    // Collect all agent names that appear across results
    const allAgentNames = AGENT_ORDER.filter((name) =>
        results.some((r) => r.agents.some((a) => a.agent_name === name))
    );

    return (
        <div className="space-y-6" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            {/* ── Column headers ── */}
            <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${results.length}, 1fr)` }}>
                {results.map((res, i) => {
                    const isWinner = i === winnerIdx;
                    const dSig = dalioSignal(res.dalio);
                    return (
                        <div
                            key={res.ticker}
                            className={`glass-card p-5 border-2 transition-all ${isWinner
                                    ? "border-[#d4af37] bg-[#d4af37]/5"
                                    : "border-[#30363d]"
                                }`}
                        >
                            {isWinner && (
                                <div className="flex items-center gap-1 mb-2">
                                    <Trophy size={10} className="text-[#d4af37]" />
                                    <span className="text-[8px] font-black uppercase tracking-widest text-[#d4af37]">Best Pick</span>
                                </div>
                            )}
                            <div className="flex items-start justify-between gap-2">
                                <div>
                                    <h2 className={`text-2xl font-black ${isWinner ? "text-[#d4af37]" : "text-white"}`}>
                                        {res.ticker}
                                    </h2>
                                    <p className="text-[10px] text-gray-500 mt-0.5 leading-tight">{res.name ?? res.ticker}</p>
                                    {res.price && (
                                        <p className="text-xs font-mono text-gray-400 mt-1">${res.price.toFixed(2)}</p>
                                    )}
                                </div>
                                <div className="flex flex-col items-end gap-1">
                                    <span className={`text-[9px] font-black px-2 py-1 rounded border uppercase ${signalBg(dSig)} ${signalColor(dSig)}`}>
                                        {dSig}
                                    </span>
                                    {res.from_cache && (
                                        <span className="flex items-center gap-1 text-[8px] text-amber-400 font-bold">
                                            <Zap size={8} fill="currentColor" />cached
                                        </span>
                                    )}
                                </div>
                            </div>
                            {/* Dalio summary */}
                            {res.dalio?.final_verdict && (
                                <p className="text-[10px] text-gray-500 mt-3 italic leading-relaxed line-clamp-3 border-t border-[#30363d] pt-3">
                                    "{res.dalio.final_verdict}"
                                </p>
                            )}
                            {res.error && (
                                <p className="text-[10px] text-red-400 mt-2 font-mono">{res.error}</p>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* ── Agent verdicts grid ── */}
            <section className="glass-card border-[#30363d] overflow-hidden">
                <div className="px-5 py-3 border-b border-[#30363d] bg-[#0d1117]/50">
                    <h3 className="text-[10px] font-black uppercase tracking-widest text-gray-400">Agent Verdicts</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                        <thead>
                            <tr className="border-b border-[#30363d]">
                                <th className="text-left px-4 py-2 text-[9px] font-black uppercase tracking-widest text-gray-600 w-24">Mind</th>
                                {results.map((r, i) => (
                                    <th
                                        key={r.ticker}
                                        className={`text-center px-4 py-2 text-[10px] font-black uppercase tracking-widest ${i === winnerIdx ? "text-[#d4af37]" : "text-gray-400"
                                            }`}
                                    >
                                        {r.ticker}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {allAgentNames.map((agentName) => (
                                <tr key={agentName} className="border-b border-[#30363d]/50 hover:bg-[#161b22]/40 transition-colors">
                                    <td className="px-4 py-2.5 font-bold text-[10px] text-gray-500">{agentName}</td>
                                    {results.map((res) => {
                                        const agent = res.agents.find((a) => a.agent_name === agentName);
                                        if (!agent) {
                                            return (
                                                <td key={res.ticker} className="text-center px-4 py-2.5 text-gray-700 text-[9px]">–</td>
                                            );
                                        }
                                        return (
                                            <td key={res.ticker} className="text-center px-4 py-2.5">
                                                <div className="flex flex-col items-center gap-1">
                                                    <span className={`text-[9px] font-black uppercase ${signalColor(agent.signal)}`}>
                                                        {agent.signal}
                                                    </span>
                                                    <div className="w-12 h-0.5 bg-[#30363d] rounded overflow-hidden">
                                                        <div
                                                            className={`h-full rounded ${signalColor(agent.signal) === "text-green-400" ? "bg-green-500" :
                                                                    signalColor(agent.signal) === "text-red-400" ? "bg-red-500" :
                                                                        "bg-gray-500"
                                                                }`}
                                                            style={{ width: `${(agent.confidence ?? 0) * 100}%` }}
                                                        />
                                                    </div>
                                                    <span className="text-[8px] font-mono text-gray-700">
                                                        {((agent.confidence ?? 0) * 100).toFixed(0)}%
                                                    </span>
                                                </div>
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                            {/* BUY count row */}
                            <tr className="bg-[#0d1117]/40 border-t border-[#30363d]">
                                <td className="px-4 py-2 text-[9px] font-black uppercase text-gray-600 tracking-widest">BUY signals</td>
                                {results.map((res, i) => (
                                    <td key={res.ticker} className={`text-center px-4 py-2 font-black text-sm ${i === winnerIdx ? "text-[#d4af37]" : "text-gray-500"
                                        }`}>
                                        {buysCounts[i]} / {res.agents.length}
                                    </td>
                                ))}
                            </tr>
                        </tbody>
                    </table>
                </div>
            </section>

            {/* ── Key fundamentals grid ── */}
            <section className="glass-card border-[#30363d] overflow-hidden">
                <div className="px-5 py-3 border-b border-[#30363d] bg-[#0d1117]/50">
                    <h3 className="text-[10px] font-black uppercase tracking-widest text-gray-400">Key Fundamentals</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                        <thead>
                            <tr className="border-b border-[#30363d]">
                                <th className="text-left px-4 py-2 text-[9px] font-black uppercase tracking-widest text-gray-600 w-32">Metric</th>
                                {results.map((r, i) => (
                                    <th key={r.ticker} className={`text-center px-4 py-2 text-[10px] font-black uppercase ${i === winnerIdx ? "text-[#d4af37]" : "text-gray-400"}`}>
                                        {r.ticker}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {KEY_FUNDAMENTALS.map(({ key, label, category }) => (
                                <tr key={key} className="border-b border-[#30363d]/50 hover:bg-[#161b22]/40 transition-colors">
                                    <td className="px-4 py-2.5 text-[10px] text-gray-500 font-medium">{label}</td>
                                    {results.map((res) => (
                                        <td key={res.ticker} className="text-center px-4 py-2.5 font-mono text-[10px] text-gray-300">
                                            {getFundamental(res.fundamental_metrics, category, key)}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}
