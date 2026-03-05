"use client";

import { useState, useCallback } from "react";
import type { OpportunityScore, PositionSizing } from "./useCombinedStream";

export interface PortfolioPositionInput {
    ticker: string;
    sector: string;
    opportunity_score: number;
    dimensions: Record<string, number>;
    position_sizing: PositionSizing;
}

export interface PortfolioPositionOutput {
    ticker: string;
    role: "CORE" | "SATELLITE";
    sector: string;
    target_weight: number;
}

export interface PortfolioRecommendationResult {
    total_allocation: number;
    core_allocation_total: number;
    satellite_allocation_total: number;
    risk_level: string;
    sector_exposures: Record<string, number>;
    core_positions: PortfolioPositionOutput[];
    satellite_positions: PortfolioPositionOutput[];
    violations_detected: string[];
}

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function usePortfolioBuilder() {
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<PortfolioRecommendationResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const buildPortfolio = useCallback(async (positions: PortfolioPositionInput[]) => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await fetch(`${BACKEND_URL}/portfolio/build`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ positions }),
            });

            if (!response.ok) {
                const txt = await response.text();
                throw new Error(txt || `Server error: ${response.status}`);
            }

            const data: PortfolioRecommendationResult = await response.json();
            setResult(data);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Failed to build portfolio");
        } finally {
            setIsLoading(false);
        }
    }, []);

    const reset = () => {
        setResult(null);
        setError(null);
    };

    return { buildPortfolio, result, isLoading, error, reset };
}
