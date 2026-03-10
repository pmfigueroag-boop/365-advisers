"use client";

import { useState, useCallback } from "react";

const BACKEND_URL = "http://localhost:8000";

// ── Types ────────────────────────────────────────────────────────────────────

export interface IdeaSignal {
    name: string;
    description: string;
    value: number;
    threshold: number;
    strength: "strong" | "moderate" | "weak";
}

export interface IdeaItem {
    id: string;
    idea_uid: string;
    ticker: string;
    name: string;
    sector: string;
    idea_type: "value" | "quality" | "growth" | "momentum" | "reversal" | "event";
    confidence: "high" | "medium" | "low";
    signal_strength: number;
    confidence_score?: number;
    detector?: string;
    priority: number;
    signals: IdeaSignal[];
    status: "active" | "analyzed" | "validated" | "in_portfolio" | "dismissed";
    generated_at: string;
    metadata?: Record<string, any>;
}

export interface ScanResult {
    scan_id: string;
    universe_size: number;
    ideas_found: number;
    scan_duration_ms: number;
    detector_stats: Record<string, any>;
    ideas: IdeaItem[];
    strategy_profile?: string | null;
}

export interface UniverseMeta {
    total_discovered: number;
    total_after_dedup: number;
    sources: Record<string, number>;
    discovery_ms: number;
}

type ScanStatus = "idle" | "scanning" | "done" | "error";

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useIdeasEngine() {
    const [ideas, setIdeas] = useState<IdeaItem[]>([]);
    const [scanStatus, setScanStatus] = useState<ScanStatus>("idle");
    const [lastScan, setLastScan] = useState<ScanResult | null>(null);
    const [lastUniverse, setLastUniverse] = useState<UniverseMeta | null>(null);
    const [error, setError] = useState<string | null>(null);

    /** Run a universe scan with the given tickers and optional strategy profile. */
    const scan = useCallback(async (tickers: string[], profileKey?: string) => {
        if (tickers.length === 0) return;
        setScanStatus("scanning");
        setError(null);

        try {
            const payload: Record<string, any> = { tickers };
            if (profileKey) payload.strategy_profile = profileKey;

            const res = await fetch(`${BACKEND_URL}/ideas/scan`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (!res.ok) throw new Error(`Scan failed: HTTP ${res.status}`);

            const data: ScanResult = await res.json();
            setLastScan(data);
            setIdeas(data.ideas);
            setLastUniverse(null);
            setScanStatus("done");
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            setError(msg);
            setScanStatus("error");
        }
    }, []);

    /** Auto-discover universe and scan — calls /ideas/scan/auto */
    const autoScan = useCallback(async (
        sources: string[] = ["static_index", "screener", "sector_rotation", "portfolio", "idea_history"],
        profileKey?: string,
        maxTickers: number = 50,
    ) => {
        setScanStatus("scanning");
        setError(null);

        try {
            const payload: Record<string, any> = {
                sources,
                max_tickers: maxTickers,
            };
            if (profileKey) payload.strategy_profile = profileKey;

            const res = await fetch(`${BACKEND_URL}/ideas/scan/auto`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (!res.ok) throw new Error(`Auto-scan failed: HTTP ${res.status}`);

            const data: ScanResult = await res.json();
            setLastScan(data);
            setIdeas(data.ideas);

            // Extract universe metadata from detector_stats
            const ud = data.detector_stats?.universe_discovery;
            if (ud) {
                setLastUniverse({
                    total_discovered: ud.total_discovered,
                    total_after_dedup: ud.total_after_dedup,
                    sources: ud.sources,
                    discovery_ms: ud.discovery_ms,
                });
            }

            setScanStatus("done");
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            setError(msg);
            setScanStatus("error");
        }
    }, []);

    /** Fetch active ideas from the backend. */
    const fetchIdeas = useCallback(async (ideaType?: string) => {
        try {
            const params = new URLSearchParams({ status: "active" });
            if (ideaType) params.set("idea_type", ideaType);

            const res = await fetch(`${BACKEND_URL}/ideas?${params}`);
            if (!res.ok) throw new Error(`Fetch failed: HTTP ${res.status}`);

            const data: IdeaItem[] = await res.json();
            setIdeas(data);
        } catch (e) {
            console.error("Failed to fetch ideas:", e);
        }
    }, []);

    /** Dismiss an idea. */
    const dismiss = useCallback(async (ideaId: string) => {
        try {
            await fetch(`${BACKEND_URL}/ideas/${ideaId}/dismiss`, { method: "POST" });
            setIdeas((prev) => prev.filter((i) => i.id !== ideaId));
        } catch (e) {
            console.error("Failed to dismiss idea:", e);
        }
    }, []);

    /** Mark an idea as analyzed. */
    const markAnalyzed = useCallback(async (ideaId: string) => {
        try {
            await fetch(`${BACKEND_URL}/ideas/${ideaId}/analyze`, { method: "POST" });
            setIdeas((prev) =>
                prev.map((i) => (i.id === ideaId ? { ...i, status: "analyzed" as const } : i))
            );
        } catch (e) {
            console.error("Failed to mark idea analyzed:", e);
        }
    }, []);

    /** Update idea status to any valid state. */
    const updateStatus = useCallback(async (ideaId: string, newStatus: string) => {
        try {
            const res = await fetch(`${BACKEND_URL}/ideas/${ideaId}/status`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: newStatus }),
            });
            if (!res.ok) return;
            setIdeas((prev) =>
                prev.map((i) => (i.id === ideaId ? { ...i, status: newStatus as IdeaItem["status"] } : i))
            );
        } catch (e) {
            console.error("Failed to update idea status:", e);
        }
    }, []);

    return {
        ideas,
        scanStatus,
        lastScan,
        lastUniverse,
        error,
        scan,
        autoScan,
        fetchIdeas,
        dismiss,
        markAnalyzed,
        updateStatus,
    };
}
