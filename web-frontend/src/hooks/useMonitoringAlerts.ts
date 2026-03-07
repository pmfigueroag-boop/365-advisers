"use client";

/**
 * useMonitoringAlerts.ts
 * ──────────────────────────────────────────────────────────────────────────
 * Hook for the Opportunity Monitoring Engine API.
 * Fetches alerts, marks them as read, and triggers scans.
 */

import { useState, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface MonitoringAlert {
    alert_id: string;
    ticker: string;
    alert_type: string;
    severity: "info" | "warning" | "critical";
    message: string;
    data: Record<string, unknown>;
    is_read: boolean;
    created_at: string;
}

export interface MonitoringScanResult {
    tickers_monitored: number;
    alerts_generated: number;
    alerts: MonitoringAlert[];
    scan_duration_ms: number;
    scanned_at: string;
}

export interface MonitoringState {
    alerts: MonitoringAlert[];
    unreadCount: number;
    lastScan: MonitoringScanResult | null;
    status: "idle" | "loading" | "scanning" | "done" | "error";
    error: string | null;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useMonitoringAlerts() {
    const [state, setState] = useState<MonitoringState>({
        alerts: [],
        unreadCount: 0,
        lastScan: null,
        status: "idle",
        error: null,
    });

    /** Fetch all alerts */
    const fetchAlerts = useCallback(async (opts?: { ticker?: string; severity?: string; unreadOnly?: boolean; limit?: number }) => {
        setState((s) => ({ ...s, status: "loading", error: null }));
        try {
            const params = new URLSearchParams();
            if (opts?.ticker) params.set("ticker", opts.ticker);
            if (opts?.severity) params.set("severity", opts.severity);
            if (opts?.unreadOnly) params.set("unread_only", "true");
            if (opts?.limit) params.set("limit", String(opts.limit));

            const res = await fetch(`${API}/monitoring/alerts?${params}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const alerts: MonitoringAlert[] = data.alerts ?? [];
            setState((s) => ({
                ...s,
                alerts,
                unreadCount: alerts.filter((a) => !a.is_read).length,
                status: "done",
            }));
        } catch (e) {
            setState((s) => ({ ...s, status: "error", error: e instanceof Error ? e.message : String(e) }));
        }
    }, []);

    /** Mark an alert as read */
    const markRead = useCallback(async (alertId: string) => {
        try {
            await fetch(`${API}/monitoring/alerts/${alertId}/read`, { method: "PATCH" });
            setState((s) => ({
                ...s,
                alerts: s.alerts.map((a) => a.alert_id === alertId ? { ...a, is_read: true } : a),
                unreadCount: Math.max(0, s.unreadCount - 1),
            }));
        } catch {
            // Silent
        }
    }, []);

    /** Trigger a monitoring scan */
    const triggerScan = useCallback(async (tickers: string[], scores?: { case?: Record<string, number>; opp?: Record<string, number> }) => {
        if (tickers.length === 0) return;
        setState((s) => ({ ...s, status: "scanning", error: null }));
        try {
            const res = await fetch(`${API}/monitoring/scan`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    tickers,
                    case_scores: scores?.case ?? {},
                    opp_scores: scores?.opp ?? {},
                }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data: MonitoringScanResult = await res.json();
            setState((s) => ({
                ...s,
                lastScan: data,
                alerts: [...data.alerts, ...s.alerts].slice(0, 100),
                unreadCount: s.unreadCount + data.alerts_generated,
                status: "done",
            }));
        } catch (e) {
            setState((s) => ({ ...s, status: "error", error: e instanceof Error ? e.message : String(e) }));
        }
    }, []);

    return {
        ...state,
        fetchAlerts,
        markRead,
        triggerScan,
    };
}
