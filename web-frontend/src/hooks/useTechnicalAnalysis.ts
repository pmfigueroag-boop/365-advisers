"use client";

import { useState, useCallback } from "react";

// ─── Types matching GET /analysis/technical schema ────────────────────────────

export interface TechnicalIndicators {
    trend: {
        sma_50: number;
        sma_200: number;
        ema_20: number;
        macd: { value: number; signal: number; histogram: number };
        price_vs_sma50: "ABOVE" | "BELOW" | "AT";
        price_vs_sma200: "ABOVE" | "BELOW" | "AT";
        macd_crossover: "BULLISH" | "BEARISH" | "NEUTRAL";
        golden_cross: boolean;
        death_cross: boolean;
    };
    momentum: {
        rsi: number;
        rsi_zone: "OVERBOUGHT" | "NEUTRAL" | "OVERSOLD";
        stochastic_k: number;
        stochastic_d: number;
        stochastic_zone: "OVERBOUGHT" | "NEUTRAL" | "OVERSOLD";
    };
    volatility: {
        bb_upper: number;
        bb_lower: number;
        bb_basis: number;
        bb_width: number;
        bb_position: "UPPER" | "UPPER_MID" | "MID" | "LOWER_MID" | "LOWER";
        atr: number;
        atr_pct: number;
    };
    volume: {
        obv: number;
        obv_trend: "RISING" | "FLAT" | "FALLING";
        current_volume: number;
        volume_vs_avg_20: number;
    };
    structure: {
        resistance_levels: number[];
        support_levels: number[];
        nearest_resistance: number | null;
        nearest_support: number | null;
        distance_to_resistance_pct: number | null;
        distance_to_support_pct: number | null;
        breakout_probability: number;
        breakout_direction: "BULLISH" | "BEARISH" | "NEUTRAL";
    };
}

export interface TechnicalSummary {
    trend_status: string;
    momentum_status: string;
    volatility_condition: string;
    volume_strength: string;
    breakout_probability: string;
    breakout_direction: string;
    signal: "STRONG_BUY" | "BUY" | "NEUTRAL" | "SELL" | "STRONG_SELL";
    signal_strength: "Strong" | "Moderate" | "Weak";
    technical_score: number;
    subscores: {
        trend: number;
        momentum: number;
        volatility: number;
        volume: number;
        structure: number;
    };
}

export interface TechnicalAnalysisResult {
    ticker: string;
    analysis_type: "technical";
    timestamp: string;
    interval: string;
    current_price: number | null;
    data_source: string;
    exchange: string;
    indicators: TechnicalIndicators;
    summary: TechnicalSummary;
    tv_recommendation: string;
    active_indicators: string[];
    processing_time_ms: number | null;
    from_cache: boolean;
}

// ─── State ────────────────────────────────────────────────────────────────────

export type TechnicalStatus = "idle" | "loading" | "done" | "error";

export interface TechnicalAnalysisState {
    status: TechnicalStatus;
    data: TechnicalAnalysisResult | null;
    error: string | null;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function useTechnicalAnalysis() {
    const [state, setState] = useState<TechnicalAnalysisState>({
        status: "idle",
        data: null,
        error: null,
    });

    const analyze = useCallback(async (ticker: string, force = false) => {
        const symbol = ticker.trim().toUpperCase();
        if (!symbol) return;

        setState({ status: "loading", data: null, error: null });

        try {
            const url = `${BACKEND_URL}/analysis/technical?ticker=${encodeURIComponent(symbol)}${force ? "&force=true" : ""}`;
            const res = await fetch(url);

            if (!res.ok) {
                const detail = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(detail?.detail ?? `HTTP ${res.status}`);
            }

            const data: TechnicalAnalysisResult = await res.json();
            setState({ status: "done", data, error: null });
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Unknown error";
            setState({ status: "error", data: null, error: message });
        }
    }, []);

    const forceRefresh = useCallback(
        async (ticker: string) => {
            // First invalidate the server-side cache, then re-run
            try {
                await fetch(
                    `${BACKEND_URL}/cache/technical/${encodeURIComponent(ticker.toUpperCase())}`,
                    { method: "DELETE" }
                );
            } catch {
                // ignore — still try to re-analyze
            }
            analyze(ticker, true);
        },
        [analyze]
    );

    const reset = useCallback(() => {
        setState({ status: "idle", data: null, error: null });
    }, []);

    return { state, analyze, forceRefresh, reset };
}
