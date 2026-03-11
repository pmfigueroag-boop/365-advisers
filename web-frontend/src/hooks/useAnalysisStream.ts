"use client";

import { useState, useCallback, useRef } from "react";

export interface AgentSignal {
    agent_name: string;
    signal: string;
    confidence: number;
    analysis: string;
    key_metrics?: Record<string, unknown>;
    selected_metrics?: string[];
    discarded_metrics?: string[];
}

export interface DalioVerdict {
    final_verdict: string;
    dalio_response: {
        verdict?: string;
        risk_score?: number;
        allocation_rec?: string;
        summary_table?: string;
    };
}

export interface DataReadyPayload {
    ticker: string;
    name: string;
    tech_indicators: Record<string, unknown>;
    tradingview: Record<string, unknown>;
    fundamental_metrics: Record<string, unknown>;
    from_cache: boolean;
    cached_at: string | null;
}


export type StreamStatus =
    | "idle"
    | "fetching_data"
    | "analyzing"
    | "complete"
    | "error";

export interface AnalysisStreamState {
    status: StreamStatus;
    ticker: string;
    dataReady: DataReadyPayload | null;
    agents: AgentSignal[];
    dalio: DalioVerdict | null;
    error: string | null;
    agentCount: number;
    fromCache: boolean;
    cachedAt: string | null;
}


const TOTAL_AGENTS = 8;
const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function useAnalysisStream() {
    const [state, setState] = useState<AnalysisStreamState>({
        status: "idle",
        ticker: "",
        dataReady: null,
        agents: [],
        dalio: null,
        error: null,
        agentCount: 0,
        fromCache: false,
        cachedAt: null,
    });

    const esRef = useRef<EventSource | null>(null);
    const BACKEND_URL_LOCAL = BACKEND_URL;

    const analyze = useCallback((ticker: string, force = false) => {
        if (esRef.current) {
            esRef.current.close();
            esRef.current = null;
        }

        const symbol = ticker.trim().toUpperCase();
        if (!symbol) return;

        setState({
            status: "fetching_data",
            ticker: symbol,
            dataReady: null,
            agents: [],
            dalio: null,
            error: null,
            agentCount: 0,
            fromCache: false,
            cachedAt: null,
        });

        const url = `${BACKEND_URL}/analyze/stream?ticker=${encodeURIComponent(symbol)}${force ? "&force=true" : ""}`;
        const es = new EventSource(url);
        esRef.current = es;

        es.addEventListener("data_ready", (e: MessageEvent) => {
            const payload: DataReadyPayload = JSON.parse(e.data);
            setState((prev) => ({
                ...prev,
                status: "analyzing",
                dataReady: payload,
                fromCache: payload.from_cache ?? false,
                cachedAt: payload.cached_at ?? null,
            }));
        });

        // --- agent_update: one of the 8 agents finished ---
        es.addEventListener("agent_update", (e: MessageEvent) => {
            const agent: AgentSignal = JSON.parse(e.data);
            setState((prev) => ({
                ...prev,
                agents: [...prev.agents, agent],
                agentCount: prev.agentCount + 1,
            }));
        });

        // --- dalio_verdict: Dalio finished → stream is complete ---
        es.addEventListener("dalio_verdict", (e: MessageEvent) => {
            const verdict: DalioVerdict = JSON.parse(e.data);
            setState((prev) => ({
                ...prev,
                status: "complete",
                dalio: verdict,
            }));
            es.close();
            esRef.current = null;
        });

        // --- done: clean close without verdict (edge case) ---
        es.addEventListener("done", () => {
            setState((prev) => ({ ...prev, status: "complete" }));
            es.close();
            esRef.current = null;
        });

        // --- error event from server ---
        es.addEventListener("error", (e: MessageEvent) => {
            let message = "Unknown error from server";
            try {
                message = JSON.parse(e.data)?.message ?? message;
            } catch { }
            setState((prev) => ({ ...prev, status: "error", error: message }));
            es.close();
            esRef.current = null;
        });

        // --- onerror: network / connection problems ---
        es.onerror = () => {
            setState((prev) => {
                if (prev.status !== "complete") {
                    return {
                        ...prev,
                        status: "error",
                        error: "Connection to backend lost. Make sure the server is running.",
                    };
                }
                return prev;
            });
            es.close();
            esRef.current = null;
        };
    }, []);

    const reset = useCallback(() => {
        if (esRef.current) {
            esRef.current.close();
            esRef.current = null;
        }
        setState({
            status: "idle",
            ticker: "",
            dataReady: null,
            agents: [],
            dalio: null,
            error: null,
            agentCount: 0,
            fromCache: false,
            cachedAt: null,
        });
    }, []);

    /** Force-bypass the cache: invalidate on server then re-run. */
    const forceRefresh = useCallback(async (ticker: string) => {
        if (!ticker) return;
        const symbol = ticker.trim().toUpperCase();
        try {
            await fetch(`${BACKEND_URL}/cache/${encodeURIComponent(symbol)}`, { method: "DELETE" });
        } catch { /* ignore — still try to re-analyze */ }
        analyze(symbol, true);
    }, [analyze]);

    return { state, analyze, forceRefresh, reset, TOTAL_AGENTS };
}
