"use client";

import { useState, useCallback, useRef } from "react";

// ─── Event + State types ─────────────────────────────────────────────────────

export interface FundamentalDataReady {
    ticker: string;
    name: string;
    sector: string;
    industry: string;
    ratios: {
        profitability?: Record<string, number | string>;
        valuation?: Record<string, number | string>;
        leverage?: Record<string, number | string>;
        quality?: Record<string, number | string>;
    };
    cashflow_series: { year: string; fcf: number; revenue: number | null }[];
}

export interface AgentMemo {
    agent: string;
    framework: string;
    signal: "BUY" | "SELL" | "HOLD" | "AVOID";
    conviction: number;
    memo: string;
    key_metrics_used: string[];
    metric_insights?: { metric: string; definition: string; interpretation: string }[];
    catalysts: string[];
    risks: string[];
}

export interface CommitteeVerdict {
    signal: "BUY" | "SELL" | "HOLD";
    score: number;
    confidence: number;
    risk_adjusted_score: number;
    consensus_narrative: string;
    key_catalysts: string[];
    key_risks: string[];
    allocation_recommendation: string;
    elapsed_ms?: number;
}

export type FundamentalStatus =
    | "idle"
    | "fetching_data"
    | "analyzing"
    | "complete"
    | "error";

export interface FundamentalState {
    status: FundamentalStatus;
    ticker: string | null;
    dataReady: FundamentalDataReady | null;
    agentMemos: AgentMemo[];
    committee: CommitteeVerdict | null;
    researchMemo: string | null;
    error: string | null;
    fromCache: boolean;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const INITIAL_STATE: FundamentalState = {
    status: "idle",
    ticker: null,
    dataReady: null,
    agentMemos: [],
    committee: null,
    researchMemo: null,
    error: null,
    fromCache: false,
};

export function useFundamentalStream() {
    const [state, setState] = useState<FundamentalState>(INITIAL_STATE);
    const esRef = useRef<EventSource | null>(null);

    const _close = () => {
        if (esRef.current) {
            esRef.current.close();
            esRef.current = null;
        }
    };

    const analyze = useCallback((ticker: string, force = false) => {
        const symbol = ticker.trim().toUpperCase();
        if (!symbol) return;

        _close();
        setState({ ...INITIAL_STATE, status: "fetching_data", ticker: symbol });

        const url = `${BACKEND_URL}/analysis/fundamental/stream?ticker=${encodeURIComponent(symbol)}${force ? "&force=true" : ""}`;
        const es = new EventSource(url);
        esRef.current = es;

        // data_ready — fundamental ratios loaded
        es.addEventListener("data_ready", (e) => {
            const data: FundamentalDataReady = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({
                ...prev,
                status: "analyzing",
                dataReady: data,
            }));
        });

        // agent_memo — one per analyst
        es.addEventListener("agent_memo", (e) => {
            const memo: AgentMemo = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({
                ...prev,
                agentMemos: [...prev.agentMemos, memo],
            }));
        });

        // committee_verdict — final score + narrative
        es.addEventListener("committee_verdict", (e) => {
            const verdict: CommitteeVerdict = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, committee: verdict }));
        });

        // research_memo — full 1-pager markdown
        es.addEventListener("research_memo", (e) => {
            const { memo } = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, researchMemo: memo }));
        });

        // done
        es.addEventListener("done", () => {
            setState((prev) => ({ ...prev, status: "complete" }));
            _close();
        });

        // error
        es.addEventListener("error", (e) => {
            const msg =
                "data" in e
                    ? JSON.parse((e as MessageEvent).data)?.message ?? "Stream error"
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

    const forceRefresh = useCallback(
        (ticker: string) => analyze(ticker, true),
        [analyze]
    );

    const reset = useCallback(() => {
        _close();
        setState(INITIAL_STATE);
    }, []);

    return { state, analyze, forceRefresh, reset };
}
