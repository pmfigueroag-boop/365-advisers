"use client";

import React, { useState, useEffect } from "react";

/* ────── Types ────── */
interface SignalHealth {
  signal_id: string;
  health: string;
  rolling_ic: number;
  half_life_days: number;
  weight_multiplier: number;
  events_count: number;
}

interface PipelineStep {
  step_name: string;
  status: string;
  duration_ms: number;
}

interface DashboardData {
  institutional_score: number;
  signal_validation: number;
  portfolio_construction: number;
  risk_management: number;
  execution: number;
  compliance: number;
  signals: SignalHealth[];
  active_kills: number;
  last_run: string;
  pipeline_steps: PipelineStep[];
  portfolio_beta: number;
  portfolio_sharpe: number;
  total_positions: number;
  recent_turnover: number;
  providers_healthy: number;
  providers_total: number;
}

/* ────── Mock Data ────── */
const MOCK_DATA: DashboardData = {
  institutional_score: 92,
  signal_validation: 100,
  portfolio_construction: 93,
  risk_management: 80,
  execution: 65,
  compliance: 65,
  signals: [
    { signal_id: "sig.momentum", health: "healthy", rolling_ic: 0.08, half_life_days: 12.5, weight_multiplier: 1.0, events_count: 347 },
    { signal_id: "sig.value", health: "healthy", rolling_ic: 0.05, half_life_days: 28.0, weight_multiplier: 1.0, events_count: 215 },
    { signal_id: "sig.quality", health: "flagged", rolling_ic: 0.02, half_life_days: 45.0, weight_multiplier: 0.5, events_count: 163 },
    { signal_id: "sig.event", health: "healthy", rolling_ic: 0.06, half_life_days: 8.0, weight_multiplier: 1.0, events_count: 89 },
    { signal_id: "sig.growth", health: "killed", rolling_ic: -0.03, half_life_days: 60.0, weight_multiplier: 0.0, events_count: 42 },
  ],
  active_kills: 1,
  last_run: new Date().toISOString(),
  pipeline_steps: [
    { step_name: "Universe Selection", status: "success", duration_ms: 12 },
    { step_name: "Signal Scanning", status: "success", duration_ms: 245 },
    { step_name: "Validation", status: "success", duration_ms: 180 },
    { step_name: "Kill Switch", status: "success", duration_ms: 8 },
    { step_name: "Signal→Portfolio Bridge", status: "success", duration_ms: 55 },
    { step_name: "Ledoit-Wolf Shrinkage", status: "success", duration_ms: 22 },
    { step_name: "MVO Optimization", status: "success", duration_ms: 340 },
    { step_name: "Factor Neutralization", status: "success", duration_ms: 15 },
    { step_name: "Rebalancing", status: "success", duration_ms: 28 },
    { step_name: "Audit Trail", status: "success", duration_ms: 5 },
    { step_name: "Performance Report", status: "success", duration_ms: 95 },
  ],
  portfolio_beta: 0.02,
  portfolio_sharpe: 1.45,
  total_positions: 12,
  recent_turnover: 0.08,
  providers_healthy: 3,
  providers_total: 3,
};

/* ────── Helpers ────── */
const healthColor = (health: string) => {
  switch (health) {
    case "healthy": return "#10b981";
    case "flagged": return "#f59e0b";
    case "throttled": return "#f97316";
    case "killed": return "#ef4444";
    default: return "#6b7280";
  }
};

const scoreColor = (score: number) => {
  if (score >= 90) return "#10b981";
  if (score >= 75) return "#3b82f6";
  if (score >= 60) return "#f59e0b";
  return "#ef4444";
};

