"use client";

/**
 * MarketRiskSignals.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Displays market-level risk signals: crowding warnings, drift, and alerts.
 */

import { AlertTriangle, Check, Shield } from "lucide-react";
import InfoTooltip from "@/components/shared/InfoTooltip";
import type { MonitoringAlert } from "@/hooks/useMonitoringAlerts";
import type { CrowdingAssessment } from "@/hooks/useCrowding";

interface MarketRiskSignalsProps {
    alerts: MonitoringAlert[];
    crowdingAssessments: Record<string, CrowdingAssessment>;
    className?: string;
}

export default function MarketRiskSignals({ alerts, crowdingAssessments, className = "" }: MarketRiskSignalsProps) {
    const criticalAlerts = alerts.filter((a) => a.severity === "critical");
    const warningAlerts = alerts.filter((a) => a.severity === "warning");
    const highCrowding = Object.entries(crowdingAssessments).filter(([, a]) => a.risk_level === "high" || a.risk_level === "extreme");

    const hasRisks = criticalAlerts.length > 0 || warningAlerts.length > 0 || highCrowding.length > 0;

    return (
        <div className={`glass-card p-5 border-[#30363d] ${className}`}>
            <div className="flex items-center gap-2 mb-4">
                <Shield size={12} className={hasRisks ? "text-orange-400" : "text-green-400"} />
                <InfoTooltip text="Alertas de riesgo a nivel de mercado: señales de crowding excesivo, drift de modelos, y alertas críticas del sistema de monitoreo." position="bottom">
                    <span className="text-[9px] font-black uppercase tracking-widest text-gray-400">Market Risk Signals</span>
                </InfoTooltip>
            </div>

            {!hasRisks ? (
                <div className="flex items-center gap-2 p-3 bg-green-500/5 rounded-lg border border-green-500/20">
                    <Check size={14} className="text-green-400" />
                    <span className="text-xs text-green-400">No significant risk signals detected</span>
                </div>
            ) : (
                <div className="space-y-2">
                    {criticalAlerts.length > 0 && (
                        <div className="flex items-start gap-2 p-3 bg-red-500/8 rounded-lg border border-red-500/20">
                            <AlertTriangle size={13} className="text-red-400 mt-0.5 flex-shrink-0" />
                            <div>
                                <span className="text-[9px] font-black text-red-400 uppercase">
                                    {criticalAlerts.length} Critical Alert{criticalAlerts.length > 1 ? "s" : ""}
                                </span>
                                <p className="text-[10px] text-gray-400 mt-0.5">{criticalAlerts[0]?.message}</p>
                            </div>
                        </div>
                    )}

                    {warningAlerts.length > 0 && (
                        <div className="flex items-start gap-2 p-3 bg-yellow-500/8 rounded-lg border border-yellow-500/20">
                            <AlertTriangle size={13} className="text-yellow-400 mt-0.5 flex-shrink-0" />
                            <div>
                                <span className="text-[9px] font-black text-yellow-400 uppercase">
                                    {warningAlerts.length} Warning{warningAlerts.length > 1 ? "s" : ""}
                                </span>
                                <p className="text-[10px] text-gray-400 mt-0.5">{warningAlerts[0]?.message}</p>
                            </div>
                        </div>
                    )}

                    {highCrowding.length > 0 && (
                        <div className="flex items-start gap-2 p-3 bg-orange-500/8 rounded-lg border border-orange-500/20">
                            <AlertTriangle size={13} className="text-orange-400 mt-0.5 flex-shrink-0" />
                            <div>
                                <span className="text-[9px] font-black text-orange-400 uppercase">
                                    {highCrowding.length} Crowding Warning{highCrowding.length > 1 ? "s" : ""}
                                </span>
                                <div className="flex gap-1.5 mt-1 flex-wrap">
                                    {highCrowding.map(([ticker, a]) => (
                                        <span key={ticker} className="text-[8px] font-mono text-orange-300 bg-orange-500/10 px-1.5 py-0.5 rounded">
                                            {ticker}: {a.risk_level}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
