"use client";

import { useState, useCallback, useRef } from "react";
import type { FundamentalDataReady, AgentMemo, CommitteeVerdict } from "./useFundamentalStream";
import type { TechnicalAnalysisResult } from "./useTechnicalAnalysis";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CIOMemo {
    thesis_summary: string;
    valuation_view: string;
    technical_context: string;
    key_catalysts: string[];
    key_risks: string[];
}

export interface DecisionReady {
    investment_position: string;
    confidence_score: number;
    cio_memo: CIOMemo;
    elapsed_ms?: number;
}

export type CombinedStatus = "idle" | "fetching_data" | "fundamental" | "technical" | "decision" | "complete" | "error";

export interface CombinedState {
    status: CombinedStatus;
    ticker: string | null;
    // Fundamental track
    fundamentalDataReady: FundamentalDataReady | null;
    agentMemos: AgentMemo[];
    committee: CommitteeVerdict | null;
    researchMemo: string | null;
    // Technical track
    technical: TechnicalAnalysisResult | null;
    // Decision track
    decision: DecisionReady | null;
    // Meta
    error: string | null;
    fromCache: boolean;
    processingMs: number | null;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const INITIAL: CombinedState = {
    status: "idle",
    ticker: null,
    fundamentalDataReady: null,
    agentMemos: [],
    committee: null,
    researchMemo: null,
    technical: null,
    decision: null,
    error: null,
    fromCache: false,
    processingMs: null,
};

export function useCombinedStream() {
    const [state, setState] = useState<CombinedState>(INITIAL);
    const esRef = useRef<EventSource | null>(null);
    const startRef = useRef<number>(0);

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
        startRef.current = Date.now();
        setState({ ...INITIAL, status: "fetching_data", ticker: symbol });

        const url = `${BACKEND_URL}/analysis/combined/stream?ticker=${encodeURIComponent(symbol)}${force ? "&force=true" : ""}`;
        const es = new EventSource(url);
        esRef.current = es;

        // data_ready — fundamental ratios phase starts
        es.addEventListener("data_ready", (e) => {
            const data: FundamentalDataReady = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, status: "fundamental", fundamentalDataReady: data }));
        });

        // agent_memo — one per analyst
        es.addEventListener("agent_memo", (e) => {
            const memo: AgentMemo = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, agentMemos: [...prev.agentMemos, memo] }));
        });

        // committee_verdict
        es.addEventListener("committee_verdict", (e) => {
            const verdict: CommitteeVerdict = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, committee: verdict, status: "technical" }));
        });

        // research_memo
        es.addEventListener("research_memo", (e) => {
            const { memo } = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, researchMemo: memo }));
        });

        // technical_ready — full TechnicalSummary JSON
        es.addEventListener("technical_ready", (e) => {
            const tech: TechnicalAnalysisResult = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, technical: tech, status: "decision" }));
        });

        // decision_ready — Final CIO Memo and Investment Position
        es.addEventListener("decision_ready", (e) => {
            const dec: DecisionReady = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, decision: dec }));
        });

        // done
        es.addEventListener("done", (e) => {
            const d = JSON.parse((e as MessageEvent).data ?? "{}");
            setState((prev) => ({
                ...prev,
                status: "complete",
                fromCache: d.from_cache ?? false,
                processingMs: Date.now() - startRef.current,
            }));
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

    const forceRefresh = useCallback((ticker: string) => analyze(ticker, true), [analyze]);
    const reset = useCallback(() => { _close(); setState(INITIAL); }, []);

    return { state, analyze, forceRefresh, reset };
}
