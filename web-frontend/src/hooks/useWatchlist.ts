"use client";

import { useState, useCallback, useEffect } from "react";

const STORAGE_KEY = "365_watchlist";
const BACKEND_URL = "http://localhost:8000";

export interface WatchlistItem {
    ticker: string;
    name: string;
    addedAt: string;
    lastSignal?: string;        // "BUY" | "SELL" | "HOLD" | "NEUTRAL"
    lastAnalyzedAt?: string;    // ISO timestamp
}

function loadFromStorage(): WatchlistItem[] {
    if (typeof window === "undefined") return [];
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
}

function saveToStorage(items: WatchlistItem[]) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch { }
}

export function useWatchlist() {
    const [items, setItems] = useState<WatchlistItem[]>([]);

    // Hydrate from localStorage on mount (client-side only)
    useEffect(() => {
        setItems(loadFromStorage());
    }, []);

    const persist = useCallback((next: WatchlistItem[]) => {
        setItems(next);
        saveToStorage(next);
    }, []);

    /** Add a ticker to the watchlist. Fetches the name from backend if not provided. */
    const add = useCallback(
        async (ticker: string, name?: string) => {
            const symbol = ticker.trim().toUpperCase();
            setItems((prev) => {
                if (prev.some((i) => i.ticker === symbol)) return prev; // already exists
                return prev; // placeholder while fetching
            });

            let resolvedName = name ?? symbol;

            if (!name) {
                try {
                    const res = await fetch(
                        `${BACKEND_URL}/ticker-info?ticker=${encodeURIComponent(symbol)}`
                    );
                    if (res.ok) {
                        const data = await res.json();
                        resolvedName = data.name ?? symbol;
                    }
                } catch {
                    // fallback: use the symbol as name
                }
            }

            setItems((prev) => {
                if (prev.some((i) => i.ticker === symbol)) return prev;
                const next: WatchlistItem[] = [
                    ...prev,
                    { ticker: symbol, name: resolvedName, addedAt: new Date().toISOString() },
                ];
                saveToStorage(next);
                return next;
            });
        },
        []
    );

    /** Remove a ticker from the watchlist. */
    const remove = useCallback(
        (ticker: string) => {
            setItems((prev) => {
                const next = prev.filter((i) => i.ticker !== ticker.toUpperCase());
                saveToStorage(next);
                return next;
            });
        },
        [persist]
    );

    /** Check if a ticker is in the watchlist. */
    const has = useCallback(
        (ticker: string) => items.some((i) => i.ticker === ticker.trim().toUpperCase()),
        [items]
    );

    /** Update the last signal and analysis timestamp for a ticker. */
    const updateSignal = useCallback(
        (ticker: string, signal: string) => {
            const symbol = ticker.trim().toUpperCase();
            setItems((prev) => {
                const next = prev.map((i) =>
                    i.ticker === symbol
                        ? { ...i, lastSignal: signal, lastAnalyzedAt: new Date().toISOString() }
                        : i
                );
                saveToStorage(next);
                return next;
            });
        },
        []
    );

    return { items, add, remove, has, updateSignal };
}
