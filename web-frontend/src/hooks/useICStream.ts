"use client";

/**
 * useICStream.ts
 * ──────────────────────────────────────────────────────────────────────────
 * SSE hook for the Investment Committee simulation.
 *
 * Connects to /api/investment-committee/{ticker}/stream and accumulates
 * the 5-round debate events into a single ICState object.
 */

import { useState, useCallback, useRef } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ICMember {
    name: string;
    role: string;
    framework: string;
    bias: string;
}

export interface PositionMemo {
    agent: string;
    signal: string;
    conviction: number;
    thesis: string;
    key_metrics: string[];
    catalysts: string[];
    risks: string[];
}

export interface Challenge {
    challenger: string;
    target: string;
    objection: string;
    evidence: string[];
    severity: string;
}

export interface Rebuttal {
    agent: string;
    challenger: string;
    defense: string;
    concession: string;
    conviction_adjustment: number;
}

export interface Vote {
    agent: string;
    signal: string;
    conviction: number;
    rationale: string;
    dissents: boolean;
    conviction_drift: number;
}

export interface ICVerdict {
    signal: string;
    score: number;
    confidence: number;
    consensus_strength: string;
    narrative: string;
    key_catalysts: string[];
    key_risks: string[];
    dissenting_opinions: string[];
    conviction_drift_summary: string;
    vote_breakdown: Record<string, number>;
}

export type ICStatus = "idle" | "connecting" | "presenting" | "challenging" | "rebutting" | "voting" | "synthesizing" | "complete" | "error";

export interface ICState {
    status: ICStatus;
    ticker: string | null;
    members: ICMember[];
    memos: PositionMemo[];
    challenges: Challenge[];
    rebuttals: Rebuttal[];
    votes: Vote[];
    verdict: ICVerdict | null;
    error: string | null;
    elapsedMs: number;
}

const INITIAL_STATE: ICState = {
    status: "idle",
    ticker: null,
    members: [],
    memos: [],
    challenges: [],
    rebuttals: [],
    votes: [],
    verdict: null,
    error: null,
    elapsedMs: 0,
};

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useICStream() {
    const [state, setState] = useState<ICState>(INITIAL_STATE);
    const esRef = useRef<EventSource | null>(null);

    const _close = () => {
        if (esRef.current) {
            esRef.current.close();
            esRef.current = null;
        }
    };

    const runIC = useCallback((ticker: string) => {
        const symbol = ticker.trim().toUpperCase();
        if (!symbol) return;

        _close();
        setState({ ...INITIAL_STATE, status: "connecting", ticker: symbol });

        const url = `${BACKEND_URL}/api/investment-committee/${encodeURIComponent(symbol)}/stream`;
        const es = new EventSource(url);
        esRef.current = es;

        // Members list
        es.addEventListener("ic_members", (e) => {
            const data = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({
                ...prev,
                status: "presenting",
                members: data.members ?? [],
            }));
        });

        // Round 1: Present
        es.addEventListener("ic_round_present", (e) => {
            const memo: PositionMemo = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({
                ...prev,
                status: "presenting",
                memos: [...prev.memos, memo],
            }));
        });

        // Round 2: Challenge
        es.addEventListener("ic_round_challenge", (e) => {
            const ch: Challenge = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({
                ...prev,
                status: "challenging",
                challenges: [...prev.challenges, ch],
            }));
        });

        // Round 3: Rebuttal
        es.addEventListener("ic_round_rebuttal", (e) => {
            const reb: Rebuttal = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({
                ...prev,
                status: "rebutting",
                rebuttals: [...prev.rebuttals, reb],
            }));
        });

        // Round 4: Vote
        es.addEventListener("ic_round_vote", (e) => {
            const vote: Vote = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({
                ...prev,
                status: "voting",
                votes: [...prev.votes, vote],
            }));
        });

        // Round 5: Verdict
        es.addEventListener("ic_verdict", (e) => {
            const verdict: ICVerdict = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({
                ...prev,
                status: "synthesizing",
                verdict,
            }));
        });

        // Done
        es.addEventListener("ic_done", (e) => {
            const data = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({
                ...prev,
                status: "complete",
                elapsedMs: data.elapsed_ms ?? 0,
            }));
            _close();
        });

        // Error
        es.addEventListener("error", (e) => {
            const msg =
                "data" in e
                    ? JSON.parse((e as MessageEvent).data)?.message ?? "IC stream error"
                    : "Connection error";
            setState((prev) => ({ ...prev, status: "error", error: msg }));
            _close();
        });

        es.onerror = () => {
            if (esRef.current) {
                setState((prev) =>
                    prev.status !== "complete" && prev.status !== "error"
                        ? { ...prev, status: "error", error: "Connection lost" }
                        : prev
                );
                _close();
            }
        };
    }, []);

    const reset = useCallback(() => {
        _close();
        setState(INITIAL_STATE);
    }, []);

    return { state, runIC, reset };
}
