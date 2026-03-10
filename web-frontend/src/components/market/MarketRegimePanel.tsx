"use client";

/**
 * MarketRegimePanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Displays the current market regime with key indicators.
 */

import { Globe, TrendingUp, TrendingDown, Minus } from "lucide-react";
import InfoTooltip from "@/components/shared/InfoTooltip";

interface MarketRegimePanelProps {
    regime?: string;
    universeSize?: number;
    computedAt?: string | null;
    className?: string;
}

const REGIME_CONFIG: Record<string, { icon: React.ReactNode; color: string; bg: string; label: string }> = {
    bullish: { icon: <TrendingUp size={18} />, color: "text-green-400", bg: "bg-green-500/10", label: "Bullish Regime" },
    bearish: { icon: <TrendingDown size={18} />, color: "text-red-400", bg: "bg-red-500/10", label: "Bearish Regime" },
    neutral: { icon: <Minus size={18} />, color: "text-yellow-400", bg: "bg-yellow-500/10", label: "Neutral Regime" },
    sideways: { icon: <Minus size={18} />, color: "text-gray-400", bg: "bg-gray-500/10", label: "Sideways Range" },
    volatile: { icon: <TrendingDown size={18} />, color: "text-orange-400", bg: "bg-orange-500/10", label: "High Volatility" },
};

export default function MarketRegimePanel({ regime = "neutral", universeSize = 0, computedAt, className = "" }: MarketRegimePanelProps) {
    const cfg = REGIME_CONFIG[regime.toLowerCase()] ?? REGIME_CONFIG.neutral;

    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center gap-2 mb-4">
                <Globe size={12} className="text-[#d4af37]" />
                <InfoTooltip text="Régimen de mercado detectado automáticamente: alcista, bajista, neutral, lateral o volátil. Se basa en el análisis de clusters de señales del universo de activos." position="bottom">
                    <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">Market Regime</span>
                </InfoTooltip>
            </div>

            <div className={`flex items-center gap-4 p-4 rounded-xl ${cfg.bg} mb-4`}>
                <span className={cfg.color}>{cfg.icon}</span>
                <div>
                    <p className={`text-lg font-black uppercase ${cfg.color}`}>{cfg.label}</p>
                    <p className="text-[10px] text-gray-500">Based on signal cluster analysis</p>
                </div>
            </div>

            <div className="space-y-2">
                <div className="flex items-center justify-between text-[10px]">
                    <InfoTooltip text="Cantidad de activos incluidos en el análisis de mercado. Se alimenta del resultado del último Idea Scan." showIcon={false}>
                        <span className="text-gray-600">Universe Size</span>
                    </InfoTooltip>
                    <span className="font-mono text-gray-400">{universeSize} assets</span>
                </div>
                {computedAt && (
                    <div className="flex items-center justify-between text-[10px]">
                        <InfoTooltip text="Fecha y hora del último cálculo de régimen y ranking de oportunidades." showIcon={false}>
                            <span className="text-gray-600">Last Computed</span>
                        </InfoTooltip>
                        <span className="font-mono text-gray-500">{new Date(computedAt).toLocaleString()}</span>
                    </div>
                )}
            </div>
        </div>
    );
}
