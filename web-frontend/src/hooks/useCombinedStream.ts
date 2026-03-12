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
    // Optional enrichment sections
    filing_context?: string;
    geopolitical_context?: string;
    macro_environment?: string;
    sentiment_context?: string;
}

export interface SourceCoverage {
    sources: Record<string, string>;
    analysis_completeness: number;
    completeness_label: string;
    freshness_scores: Record<string, string>;
    messages: string[];
    unavailable: string[];
    partial: string[];
}

export interface DecisionReady {
    investment_position: string;
    confidence_score: number;
    cio_memo: CIOMemo;
    elapsed_ms?: number;
    source_coverage?: SourceCoverage;
}

export interface SpecialtyOpinion {
    signal: string;
    conviction: string;
    narrative: string;
    key_data: string[];
}

export interface TechnicalMemo {
    trend: SpecialtyOpinion;
    momentum: SpecialtyOpinion;
    volatility: SpecialtyOpinion;
    volume: SpecialtyOpinion;
    structure: SpecialtyOpinion;
    consensus: string;
    consensus_signal: string;
    consensus_conviction: string;
    tradingview_comparison: string;
    key_levels: string;
    timing: string;
    risk_factors: string[];
}

export interface OpportunityScore {
    opportunity_score: number;
    dimensions: Record<string, number>;
    factors: Record<string, number>;
}

export interface PositionSizing {
    opportunity_score: number;
    conviction_level: string;
    risk_level: string;
    base_position_size: number;
    risk_adjustment: number;
    suggested_allocation: number;
    recommended_action: string;
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
    technicalMemo: TechnicalMemo | null;
    // Coverage track
    sourceCoverage: SourceCoverage | null;
    // Portfolio track
    opportunity: OpportunityScore | null;
    positionSizing: PositionSizing | null;
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
    technicalMemo: null,
    sourceCoverage: null,
    opportunity: null,
    positionSizing: null,
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

        // Timeout: if no data_ready arrives within 30s, abort with an error
        const timeoutId = setTimeout(() => {
            setState((prev) => {
                if (prev.status === "fetching_data") {
                    _close();
                    return { ...prev, status: "error", error: `Could not fetch data for ${symbol}. Please verify the ticker and try again.` };
                }
                return prev;
            });
        }, 30_000);

        // data_ready — fundamental ratios phase starts
        es.addEventListener("data_ready", (e) => {
            clearTimeout(timeoutId);
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

        // technical_memo — LLM interpretive technical analysis
        es.addEventListener("technical_memo", (e) => {
            const memo: TechnicalMemo = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, technicalMemo: memo }));
        });

        // source_coverage — EDPL coverage report
        es.addEventListener("source_coverage", (e) => {
            const cov: SourceCoverage = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, sourceCoverage: cov }));
        });

        // opportunity_score
        es.addEventListener("opportunity_score", (e) => {
            const opp: OpportunityScore = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, opportunity: opp }));
        });

        // position_sizing
        es.addEventListener("position_sizing", (e) => {
            const pos: PositionSizing = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, positionSizing: pos }));
        });

        // decision_ready — Final CIO Memo and Investment Position
        es.addEventListener("decision_ready", (e) => {
            const dec: DecisionReady = JSON.parse((e as MessageEvent).data);
            setState((prev) => ({ ...prev, decision: dec }));
        });

        // done
        es.addEventListener("done", (e) => {
            clearTimeout(timeoutId);
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
            clearTimeout(timeoutId);
            const msg =
                "data" in e
                    ? JSON.parse((e as MessageEvent).data)?.message ?? "Stream error"
                    : "Connection error";
            setState((prev) => ({ ...prev, status: "error", error: msg }));
            _close();
        });

        es.onerror = () => {
            clearTimeout(timeoutId);
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
