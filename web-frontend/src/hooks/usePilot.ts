"use client";

import { useState, useEffect, useCallback, useRef } from "react";

const BACKEND_URL = "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

interface PilotPosition {
    ticker: string;
    weight: number;
    shares: number;
    entry_price: number;
    current_price: number;
    position_pnl: number;
    position_pnl_pct: number;
    bucket: string;
}

interface PilotPortfolioMetrics {
    portfolio_type: string;
    total_return: number;
    alpha_vs_benchmark: number;
    sharpe_ratio: number;
    annualized_volatility: number;
    max_sector_concentration: number;
}

interface PilotAlert {
    id: string;
    alert_type: string;
    severity: "info" | "warning" | "critical";
    title: string;
    message: string;
    current_value: number;
    threshold_value: number;
    auto_action: string;
    created_at: string;
}

interface PilotHealthStatus {
    pipeline_status: string;
    data_fresh: boolean;
    data_last_updated: string | null;
    uptime_pct: number;
    active_strategies_count: number;
    target_strategies_count: number;
    critical_alerts_count: number;
    warning_alerts_count: number;
    last_run_duration_seconds: number;
}

interface SignalLeaderboardEntry {
    rank: number;
    signal_name: string;
    category: string;
    hit_rate: number;
    avg_return: number;
    total_firings: number;
}

interface StrategyLeaderboardEntry {
    rank: number;
    strategy_name: string;
    category: string;
    sharpe_ratio: number;
    max_drawdown: number;
    quality_score: number;
    alpha: number;
}

interface EquityCurvePoint {
    date: string;
    nav: number;
    daily_return: number;
    cumulative_return: number;
}

interface PilotDashboard {
    pilot_status: {
        pilot_id: string;
        phase: string;
        current_week: number;
        total_weeks: number;
        is_active: boolean;
        total_trading_days: number;
        total_alerts_generated: number;
        total_signals_evaluated: number;
        last_daily_run: string | null;
    };
    equity_curves: Record<string, EquityCurvePoint[]>;
    positions: Record<string, PilotPosition[]>;
    portfolio_metrics: PilotPortfolioMetrics[];
    health: PilotHealthStatus;
    recent_alerts: PilotAlert[];
    signal_leaderboard: SignalLeaderboardEntry[];
    strategy_leaderboard: StrategyLeaderboardEntry[];
}

type PilotHookStatus = "idle" | "loading" | "ready" | "error" | "no_pilot";

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function usePilot() {
    const [dashboard, setDashboard] = useState<PilotDashboard | null>(null);
    const [status, setStatus] = useState<PilotHookStatus>("idle");
    const [error, setError] = useState<string | null>(null);
    const [pilotId, setPilotId] = useState<string | null>(null);
    const refreshTimer = useRef<NodeJS.Timeout | null>(null);

    // ── Fetch active pilot ────────────────────────────────────────────────
    const fetchActivePilot = useCallback(async () => {
        try {
            const res = await fetch(`${BACKEND_URL}/pilot/status`);
            if (!res.ok) {
                setStatus("no_pilot");
                return null;
            }
            const data = await res.json();
            if (data?.pilot_id) {
                setPilotId(data.pilot_id);
                return data.pilot_id;
            }
            setStatus("no_pilot");
            return null;
        } catch {
            setStatus("no_pilot");
            return null;
        }
    }, []);

    // ── Fetch full dashboard ──────────────────────────────────────────────
    const fetchDashboard = useCallback(async (id: string) => {
        try {
            setStatus("loading");
            const res = await fetch(`${BACKEND_URL}/pilot/dashboard/${id}`);
            if (!res.ok) throw new Error(`Dashboard fetch failed: ${res.status}`);
            const data: PilotDashboard = await res.json();
            setDashboard(data);
            setStatus("ready");
            setError(null);
        } catch (e: any) {
            setError(e.message);
            setStatus("error");
        }
    }, []);

    // ── Initialize a new pilot ────────────────────────────────────────────
    const initializePilot = useCallback(async () => {
        try {
            setStatus("loading");
            const res = await fetch(`${BACKEND_URL}/pilot/initialize`, { method: "POST", headers: { "Content-Type": "application/json" } });
            if (!res.ok) throw new Error(`Init failed: ${res.status}`);
            const data = await res.json();
            setPilotId(data.pilot_id);
            await fetchDashboard(data.pilot_id);
            return data.pilot_id;
        } catch (e: any) {
            setError(e.message);
            setStatus("error");
            return null;
        }
    }, [fetchDashboard]);

    // ── Run a daily cycle manually ────────────────────────────────────────
    const runDailyCycle = useCallback(async () => {
        if (!pilotId) return;
        try {
            setStatus("loading");
            const res = await fetch(`${BACKEND_URL}/pilot/run-daily/${pilotId}`, { method: "POST" });
            if (!res.ok) throw new Error(`Cycle failed: ${res.status}`);
            await fetchDashboard(pilotId);
        } catch (e: any) {
            setError(e.message);
            setStatus("error");
        }
    }, [pilotId, fetchDashboard]);

    // ── Advance phase ─────────────────────────────────────────────────────
    const advancePhase = useCallback(async () => {
        if (!pilotId) return;
        try {
            const res = await fetch(`${BACKEND_URL}/pilot/advance-phase/${pilotId}`, { method: "POST" });
            if (!res.ok) throw new Error(`Advance failed: ${res.status}`);
            await fetchDashboard(pilotId);
        } catch (e: any) {
            setError(e.message);
        }
    }, [pilotId, fetchDashboard]);

    // ── Auto-refresh every 60s ────────────────────────────────────────────
    useEffect(() => {
        const init = async () => {
            const id = await fetchActivePilot();
            if (id) await fetchDashboard(id);
        };
        init();

        refreshTimer.current = setInterval(() => {
            if (pilotId) fetchDashboard(pilotId);
        }, 60_000);

        return () => {
            if (refreshTimer.current) clearInterval(refreshTimer.current);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return {
        dashboard,
        status,
        error,
        pilotId,
        initializePilot,
        runDailyCycle,
        advancePhase,
        refresh: () => pilotId ? fetchDashboard(pilotId) : fetchActivePilot(),
    };
}
