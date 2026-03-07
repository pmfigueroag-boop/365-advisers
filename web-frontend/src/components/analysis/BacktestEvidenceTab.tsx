"use client";

/**
 * BacktestEvidenceTab.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Shows signal backtest results with trade history and performance metrics.
 */

import { useState } from "react";
import { BarChart3, Loader2, Play, TrendingUp, TrendingDown } from "lucide-react";
import { useBacktest } from "@/hooks/useBacktest";
import type { BacktestResult, BacktestTrade } from "@/hooks/useBacktest";

interface BacktestEvidenceTabProps {
    ticker: string;
}

export default function BacktestEvidenceTab({ ticker }: BacktestEvidenceTabProps) {
    const { results, status, error, run } = useBacktest();
    const [period, setPeriod] = useState("1y");

    const handleRun = () => {
        if (ticker) run(ticker, { period });
    };

    return (
        <div className="space-y-5" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Header + Controls */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <BarChart3 size={14} className="text-[#d4af37]" />
                    <h3 className="text-sm font-black uppercase tracking-widest text-gray-300">Backtest Evidence</h3>
                </div>
                <div className="flex items-center gap-2">
                    <select
                        value={period}
                        onChange={(e) => setPeriod(e.target.value)}
                        className="bg-[#161b22] border border-[#30363d] rounded-lg text-[10px] px-2 py-1.5 text-gray-400 focus:outline-none focus:border-[#d4af37]/40"
                    >
                        <option value="3m">3 Months</option>
                        <option value="6m">6 Months</option>
                        <option value="1y">1 Year</option>
                        <option value="2y">2 Years</option>
                    </select>
                    <button
                        onClick={handleRun}
                        disabled={status === "running" || !ticker}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-wider bg-gradient-to-r from-[#d4af37] to-[#e8c84a] text-black hover:brightness-110 transition-all disabled:opacity-50"
                    >
                        {status === "running" ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
                        Run Backtest
                    </button>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div className="p-3 bg-red-500/5 border border-red-500/20 rounded-lg text-red-400 text-xs">
                    {error}
                </div>
            )}

            {/* Running */}
            {status === "running" && (
                <div className="flex items-center justify-center py-12 gap-3 text-[#d4af37]">
                    <Loader2 size={18} className="animate-spin" />
                    <span className="text-sm font-bold">Running backtest for {ticker}…</span>
                </div>
            )}

            {/* Empty state */}
            {status === "idle" && results.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                    <BarChart3 size={32} className="text-gray-700 mb-3" />
                    <p className="text-sm text-gray-500">No backtest data yet</p>
                    <p className="text-xs text-gray-600 mt-1">Click &quot;Run Backtest&quot; to see signal performance evidence</p>
                </div>
            )}

            {/* Results */}
            {results.map((result, idx) => (
                <BacktestResultCard key={idx} result={result} />
            ))}
        </div>
    );
}

