"use client";

/**
 * useCrowding.ts
 * ──────────────────────────────────────────────────────────────────────────
 * Hook for Signal Crowding Detection API.
 * Assesses crowding risk per ticker and batch.
 */

import { useState, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CrowdingAssessment {
    ticker: string;
    crowding_score: number;
    risk_level: string;      // "low" | "moderate" | "high" | "extreme"
    components: {
        flow_crowding: number;
        institutional_herding: number;
        volatility_regime: number;
    };
    alerts: string[];
}

export interface CrowdingState {
    assessments: Record<string, CrowdingAssessment>;
    status: "idle" | "loading" | "done" | "error";
    error: string | null;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useCrowding() {
    const [state, setState] = useState<CrowdingState>({
        assessments: {},
        status: "idle",
        error: null,
    });

    /** Assess crowding for a single ticker */
    const assess = useCallback(async (ticker: string) => {
        setState((s) => ({ ...s, status: "loading", error: null }));
        try {
            const res = await fetch(`${API}/crowding/${encodeURIComponent(ticker.toUpperCase())}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data: CrowdingAssessment = await res.json();
            setState((s) => ({
                ...s,
                assessments: { ...s.assessments, [ticker.toUpperCase()]: data },
                status: "done",
            }));
        } catch (e) {
            setState((s) => ({ ...s, status: "error", error: e instanceof Error ? e.message : String(e) }));
        }
    }, []);

    /** Batch assessment for multiple tickers */
    const assessBatch = useCallback(async (tickers: string[]) => {
        if (tickers.length === 0) return;
        setState((s) => ({ ...s, status: "loading", error: null }));
        try {
            const res = await fetch(`${API}/crowding/batch`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tickers }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setState((s) => ({
                ...s,
                assessments: { ...s.assessments, ...(data.results ?? {}) },
                status: "done",
            }));
        } catch (e) {
            setState((s) => ({ ...s, status: "error", error: e instanceof Error ? e.message : String(e) }));
        }
    }, []);

    /** Get a single ticker's assessment from cache */
    const getAssessment = useCallback((ticker: string): CrowdingAssessment | null => {
        return state.assessments[ticker.toUpperCase()] ?? null;
    }, [state.assessments]);

    return {
        ...state,
        assess,
        assessBatch,
        getAssessment,
    };
}
