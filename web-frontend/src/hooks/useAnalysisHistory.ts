"use client";

import { useState, useEffect, useCallback } from "react";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface HistoryAgentSummary {
    name: string;
    signal: string;
    confidence: number;
}

export interface HistoryEntry {
    id: string;          // "<TICKER>-<timestamp>"
    ticker: string;
    name: string;
    analyzedAt: string;  // ISO-8601
    signal: string;      // BUY | SELL | HOLD
    agentSummary: HistoryAgentSummary[];
    dalioVerdict: string;
    fromCache: boolean;
    // New fields for Portfolio Builder
    fundamental_score?: number;
    opportunity_score?: number;
    position_sizing?: Record<string, unknown>;
    sector?: string;
    dimensions?: Record<string, number>;
    volatility_atr?: number;
    timestamp?: string;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const STORAGE_KEY = "365_history";
const MAX_ENTRIES = 50;

function loadFromStorage(): HistoryEntry[] {
    if (typeof window === "undefined") return [];
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? (JSON.parse(raw) as HistoryEntry[]) : [];
    } catch {
        return [];
    }
}

function saveToStorage(entries: HistoryEntry[]) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    } catch {
        // quota exceeded — silently ignore
    }
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useAnalysisHistory() {
    const [entries, setEntries] = useState<HistoryEntry[]>([]);
    const [hydrated, setHydrated] = useState(false);

    // SSR-safe hydration
    useEffect(() => {
        setEntries(loadFromStorage());
        setHydrated(true);
    }, []);

    const add = useCallback((entry: Omit<HistoryEntry, "id" | "analyzedAt">) => {
        const now = Date.now();
        const newEntry: HistoryEntry = {
            ...entry,
            id: `${entry.ticker}-${now}`,
            analyzedAt: new Date(now).toISOString(),
            timestamp: new Date(now).toISOString(),
        };
        setEntries((prev) => {
            // Newest first, capped at MAX_ENTRIES
            const updated = [newEntry, ...prev].slice(0, MAX_ENTRIES);
            saveToStorage(updated);
            return updated;
        });
    }, []);

    const removeById = useCallback((id: string) => {
        setEntries((prev) => {
            const updated = prev.filter((e) => e.id !== id);
            saveToStorage(updated);
            return updated;
        });
    }, []);

    const clear = useCallback(() => {
        setEntries([]);
        saveToStorage([]);
    }, []);

    return { entries, add, removeById, clear, hydrated };
}
