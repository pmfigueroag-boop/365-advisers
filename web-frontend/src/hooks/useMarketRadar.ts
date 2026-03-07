"use client";

/**
 * useMarketRadar.ts
 * ──────────────────────────────────────────────────────────────────────────
 * Hook for fetching market-wide radar data: global ranking, sector rankings,
 * and top opportunities from the Ranking Engine API.
 */

import { useState, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface RankedItem {
    ticker: string;
    name: string;
    sector: string;
    idea_type: string;
    composite_score: number;
    case_score: number;
    opp_score: number;
    signal_strength: number;
    suggested_allocation: number;
    rank: number;
    tier: string;
}

export interface SectorRanking {
    sector: string;
    ranking: RankedItem[];
    count: number;
    avgScore: number;
}

export interface MarketRadarState {
    globalRanking: RankedItem[];
    topOpportunities: RankedItem[];
    sectorRankings: Record<string, RankedItem[]>;
    sectors: string[];
    strategies: string[];
    universeSize: number;
    computedAt: string | null;
    status: "idle" | "loading" | "done" | "error";
    error: string | null;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useMarketRadar() {
    const [state, setState] = useState<MarketRadarState>({
        globalRanking: [],
        topOpportunities: [],
        sectorRankings: {},
        sectors: [],
        strategies: [],
        universeSize: 0,
        computedAt: null,
        status: "idle",
        error: null,
    });

    /** Fetch the latest global ranking */
    const fetchGlobalRanking = useCallback(async () => {
        setState((s) => ({ ...s, status: "loading", error: null }));
        try {
            const res = await fetch(`${API}/ranking/global`);
            if (!res.ok) {
                if (res.status === 404) {
                    setState((s) => ({ ...s, status: "done", globalRanking: [] }));
                    return;
                }
                throw new Error(`HTTP ${res.status}`);
            }
            const data = await res.json();
            setState((s) => ({
                ...s,
                globalRanking: data.ranking ?? [],
                universeSize: data.universe_size ?? 0,
                computedAt: data.computed_at ?? null,
                status: "done",
            }));
        } catch (e) {
            setState((s) => ({ ...s, status: "error", error: e instanceof Error ? e.message : String(e) }));
        }
    }, []);

    /** Fetch top N opportunities */
    const fetchTopOpportunities = useCallback(async () => {
        try {
            const res = await fetch(`${API}/ranking/top`);
            if (!res.ok) return;
            const data = await res.json();
            setState((s) => ({ ...s, topOpportunities: data.top ?? [] }));
        } catch {
            // Silent — non-critical
        }
    }, []);

    /** Fetch ranking for a specific sector */
    const fetchSectorRanking = useCallback(async (sector: string) => {
        try {
            const res = await fetch(`${API}/ranking/sector/${encodeURIComponent(sector)}`);
            if (!res.ok) return;
            const data = await res.json();
            setState((s) => ({
                ...s,
                sectorRankings: { ...s.sectorRankings, [sector]: data.ranking ?? [] },
            }));
        } catch {
            // Silent
        }
    }, []);

    /** Compute a new ranking from ideas + scores */
    const computeRanking = useCallback(async (ideas: Record<string, unknown>[], caseScores: Record<string, number>, oppScores: Record<string, number>) => {
        setState((s) => ({ ...s, status: "loading", error: null }));
        try {
            const res = await fetch(`${API}/ranking/compute`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ideas, case_scores: caseScores, opp_scores: oppScores }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setState({
                globalRanking: data.global_ranking ?? [],
                topOpportunities: data.top_n ?? [],
                sectorRankings: {},
                sectors: data.sectors ?? [],
                strategies: data.strategies ?? [],
                universeSize: data.universe_size ?? 0,
                computedAt: data.computed_at ?? null,
                status: "done",
                error: null,
            });
        } catch (e) {
            setState((s) => ({ ...s, status: "error", error: e instanceof Error ? e.message : String(e) }));
        }
    }, []);

    /** Refresh all data */
    const refreshAll = useCallback(async () => {
        await Promise.all([fetchGlobalRanking(), fetchTopOpportunities()]);
    }, [fetchGlobalRanking, fetchTopOpportunities]);

    return {
        ...state,
        fetchGlobalRanking,
        fetchTopOpportunities,
        fetchSectorRanking,
        computeRanking,
        refreshAll,
    };
}