const ScoreGauge = ({ score, label, size = 80 }: { score: number; label: string; size?: number }) => {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = scoreColor(score);
  
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size/2} ${size/2})`}
          style={{ transition: "stroke-dashoffset 1s ease-in-out" }} />
        <text x={size/2} y={size/2} textAnchor="middle" dy="0.35em"
          style={{ fill: "#fff", fontSize: size > 70 ? "20px" : "14px", fontWeight: 700, fontFamily: "var(--font-geist-mono)" }}>
          {score}
        </text>
      </svg>
      <span style={{ color: "rgba(255,255,255,0.5)", fontSize: "11px", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.5px" }}>{label}</span>
    </div>
  );
};

/* ────── Component ────── */
export default function QuantDashboard() {
  const [data] = useState<DashboardData>(MOCK_DATA);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  if (!mounted) return null;

  const totalPipelineMs = data.pipeline_steps.reduce((s, st) => s + st.duration_ms, 0);

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(135deg, #0a0a1a 0%, #111827 40%, #0f172a 100%)",
      color: "#fff",
      fontFamily: "var(--font-inter), system-ui, sans-serif",
      padding: "24px",
    }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: "28px", paddingBottom: "16px",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 700, margin: 0, letterSpacing: "-0.5px" }}>
            Quant Infrastructure Dashboard
          </h1>
          <p style={{ color: "rgba(255,255,255,0.4)", fontSize: "13px", margin: "4px 0 0" }}>
            365 Advisers — Institutional Analytics
          </p>
        </div>
        <div style={{
          display: "flex", gap: "8px", alignItems: "center",
          background: "rgba(16, 185, 129, 0.1)", border: "1px solid rgba(16, 185, 129, 0.2)",
          borderRadius: "8px", padding: "8px 16px",
        }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 8px #10b981" }} />
          <span style={{ fontSize: "13px", fontWeight: 600, color: "#10b981" }}>Pipeline Active</span>
        </div>
      </div>

      {/* Scorecard Row */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 3fr",
        gap: "16px", marginBottom: "20px",
      }}>
        {/* Main Score */}
        <div style={{
          background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)",
          borderRadius: "12px", padding: "24px",
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        }}>
          <ScoreGauge score={data.institutional_score} label="Institutional Score" size={120} />
        </div>

        {/* Sub-scores */}
        <div style={{
          background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)",
          borderRadius: "12px", padding: "20px",
          display: "flex", alignItems: "center", justifyContent: "space-around",
        }}>
          <ScoreGauge score={data.signal_validation} label="Signals" />
          <ScoreGauge score={data.portfolio_construction} label="Portfolio" />
          <ScoreGauge score={data.risk_management} label="Risk" />
          <ScoreGauge score={data.execution} label="Execution" />
          <ScoreGauge score={data.compliance} label="Compliance" />
        </div>
      </div>

      {/* Two Column Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "20px" }}>

        {/* Signal Health Table */}
        <div style={{
          background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)",
          borderRadius: "12px", padding: "20px",
        }}>
          <h3 style={{ fontSize: "14px", fontWeight: 600, margin: "0 0 16px", color: "rgba(255,255,255,0.7)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Signal Health <span style={{ color: "rgba(255,255,255,0.3)", fontWeight: 400 }}>• Kill Switch</span>
          </h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <thead>
              <tr style={{ color: "rgba(255,255,255,0.35)", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                <th style={{ textAlign: "left", padding: "4px 8px" }}>Signal</th>
                <th style={{ textAlign: "center", padding: "4px 8px" }}>Status</th>
                <th style={{ textAlign: "right", padding: "4px 8px" }}>IC</th>
                <th style={{ textAlign: "right", padding: "4px 8px" }}>Half-Life</th>
                <th style={{ textAlign: "right", padding: "4px 8px" }}>Weight</th>
              </tr>
            </thead>
            <tbody>
              {data.signals.map((sig) => (
                <tr key={sig.signal_id} style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}>
                  <td style={{ padding: "10px 8px", fontFamily: "var(--font-geist-mono)", fontWeight: 500, fontSize: "12px" }}>{sig.signal_id}</td>
                  <td style={{ textAlign: "center", padding: "10px 8px" }}>
                    <span style={{
                      display: "inline-block", padding: "2px 10px", borderRadius: "12px",
                      fontSize: "11px", fontWeight: 600, textTransform: "uppercase",
                      background: `${healthColor(sig.health)}20`,
                      color: healthColor(sig.health),
                      border: `1px solid ${healthColor(sig.health)}30`,
                    }}>{sig.health}</span>
                  </td>
                  <td style={{
                    textAlign: "right", padding: "10px 8px",
                    fontFamily: "var(--font-geist-mono)", fontWeight: 600,
                    color: sig.rolling_ic >= 0.03 ? "#10b981" : sig.rolling_ic >= 0 ? "#f59e0b" : "#ef4444",
                  }}>{sig.rolling_ic.toFixed(3)}</td>
                  <td style={{ textAlign: "right", padding: "10px 8px", fontFamily: "var(--font-geist-mono)", color: "rgba(255,255,255,0.6)" }}>{sig.half_life_days}d</td>
                  <td style={{
                    textAlign: "right", padding: "10px 8px",
                    fontFamily: "var(--font-geist-mono)", fontWeight: 600,
                    color: sig.weight_multiplier === 1 ? "rgba(255,255,255,0.5)" : sig.weight_multiplier === 0 ? "#ef4444" : "#f59e0b",
                  }}>{(sig.weight_multiplier * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pipeline Status */}
        <div style={{
          background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)",
          borderRadius: "12px", padding: "20px",
        }}>
          <h3 style={{ fontSize: "14px", fontWeight: 600, margin: "0 0 16px", color: "rgba(255,255,255,0.7)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Pipeline Execution <span style={{ color: "rgba(255,255,255,0.3)", fontWeight: 400 }}>• {totalPipelineMs}ms</span>
          </h3>
          {data.pipeline_steps.map((step, i) => {
            const pct = (step.duration_ms / Math.max(totalPipelineMs, 1)) * 100;
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                <span style={{
                  width: 16, height: 16, borderRadius: "4px", display: "flex", alignItems: "center", justifyContent: "center",
                  background: step.status === "success" ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)",
                  color: step.status === "success" ? "#10b981" : "#ef4444",
                  fontSize: "10px", fontWeight: 700,
                }}>✓</span>
                <span style={{ flex: 1, fontSize: "12px", color: "rgba(255,255,255,0.6)" }}>{step.step_name}</span>
                <div style={{ width: 60, height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: 2,
                    width: `${Math.max(pct, 3)}%`,
                    background: step.duration_ms > 200 ? "#f59e0b" : "#10b981",
                    transition: "width 1s ease",
                  }} />
                </div>
                <span style={{ fontSize: "11px", fontFamily: "var(--font-geist-mono)", color: "rgba(255,255,255,0.35)", width: 40, textAlign: "right" }}>
                  {step.duration_ms}ms
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Bottom Row: Portfolio + Providers */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "16px" }}>
        {[
          { label: "Portfolio Beta", value: data.portfolio_beta.toFixed(3), sub: "Market Neutral", color: Math.abs(data.portfolio_beta) < 0.1 ? "#10b981" : "#f59e0b" },
          { label: "Sharpe Ratio", value: data.portfolio_sharpe.toFixed(2), sub: "Annualized", color: data.portfolio_sharpe >= 1 ? "#10b981" : "#f59e0b" },
          { label: "Positions", value: data.total_positions.toString(), sub: `Turnover ${(data.recent_turnover * 100).toFixed(0)}%`, color: "#3b82f6" },
          { label: "Data Providers", value: `${data.providers_healthy}/${data.providers_total}`, sub: "Circuit Breakers", color: data.providers_healthy === data.providers_total ? "#10b981" : "#ef4444" },
        ].map((card, i) => (
          <div key={i} style={{
            background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)",
            borderRadius: "12px", padding: "20px", textAlign: "center",
          }}>
            <div style={{ color: "rgba(255,255,255,0.4)", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>{card.label}</div>
            <div style={{ fontSize: "28px", fontWeight: 700, fontFamily: "var(--font-geist-mono)", color: card.color }}>{card.value}</div>
            <div style={{ color: "rgba(255,255,255,0.3)", fontSize: "11px", marginTop: "4px" }}>{card.sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
