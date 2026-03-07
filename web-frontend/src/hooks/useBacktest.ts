"use client";

/**
 * useBacktest.ts
 * ──────────────────────────────────────────────────────────────────────────
 * Hook for running signal backtests via the Backtest API.
 */

import { useState, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface BacktestResult {
    ticker: string;
    signal_id: string;
    period: string;
    total_signals: number;
    win_rate: number;
    avg_return: number;
    max_return: number;
    min_return: number;
    sharpe_ratio: number;
    profit_factor: number;
    trades: BacktestTrade[];
}

export interface BacktestTrade {
    entry_date: string;
    exit_date: string;
    entry_price: number;
    exit_price: number;
    return_pct: number;
    signal_strength: string;
    holding_days: number;
}

export interface BacktestState {
    results: BacktestResult[];
    status: "idle" | "running" | "done" | "error";
    error: string | null;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useBacktest() {
    const [state, setState] = useState<BacktestState>({
        results: [],
        status: "idle",
        error: null,
    });

    /** Run a backtest for a ticker and optional signal */
    const run = useCallback(async (ticker: string, opts?: { signalId?: string; period?: string; lookback?: number }) => {
        setState({ results: [], status: "running", error: null });
        try {
            const res = await fetch(`${API}/backtest/run`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ticker: ticker.toUpperCase(),
                    signal_id: opts?.signalId,
                    period: opts?.period ?? "1y",
                    lookback: opts?.lookback ?? 252,
                }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const results: BacktestResult[] = Array.isArray(data) ? data : data.results ? data.results : [data];
            setState({ results, status: "done", error: null });
        } catch (e) {
            setState({ results: [], status: "error", error: e instanceof Error ? e.message : String(e) });
        }
    }, []);

    return { ...state, run };
}
