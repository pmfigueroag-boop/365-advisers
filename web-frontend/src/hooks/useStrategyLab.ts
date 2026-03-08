"use client";

/**
 * useStrategyLab.ts
 * ──────────────────────────────────────────────────────────────────────────
 * Data hook for the Strategy Lab.
 * Manages strategies, templates, recommendations, and sub-view state.
 */

import { useState, useCallback, useEffect, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────

export type LabSubView = "home" | "builder" | "backtest" | "compare" | "portfolio";

export interface StrategyItem {
    strategy_id: string;
    name: string;
    description: string;
    version: string;
    category: string;
    lifecycle_state: string;
    tags: string[];
    sharpe_ratio?: number;
    last_backtest?: string;
    config?: Record<string, unknown>;
}

export interface TemplateItem {
    name: string;
    description: string;
    category: string;
    config: Record<string, unknown>;
}

export interface Recommendation {
    name: string;
    strategy_id?: string;
    reason: string;
    expected_sharpe?: number;
}

interface LabState {
    strategies: StrategyItem[];
    templates: TemplateItem[];
    recommendations: Recommendation[];
    loading: boolean;
    error: string | null;
}

// ── Hook ───────────────────────────────────────────────────────────────────

export function useStrategyLab() {
    const [subView, setSubView] = useState<LabSubView>("home");
    const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
    const [state, setState] = useState<LabState>({
        strategies: [],
        templates: [],
        recommendations: [],
        loading: false,
        error: null,
    });
    const fetchedRef = useRef(false);

    // ── Fetch strategies ───────────────────────────────────────────────────
    const fetchStrategies = useCallback(async () => {
        try {
            const res = await fetch(`${API}/lab/strategies`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const list = Array.isArray(data) ? data : data.strategies ?? [];
            setState((s) => ({ ...s, strategies: list }));
        } catch {
            // Non-fatal — strategies may just be empty
        }
    }, []);

    // ── Fetch templates ────────────────────────────────────────────────────
    const fetchTemplates = useCallback(async () => {
        try {
            const res = await fetch(`${API}/lab/templates`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const list = Array.isArray(data) ? data : data.templates ?? [];
            setState((s) => ({ ...s, templates: list }));
        } catch {
            // Non-fatal
        }
    }, []);

    // ── Fetch recommendations ──────────────────────────────────────────────
    const fetchRecommendations = useCallback(async () => {
        try {
            const res = await fetch(`${API}/lab/recommendations?top_n=5`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const recs = Array.isArray(data) ? data : data.recommendations ?? [];
            setState((s) => ({ ...s, recommendations: recs }));
        } catch {
            // Non-fatal
        }
    }, []);

    // ── Initial load ───────────────────────────────────────────────────────
    const loadAll = useCallback(async () => {
        if (state.loading) return;
        setState((s) => ({ ...s, loading: true, error: null }));
        try {
            await Promise.all([fetchStrategies(), fetchTemplates(), fetchRecommendations()]);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to load lab data";
            setState((s) => ({ ...s, error: message }));
        } finally {
            setState((s) => ({ ...s, loading: false }));
        }
    }, [fetchStrategies, fetchTemplates, fetchRecommendations, state.loading]);

    useEffect(() => {
        if (!fetchedRef.current) {
            fetchedRef.current = true;
            loadAll();
        }
    }, [loadAll]);

    // ── Actions ────────────────────────────────────────────────────────────
    const createStrategy = useCallback(async (name: string, description: string, config?: Record<string, unknown>) => {
        setState((s) => ({ ...s, loading: true }));
        try {
            const res = await fetch(`${API}/lab/strategies`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, description, config: config ?? {} }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            await fetchStrategies();
            return data.strategy_id ?? data.id;
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to create strategy";
            setState((s) => ({ ...s, error: message }));
            return null;
        } finally {
            setState((s) => ({ ...s, loading: false }));
        }
    }, [fetchStrategies]);

    const cloneStrategy = useCallback(async (strategyId: string, newName: string) => {
        try {
            const res = await fetch(`${API}/lab/strategies/${strategyId}/clone?new_name=${encodeURIComponent(newName)}`, {
                method: "POST",
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            await fetchStrategies();
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to clone";
            setState((s) => ({ ...s, error: message }));
        }
    }, [fetchStrategies]);

    const deactivateStrategy = useCallback(async (strategyId: string) => {
        try {
            await fetch(`${API}/lab/strategies/${strategyId}`, { method: "DELETE" });
            await fetchStrategies();
        } catch {
            // silent
        }
    }, [fetchStrategies]);

    // ── Navigation helpers ─────────────────────────────────────────────────
    const openBuilder = useCallback((strategyId?: string) => {
        setSelectedStrategyId(strategyId ?? null);
        setSubView("builder");
    }, []);

    const openBacktest = useCallback((strategyId: string) => {
        setSelectedStrategyId(strategyId);
        setSubView("backtest");
    }, []);

    return {
        // State
        ...state,
        subView,
        selectedStrategyId,
        // Navigation
        setSubView,
        openBuilder,
        openBacktest,
        setSelectedStrategyId,
        // Actions
        createStrategy,
        cloneStrategy,
        deactivateStrategy,
        refresh: loadAll,
    };
}
