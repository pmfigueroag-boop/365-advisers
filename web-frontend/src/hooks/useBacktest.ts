"use client";

/**
 * useBacktest.ts
 * ──────────────────────────────────────────────────────────────────────────
 * Hook for running signal backtests via the Backtest API.
 *
 * Matches the backend BacktestStartRequest:
 *   universe:      list[str]  (required, min 1)
 *   start_date:    str        (required, YYYY-MM-DD)
 *   end_date:      str | None (optional)
 *   signal_ids:    list[str] | None
 *   forward_windows: list[int]  (default [1,5,10,20,60])
 *   min_observations: int       (default 30)
 *   benchmark_ticker: str       (default "SPY")
 */

import { useState, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface BacktestRunResponse {
    run_id: string;
    status: string;
    message: string;
}

export interface BacktestReport {
    run_id: string;
    status: string;
    universe: string[];
    signal_results: BacktestSignalResult[];
    execution_time_seconds: number;
    calibration_suggestions: CalibrationSuggestion[];
}

export interface BacktestSignalResult {
    signal_id: string;
    ticker: string;
    total_firings: number;
    win_rate: number;
    avg_return: number;
    max_return: number;
    min_return: number;
    sharpe_ratio: number;
    profit_factor: number;
}

export interface CalibrationSuggestion {
    signal_id: string;
    parameter: string;
    current_value: number;
    suggested_value: number;
    evidence: string;
}

// Keep old types for backward compat with BacktestEvidenceTab
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
    runResponse: BacktestRunResponse | null;
    report: BacktestReport | null;
    results: BacktestResult[];
    status: "idle" | "running" | "done" | "error";
    error: string | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function periodToStartDate(period: string): string {
    const now = new Date();
    const map: Record<string, number> = {
        "3m": 90,
        "6m": 180,
        "1y": 365,
        "2y": 730,
    };
    const days = map[period] ?? 365;
    now.setDate(now.getDate() - days);
    return now.toISOString().split("T")[0];
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useBacktest() {
    const [state, setState] = useState<BacktestState>({
        runResponse: null,
        report: null,
        results: [],
        status: "idle",
        error: null,
    });

    /** Start a backtest run for one or more tickers */
    const run = useCallback(async (
        ticker: string,
        opts?: { signalId?: string; period?: string }
    ) => {
        setState({ runResponse: null, report: null, results: [], status: "running", error: null });
        try {
            const startDate = periodToStartDate(opts?.period ?? "1y");

            // Step 1: Start the backtest
            const res = await fetch(`${API}/backtest/run`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    universe: [ticker.toUpperCase()],
                    start_date: startDate,
                    signal_ids: opts?.signalId ? [opts.signalId] : null,
                }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const runResp: BacktestRunResponse = await res.json();

            // Step 2: Fetch the report
            const reportRes = await fetch(`${API}/backtest/runs/${runResp.run_id}`, {
                method: "GET",
            });

            let report: BacktestReport | null = null;
            let results: BacktestResult[] = [];

            if (reportRes.ok) {
                report = await reportRes.json();
                // Map signal results → BacktestResult for the UI
                if (report?.signal_results) {
                    results = report.signal_results.map((sr) => ({
                        ticker: sr.ticker || ticker.toUpperCase(),
                        signal_id: sr.signal_id,
                        period: opts?.period ?? "1y",
                        total_signals: sr.total_firings,
                        win_rate: sr.win_rate ?? 0,
                        avg_return: sr.avg_return ?? 0,
                        max_return: sr.max_return ?? 0,
                        min_return: sr.min_return ?? 0,
                        sharpe_ratio: sr.sharpe_ratio ?? 0,
                        profit_factor: sr.profit_factor ?? 0,
                        trades: [],
                    }));
                }
            }

            setState({
                runResponse: runResp,
                report,
                results,
                status: "done",
                error: null,
            });
        } catch (e) {
            setState({
                runResponse: null,
                report: null,
                results: [],
                status: "error",
                error: e instanceof Error ? e.message : String(e),
            });
        }
    }, []);

    return { ...state, run };
}
