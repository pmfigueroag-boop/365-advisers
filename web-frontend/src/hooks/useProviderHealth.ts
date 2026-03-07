"use client";

/**
 * useProviderHealth.ts
 * ──────────────────────────────────────────────────────────────────────────
 * Hook for fetching EDPL provider health and registry data.
 */

import { useState, useEffect, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ProviderHealth {
    provider_name: string;
    domain: string;
    status: string;
    last_success: string | null;
    last_failure: string | null;
    consecutive_failures: number;
    avg_latency_ms: number;
    message: string;
}

export interface RegistryEntry {
    name: string;
    status: string;
    capabilities: string[];
}

export interface ProviderRegistryData {
    domains: Record<string, RegistryEntry[]>;
    active_domains: string[];
}

export function useProviderHealth() {
    const [health, setHealth] = useState<Record<string, ProviderHealth>>({});
    const [registry, setRegistry] = useState<ProviderRegistryData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [healthResp, registryResp] = await Promise.all([
                fetch(`${API}/providers/health`),
                fetch(`${API}/providers/registry`),
            ]);

            if (healthResp.ok) {
                const data = await healthResp.json();
                setHealth(data.providers || {});
            }

            if (registryResp.ok) {
                const data = await registryResp.json();
                setRegistry({
                    domains: data.domains || {},
                    active_domains: data.active_domains || [],
                });
            }
        } catch (err: any) {
            setError(err.message || "Failed to fetch provider status");
        } finally {
            setLoading(false);
        }
    }, []);

    // Auto-refresh on mount and every 30s
    useEffect(() => {
        refresh();
        const interval = setInterval(refresh, 30000);
        return () => clearInterval(interval);
    }, [refresh]);

    const toggleProvider = useCallback(async (name: string, enable: boolean) => {
        try {
            const endpoint = enable ? "enable" : "disable";
            await fetch(`${API}/providers/${name}/${endpoint}`, { method: "POST" });
            await refresh();
        } catch (err) {
            console.error("Failed to toggle provider:", err);
        }
    }, [refresh]);

    return { health, registry, loading, error, refresh, toggleProvider };
}
