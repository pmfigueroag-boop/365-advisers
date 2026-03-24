/**
 * useTechnicalICStream.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * SSE hook for the Technical IC "War Room" debate stream.
 *
 * Consumes events from GET /api/technical-ic/{ticker}/stream:
 *   tic_members         → agent identities
 *   tic_round_assess    → Round 1 assessments (×6)
 *   tic_round_conflict  → Round 2 conflicts
 *   tic_round_timeframe → Round 3 timeframe reconciliations (×6)
 *   tic_round_vote      → Round 4 votes (×6)
 *   tic_verdict         → Round 5 Head Technician verdict
 *   tic_done            → session complete
 */

import { useState, useCallback, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ──────────────────────────────────────────────────────────────────

export interface TacticalMember {
    name: string;
    role: string;
    domain: string;
    framework: string;
    bias_description: string;
}

export interface TacticalAssessment {
    agent: string;
    domain: string;
    signal: "STRONG_BULLISH" | "BULLISH" | "NEUTRAL" | "BEARISH" | "STRONG_BEARISH";
    conviction: number;
    thesis: string;
    supporting_data: string[];
    theoretical_framework: string;
    cross_module_note: string;
}

export interface TacticalConflict {
    challenger: string;
    target: string;
    disagreement: string;
    challenger_evidence: string[];
    theoretical_basis: string;
    severity: "HIGH" | "MEDIUM" | "LOW";
}

export interface TimeframeAssessment {
    agent: string;
    timeframe_alignment: "ALIGNED" | "DIVERGENT" | "PARTIAL";
    dominant_timeframe: string;
    timeframe_readings: Record<string, string>;
    conviction_adjustment: number;
    defense: string;
}

export interface TacticalVote {
    agent: string;
    signal: "STRONG_BULLISH" | "BULLISH" | "NEUTRAL" | "BEARISH" | "STRONG_BEARISH";
    conviction: number;
    conviction_drift: number;
    rationale: string;
    regime_weight: number;
    dissents: boolean;
}

export interface ActionPlan {
    entry_zone: string;
    stop_loss: string;
    take_profit_1: string;
    take_profit_2: string;
    invalidation: string;
    risk_reward: string;
    position_size_note: string;
}

export interface TechnicalICVerdict {
    signal: string;
    score: number;
    confidence: number;
    consensus_strength: string;
    narrative: string;
    action_plan: ActionPlan;
    key_levels: string;
    timing: string;
    risk_factors: string[];
    vote_breakdown: Record<string, number>;
    dissenting_opinions: string[];
}

// ─── State ──────────────────────────────────────────────────────────────────

export interface TechnicalICState {
    status: "idle" | "running" | "done" | "error";
    members: TacticalMember[];
    assessments: TacticalAssessment[];
    conflicts: TacticalConflict[];
    timeframes: TimeframeAssessment[];
    votes: TacticalVote[];
    verdict: TechnicalICVerdict | null;
    elapsed_ms: number;
    error: string | null;
}

const INITIAL_STATE: TechnicalICState = {
    status: "idle",
    members: [],
    assessments: [],
    conflicts: [],
    timeframes: [],
    votes: [],
    verdict: null,
    elapsed_ms: 0,
    error: null,
};

// ─── Hook ───────────────────────────────────────────────────────────────────

export function useTechnicalICStream(ticker: string | null) {
    const [state, setState] = useState<TechnicalICState>(INITIAL_STATE);
    const esRef = useRef<EventSource | null>(null);

    const run = useCallback(() => {
        if (!ticker) return;
        // Reset state
        setState({ ...INITIAL_STATE, status: "running" });

        // Close any existing connection
        if (esRef.current) {
            esRef.current.close();
        }

        const url = `${API}/api/technical-ic/${encodeURIComponent(ticker)}/stream`;
        const es = new EventSource(url);
        esRef.current = es;

        es.addEventListener("tic_members", (e) => {
            const data = JSON.parse(e.data);
            setState((s) => ({ ...s, members: data.members || [] }));
        });

        es.addEventListener("tic_round_assess", (e) => {
            const data = JSON.parse(e.data);
            setState((s) => ({
                ...s,
                assessments: [...s.assessments, data as TacticalAssessment],
            }));
        });

        es.addEventListener("tic_round_conflict", (e) => {
            const data = JSON.parse(e.data);
            setState((s) => ({
                ...s,
                conflicts: [...s.conflicts, data as TacticalConflict],
            }));
        });

        es.addEventListener("tic_round_timeframe", (e) => {
            const data = JSON.parse(e.data);
            setState((s) => ({
                ...s,
                timeframes: [...s.timeframes, data as TimeframeAssessment],
            }));
        });

        es.addEventListener("tic_round_vote", (e) => {
            const data = JSON.parse(e.data);
            setState((s) => ({
                ...s,
                votes: [...s.votes, data as TacticalVote],
            }));
        });

        es.addEventListener("tic_verdict", (e) => {
            const data = JSON.parse(e.data);
            setState((s) => ({ ...s, verdict: data as TechnicalICVerdict }));
        });

        es.addEventListener("tic_done", (e) => {
            const data = JSON.parse(e.data);
            setState((s) => ({
                ...s,
                status: "done",
                elapsed_ms: data.elapsed_ms || 0,
            }));
            es.close();
        });

        es.addEventListener("error", (e) => {
            try {
                const data = JSON.parse((e as MessageEvent).data);
                setState((s) => ({
                    ...s,
                    status: "error",
                    error: data.message || "Connection error",
                }));
            } catch {
                setState((s) => ({
                    ...s,
                    status: "error",
                    error: "Connection lost",
                }));
            }
            es.close();
        });

        es.onerror = () => {
            if (es.readyState === EventSource.CLOSED) return;
            setState((s) => {
                if (s.status === "done") return s;
                return { ...s, status: "error", error: "SSE connection error" };
            });
            es.close();
        };
    }, [ticker]);

    const reset = useCallback(() => {
        if (esRef.current) {
            esRef.current.close();
            esRef.current = null;
        }
        setState(INITIAL_STATE);
    }, []);

    return { state, run, reset };
}
