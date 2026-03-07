"use client";

/**
 * RiskBudgetPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Shows portfolio risk metrics: VaR, max drawdown, Sharpe estimate.
 */

import { Shield, AlertTriangle, TrendingDown, BarChart3 } from "lucide-react";

interface RiskBudgetPanelProps {
    var95?: number;
    maxDrawdown?: number;
    sharpeEstimate?: number;
    portfolioVolatility?: number;
    className?: string;
}

export default function RiskBudgetPanel({
    var95,
    maxDrawdown,
    sharpeEstimate,
    portfolioVolatility,
    className = "",
}: RiskBudgetPanelProps) {
    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center gap-2 mb-4">
                <Shield size={12} className="text-red-400" />
                <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">Risk Budget</span>
            </div>

            <div className="grid grid-cols-2 gap-3">
                {var95 != null && (
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <AlertTriangle size={9} className="text-orange-400" />
                            <span className="text-[8px] font-black uppercase tracking-wider text-gray-600">VaR 95%</span>
                        </div>
                        <p className="text-lg font-black text-orange-400" style={{ fontFamily: "var(--font-data)" }}>
                            {var95.toFixed(1)}%
                        </p>
                    </div>
                )}

                {maxDrawdown != null && (
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <TrendingDown size={9} className="text-red-400" />
                            <span className="text-[8px] font-black uppercase tracking-wider text-gray-600">Max Drawdown</span>
                        </div>
                        <p className="text-lg font-black text-red-400" style={{ fontFamily: "var(--font-data)" }}>
                            {maxDrawdown.toFixed(1)}%
                        </p>
                    </div>
                )}

                {sharpeEstimate != null && (
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <BarChart3 size={9} className="text-blue-400" />
                            <span className="text-[8px] font-black uppercase tracking-wider text-gray-600">Sharpe Est.</span>
                        </div>
                        <p className="text-lg font-black text-blue-400" style={{ fontFamily: "var(--font-data)" }}>
                            {sharpeEstimate.toFixed(2)}
                        </p>
                    </div>
                )}

                {portfolioVolatility != null && (
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <Shield size={9} className="text-purple-400" />
                            <span className="text-[8px] font-black uppercase tracking-wider text-gray-600">Portfolio Vol</span>
                        </div>
                        <p className="text-lg font-black text-purple-400" style={{ fontFamily: "var(--font-data)" }}>
                            {portfolioVolatility.toFixed(1)}%
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
