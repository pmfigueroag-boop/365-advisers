"use client";

import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine,
    CartesianGrid,
    Legend,
} from "recharts";
import { useEffect, useState } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ScoreRecord {
    recorded_at: string;
    score: number;
    signal: string;
}

interface ScoreHistoryData {
    fundamental: ScoreRecord[];
    technical: ScoreRecord[];
}

interface ScoreHistoryChartProps {
    ticker: string;
}

// ─── Custom Tooltip ───────────────────────────────────────────────────────────

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: { dataKey: string; color: string; value: number; payload: Record<string, string> }[]; label?: string }) {
    if (!active || !payload?.length) return null;
    return (
        <div className="glass-card p-3 border border-[#30363d] text-[10px]">
            <p className="text-gray-500 mb-2 font-mono">{label ? new Date(label).toLocaleDateString() : ""}</p>
            {payload.map((p) => (
                <div key={p.dataKey} className="flex items-center gap-2 mb-1">
                    <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
                    <span className="text-gray-400 capitalize">{p.dataKey}:</span>
                    <span className="font-black" style={{ color: p.color }}>{p.value?.toFixed(1)}/10</span>
                    {p.payload[`${p.dataKey}_signal`] && (
                        <span className="text-gray-600 uppercase text-[8px] font-bold">{p.payload[`${p.dataKey}_signal`]}</span>
                    )}
                </div>
            ))}
        </div>
    );
}

// ─── Signal dot ───────────────────────────────────────────────────────────────

function SignalDot(props: { cx?: number; cy?: number; payload?: Record<string, string>; dataKey?: string }) {
    const { cx, cy, payload, dataKey } = props;
    if (!cx || !cy || !payload || !dataKey) return null;
    const signal = payload[`${dataKey}_signal`] as string ?? "";
    let fill = "#6b7280";
    if (signal === "BUY" || signal === "STRONG_BUY") fill = "#4ade80";
    else if (signal === "SELL" || signal === "STRONG_SELL" || signal === "AVOID") fill = "#f87171";
    else if (signal === "HOLD" || signal === "NEUTRAL") fill = "#d4af37";
    return <circle cx={cx} cy={cy} r={3} fill={fill} stroke="none" />;
}

// ─── Main chart component ─────────────────────────────────────────────────────

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function ScoreHistoryChart({ ticker }: ScoreHistoryChartProps) {
    const [data, setData] = useState<ScoreHistoryData>({ fundamental: [], technical: [] });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!ticker) return;
        setLoading(true);

        const fetchBoth = async () => {
            try {
                const [fundRes, techRes] = await Promise.all([
                    fetch(`${BACKEND_URL}/score-history?ticker=${encodeURIComponent(ticker)}&type=fundamental&limit=30`),
                    fetch(`${BACKEND_URL}/score-history?ticker=${encodeURIComponent(ticker)}&type=technical&limit=30`),
                ]);
                const fund = fundRes.ok ? (await fundRes.json()).history as ScoreRecord[] : [];
                const tech = techRes.ok ? (await techRes.json()).history as ScoreRecord[] : [];
                setData({ fundamental: fund, technical: tech });
            } catch {
                setData({ fundamental: [], technical: [] });
            } finally {
                setLoading(false);
            }
        };
        fetchBoth();
    }, [ticker]);

    // Merge fundamental + technical into a unified time-series by date
    const merged = (() => {
        const map = new Map<string, any>();

        data.fundamental.forEach((r) => {
            const key = r.recorded_at;
            map.set(key, { ...map.get(key), date: key, fundamental: r.score, fundamental_signal: r.signal });
        });
        data.technical.forEach((r) => {
            const key = r.recorded_at;
            map.set(key, { ...map.get(key), date: key, technical: r.score, technical_signal: r.signal });
        });

        return Array.from(map.values()).sort(
            (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
        );
    })();

    const hasData = merged.length > 0;

    if (loading) {
        return (
            <div className="glass-card p-5 border-[#30363d]">
                <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-4">Score History</p>
                <div className="h-40 flex items-center justify-center">
                    <div className="w-8 h-8 border-2 border-[#d4af37]/20 border-t-[#d4af37] rounded-full animate-spin" />
                </div>
            </div>
        );
    }

    if (!hasData) {
        return (
            <div className="glass-card p-5 border-[#30363d]">
                <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-4">Score History</p>
                <div className="h-32 flex items-center justify-center">
                    <p className="text-gray-700 text-xs">Run more analyses to build history.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="glass-card p-5 border-[#30363d]" style={{ animation: "fadeSlideIn 0.4s ease both" }}>
            <div className="flex items-center justify-between mb-4">
                <p className="text-[9px] font-black uppercase tracking-widest text-gray-500">Score History — {ticker}</p>
                <div className="flex gap-3 text-[8px] font-bold">
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#d4af37] inline-block" />Fundamental</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#60a5fa] inline-block" />Technical</span>
                </div>
            </div>
            <ResponsiveContainer width="100%" height={180}>
                <LineChart data={merged} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262d" vertical={false} />
                    <XAxis
                        dataKey="date"
                        tick={{ fill: "#4b5563", fontSize: 8 }}
                        tickFormatter={(d) => new Date(d).toLocaleDateString("en", { month: "short", day: "numeric" })}
                        axisLine={false}
                        tickLine={false}
                    />
                    <YAxis
                        domain={[0, 10]}
                        ticks={[0, 2, 4, 6, 8, 10]}
                        tick={{ fill: "#4b5563", fontSize: 8 }}
                        axisLine={false}
                        tickLine={false}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <ReferenceLine y={5} stroke="#30363d" strokeDasharray="4 4" />
                    <Line
                        type="monotone"
                        dataKey="fundamental"
                        stroke="#d4af37"
                        strokeWidth={2}
                        dot={(props) => <SignalDot {...props} dataKey="fundamental" />}
                        activeDot={{ r: 5, fill: "#d4af37" }}
                        connectNulls
                    />
                    <Line
                        type="monotone"
                        dataKey="technical"
                        stroke="#60a5fa"
                        strokeWidth={2}
                        dot={(props) => <SignalDot {...props} dataKey="technical" />}
                        activeDot={{ r: 5, fill: "#60a5fa" }}
                        connectNulls
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
