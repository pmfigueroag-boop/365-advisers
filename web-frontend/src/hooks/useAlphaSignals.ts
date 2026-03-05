"use client";

/**
 * useAlphaSignals.ts
 * ──────────────────────────────────────────────────────────────────────────
 * React hook for the Alpha Signals Library API.
 *
 * Provides:
 *  - evaluate(ticker) → fetch signal profile for a ticker
 *  - registry listing
 *  - signal toggling
 */

import { useState, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────

export interface EvaluatedSignal {
    signal_id: string;
    signal_name: string;
    category: string;
    fired: boolean;
    value: number | null;
    threshold: number;
    strength: "strong" | "moderate" | "weak";
    confidence: number;
    description: string;
}

export interface CategoryScore {
    category: string;
    fired: number;
    total: number;
    composite_strength: number;
    confidence: "high" | "medium" | "low";
    dominant_strength: "strong" | "moderate" | "weak";
}

export interface CompositeScore {
    overall_strength: number;
    overall_confidence: "high" | "medium" | "low";
    category_scores: Record<string, CategoryScore>;
    multi_category_bonus: boolean;
    dominant_category: string | null;
    active_categories: number;
}

export interface CategorySubscoreResponse {
    category: string;
    score: number;
    fired: number;
    total: number;
    coverage: number;
    top_signals: string[];
    conflict_detected: boolean;
    conflict_penalty: number;
}

export interface DecayInfo {
    applied: boolean;
    average_freshness: number;
    expired_signals: number;
    freshness_level: "fresh" | "aging" | "stale" | "expired";
}

export interface CompositeAlphaResponse {
    score: number;
    environment: string;
    subscores: Record<string, CategorySubscoreResponse>;
    active_categories: number;
    convergence_bonus: number;
    cross_category_conflicts: string[];
    decay?: DecayInfo;
}

export interface SignalProfileResponse {
    ticker: string;
    evaluated_at: string;
    total_signals: number;
    fired_signals: number;
    signals: EvaluatedSignal[];
    category_summary: Record<string, CategoryScore>;
    composite: CompositeScore;
    composite_alpha?: CompositeAlphaResponse;
}

export interface RegistrySignal {
    id: string;
    name: string;
    category: string;
    description: string;
    feature_path: string;
    direction: string;
    threshold: number;
    enabled: boolean;
    weight: number;
    tags: string[];
}

export type SignalStatus = "idle" | "loading" | "done" | "error";

// ── Hook ──────────────────────────────────────────────────────────────────

export function useAlphaSignals() {
    const [profile, setProfile] = useState<SignalProfileResponse | null>(null);
    const [status, setStatus] = useState<SignalStatus>("idle");
    const [error, setError] = useState<string | null>(null);

    const evaluate = useCallback(async (ticker: string) => {
        setStatus("loading");
        setError(null);
        try {
            const res = await fetch(`${API}/signals/${encodeURIComponent(ticker)}`);
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || `HTTP ${res.status}`);
            }
            const data: SignalProfileResponse = await res.json();
            setProfile(data);
            setStatus("done");
            return data;
        } catch (e: any) {
            setError(e.message || "Failed to evaluate signals");
            setStatus("error");
            return null;
        }
    }, []);

    const clearProfile = useCallback(() => {
        setProfile(null);
        setStatus("idle");
        setError(null);
    }, []);

    return { profile, status, error, evaluate, clearProfile };
}