function BacktestResultCard({ result }: { result: BacktestResult }) {
    const [showTrades, setShowTrades] = useState(false);

    // Safe number coercion — backend may return null/undefined/object
    const n = (v: unknown): number => (typeof v === "number" && !isNaN(v) ? v : 0);

    const wr = n(result.win_rate);
    const ar = n(result.avg_return);
    const sr = n(result.sharpe_ratio);
    const pf = n(result.profit_factor);
    const mx = n(result.max_return);
    const mn = n(result.min_return);

    const winColor = wr >= 60 ? "text-green-400" : wr >= 40 ? "text-yellow-400" : "text-red-400";
    const returnColor = ar >= 0 ? "text-green-400" : "text-red-400";

    return (
        <div className="glass-card border-[#30363d] overflow-hidden">
            <div className="p-5">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-black text-white" style={{ fontFamily: "var(--font-data)" }}>{result.ticker}</span>
                        {result.signal_id && (
                            <span className="text-[8px] font-mono text-gray-600 bg-[#161b22] px-1.5 py-0.5 rounded">{result.signal_id}</span>
                        )}
                    </div>
                    <span className="text-[8px] font-mono text-gray-600">{result.period} · {n(result.total_signals)} signals</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <p className="text-[8px] font-black uppercase tracking-wider text-gray-600 mb-1">Win Rate</p>
                        <p className={`text-lg font-black ${winColor}`} style={{ fontFamily: "var(--font-data)" }}>
                            {wr.toFixed(1)}%
                        </p>
                    </div>
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <p className="text-[8px] font-black uppercase tracking-wider text-gray-600 mb-1">Avg Return</p>
                        <p className={`text-lg font-black ${returnColor}`} style={{ fontFamily: "var(--font-data)" }}>
                            {ar >= 0 ? "+" : ""}{ar.toFixed(2)}%
                        </p>
                    </div>
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <p className="text-[8px] font-black uppercase tracking-wider text-gray-600 mb-1">Sharpe</p>
                        <p className="text-lg font-black text-blue-400" style={{ fontFamily: "var(--font-data)" }}>
                            {sr.toFixed(2)}
                        </p>
                    </div>
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <p className="text-[8px] font-black uppercase tracking-wider text-gray-600 mb-1">Profit Factor</p>
                        <p className="text-lg font-black text-[#d4af37]" style={{ fontFamily: "var(--font-data)" }}>
                            {pf.toFixed(2)}
                        </p>
                    </div>
                </div>

                {/* Range */}
                <div className="flex items-center justify-between text-[10px] text-gray-500 mb-4">
                    <span>Best: <span className="text-green-400 font-mono font-bold">+{mx.toFixed(2)}%</span></span>
                    <span>Worst: <span className="text-red-400 font-mono font-bold">{mn.toFixed(2)}%</span></span>
                </div>

                {/* Toggle trades */}
                {result.trades && result.trades.length > 0 && (
                    <button
                        onClick={() => setShowTrades(!showTrades)}
                        className="text-[9px] font-bold uppercase text-[#d4af37] hover:text-[#e8c84a] transition-colors"
                    >
                        {showTrades ? "Hide" : "Show"} {result.trades.length} Trades
                    </button>
                )}
            </div>

            {/* Trade history */}
            {showTrades && result.trades && (
                <div className="border-t border-[#30363d] overflow-x-auto">
                    <table className="w-full text-[10px]">
                        <thead>
                            <tr className="text-gray-600 text-[8px] font-black uppercase border-b border-[#30363d]">
                                <th className="text-left px-4 py-2">Entry</th>
                                <th className="text-left px-3 py-2">Exit</th>
                                <th className="text-right px-3 py-2">Return</th>
                                <th className="text-right px-3 py-2">Days</th>
                                <th className="text-right px-4 py-2">Strength</th>
                            </tr>
                        </thead>
                        <tbody>
                            {result.trades.slice(0, 20).map((trade, i) => (
                                <TradeRow key={i} trade={trade} />
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

function TradeRow({ trade }: { trade: BacktestTrade }) {
    const isPositive = trade.return_pct >= 0;
    return (
        <tr className="border-b border-[#30363d]/50 hover:bg-white/[0.02]">
            <td className="px-4 py-2 font-mono text-gray-400">{trade.entry_date}</td>
            <td className="px-3 py-2 font-mono text-gray-400">{trade.exit_date}</td>
            <td className={`px-3 py-2 text-right font-mono font-bold ${isPositive ? "text-green-400" : "text-red-400"}`}>
                <span className="flex items-center justify-end gap-1">
                    {isPositive ? <TrendingUp size={9} /> : <TrendingDown size={9} />}
                    {isPositive ? "+" : ""}{trade.return_pct.toFixed(2)}%
                </span>
            </td>
            <td className="px-3 py-2 text-right font-mono text-gray-500">{trade.holding_days}d</td>
            <td className="px-4 py-2 text-right">
                <span className={`text-[8px] font-black uppercase ${trade.signal_strength === "strong" ? "text-green-400" : trade.signal_strength === "moderate" ? "text-yellow-400" : "text-gray-500"}`}>
                    {trade.signal_strength}
                </span>
            </td>
        </tr>
    );
}
