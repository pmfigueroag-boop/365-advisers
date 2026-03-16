"use client";

/**
 * RiskBudgetPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Shows portfolio risk metrics: VaR, max drawdown, Sharpe estimate.
 * P1 Fix: Added empty state with guidance.
 */

import { Shield, AlertTriangle, TrendingDown, BarChart3, Microscope } from "lucide-react";

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
    const hasAnyData = var95 != null || maxDrawdown != null || sharpeEstimate != null || portfolioVolatility != null;

    // Empty state
    if (!hasAnyData) {
        return (
            <div className={`glass-card p-5 border-[#30363d] ${className}`}>
                <div className="flex items-center gap-2 mb-4">
                    <Shield size={12} className="text-red-400" />
                    <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Risk Budget</span>
                </div>
                <div className="flex flex-col items-center justify-center py-6 text-center">
                    <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-3"
                        style={{
                            background: 'linear-gradient(135deg, rgba(22,27,34,0.9), rgba(13,17,26,0.95))',
                            border: '1px solid rgba(239,68,68,0.15)',
                        }}>
                        <Microscope size={20} className="text-gray-600" />
                    </div>
                    <p className="text-[11px] text-gray-500 font-medium mb-1">
                        Not enough data
                    </p>
                    <p className="text-[10px] text-gray-600 max-w-[180px] leading-relaxed">
                        Analyze 3+ assets in the Terminal to compute risk metrics
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center gap-2 mb-4">
                <Shield size={12} className="text-red-400" />
                <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Risk Budget</span>
            </div>

            <div className="grid grid-cols-2 gap-3">
                {var95 != null && (
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <AlertTriangle size={10} className="text-orange-400" />
                            <span className="text-[10px] font-black uppercase tracking-wider text-gray-600">VaR 95%</span>
                        </div>
                        <p className="text-lg font-black text-orange-400" style={{ fontFamily: "var(--font-data)" }}>
                            {var95.toFixed(1)}%
                        </p>
                    </div>
                )}

                {maxDrawdown != null && (
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <TrendingDown size={10} className="text-red-400" />
                            <span className="text-[10px] font-black uppercase tracking-wider text-gray-600">Max Drawdown</span>
                        </div>
                        <p className="text-lg font-black text-red-400" style={{ fontFamily: "var(--font-data)" }}>
                            {maxDrawdown.toFixed(1)}%
                        </p>
                    </div>
                )}

                {sharpeEstimate != null && (
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <BarChart3 size={10} className="text-blue-400" />
                            <span className="text-[10px] font-black uppercase tracking-wider text-gray-600">Sharpe Est.</span>
                        </div>
                        <p className="text-lg font-black text-blue-400" style={{ fontFamily: "var(--font-data)" }}>
                            {sharpeEstimate.toFixed(2)}
                        </p>
                    </div>
                )}

                {portfolioVolatility != null && (
                    <div className="bg-[#161b22] rounded-xl p-3 border border-[#30363d]">
                        <div className="flex items-center gap-1.5 mb-1">
                            <Shield size={10} className="text-purple-400" />
                            <span className="text-[10px] font-black uppercase tracking-wider text-gray-600">Portfolio Vol</span>
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
