"use client";

import React, { useState, useEffect } from "react";
import { ChevronDown, Layers, Info } from "lucide-react";

const BACKEND_URL = "http://localhost:8000";

// ── Types ────────────────────────────────────────────────────────────────────

export interface StrategyProfileData {
    key: string;
    display_name: string;
    description: string;
    enabled_detectors: string[];
    disabled_detectors: string[];
    ranking_weights: {
        w_signal: number;
        w_alpha: number;
        w_confidence: number;
        multi_detector_bonus: number;
    };
    minimum_confidence: number;
    minimum_signal_strength: number;
    preferred_horizons: string[];
    sort_default: string;
    ui_hints: {
        icon?: string;
        color?: string;
        badge?: string;
    };
    active: boolean;
}

interface StrategyProfileSelectorProps {
    selectedProfile: string | null;
    onSelect: (profileKey: string | null) => void;
    compact?: boolean;
}

// ── Component ────────────────────────────────────────────────────────────────

export default function StrategyProfileSelector({
    selectedProfile,
    onSelect,
    compact = false,
}: StrategyProfileSelectorProps) {
    const [profiles, setProfiles] = useState<StrategyProfileData[]>([]);
    const [isOpen, setIsOpen] = useState(false);
    const [hoveredKey, setHoveredKey] = useState<string | null>(null);

    useEffect(() => {
        fetch(`${BACKEND_URL}/ideas/profiles`)
            .then((r) => r.json())
            .then((data) => setProfiles(data.profiles ?? []))
            .catch(() => setProfiles([]));
    }, []);

    const selected = profiles.find((p) => p.key === selectedProfile);
    const displayLabel = selected?.display_name ?? "All Strategies";
    const displayBadge = selected?.ui_hints?.badge;
    const displayColor = selected?.ui_hints?.color ?? "#d4af37";

    return (
        <div className="relative">
            {/* Trigger button */}
            <button
                id="strategy-profile-selector"
                onClick={() => setIsOpen(!isOpen)}
                className={`flex items-center gap-1.5 rounded border transition-all ${
                    isOpen
                        ? "border-[#d4af37]/50 bg-[#d4af37]/10"
                        : "border-[#30363d] bg-[#161b22]/60 hover:border-[#484f58]"
                } ${compact ? "px-2 py-1" : "px-3 py-1.5"}`}
            >
                <Layers
                    size={compact ? 10 : 12}
                    style={{ color: selected ? displayColor : "#8b949e" }}
                />
                <span
                    className={`font-bold tracking-wider uppercase ${
                        compact ? "text-[7px]" : "text-[8px]"
                    }`}
                    style={{ color: selected ? displayColor : "#8b949e" }}
                >
                    {displayLabel}
                </span>
                {displayBadge && (
                    <span
                        className="text-[7px] font-bold px-1 py-0 rounded"
                        style={{
                            color: displayColor,
                            background: `${displayColor}20`,
                        }}
                    >
                        {displayBadge}
                    </span>
                )}
                <ChevronDown
                    size={10}
                    className={`text-gray-600 transition-transform ${
                        isOpen ? "rotate-180" : ""
                    }`}
                />
            </button>

            {/* Dropdown */}
            {isOpen && (
                <div className="absolute top-full left-0 mt-1 z-50 w-64 rounded-lg border border-[#30363d] bg-[#161b22] shadow-xl animate-in fade-in slide-in-from-top-1 duration-150">
                    {/* Default option */}
                    <button
                        onClick={() => { onSelect(null); setIsOpen(false); }}
                        className={`w-full text-left px-3 py-2 transition-colors border-b border-[#30363d] ${
                            selectedProfile === null
                                ? "bg-[#d4af37]/10 text-[#d4af37]"
                                : "text-gray-400 hover:bg-[#21262d]"
                        }`}
                    >
                        <div className="flex items-center gap-1.5">
                            <Layers size={10} className="text-gray-500" />
                            <span className="text-[9px] font-bold uppercase">All Strategies</span>
                        </div>
                        <p className="text-[8px] text-gray-600 mt-0.5">
                            Default institutional scan — all detectors active
                        </p>
                    </button>

                    {/* Profile list */}
                    {profiles.map((profile) => (
                        <button
                            key={profile.key}
                            id={`strategy-profile-${profile.key}`}
                            onClick={() => { onSelect(profile.key); setIsOpen(false); }}
                            onMouseEnter={() => setHoveredKey(profile.key)}
                            onMouseLeave={() => setHoveredKey(null)}
                            className={`w-full text-left px-3 py-2 transition-colors border-b border-[#30363d]/50 last:border-0 ${
                                selectedProfile === profile.key
                                    ? "bg-[#d4af37]/10"
                                    : "hover:bg-[#21262d]"
                            }`}
                        >
                            <div className="flex items-center gap-1.5">
                                <span
                                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                                    style={{ background: profile.ui_hints?.color ?? "#8b949e" }}
                                />
                                <span
                                    className="text-[9px] font-bold"
                                    style={{
                                        color:
                                            selectedProfile === profile.key
                                                ? profile.ui_hints?.color ?? "#d4af37"
                                                : "#e6edf3",
                                    }}
                                >
                                    {profile.display_name}
                                </span>
                                {profile.ui_hints?.badge && (
                                    <span
                                        className="text-[7px] font-bold px-1 py-0 rounded"
                                        style={{
                                            color: profile.ui_hints.color ?? "#8b949e",
                                            background: `${profile.ui_hints.color ?? "#8b949e"}20`,
                                        }}
                                    >
                                        {profile.ui_hints.badge}
                                    </span>
                                )}
                            </div>

                            {/* Description (show on hover or when selected) */}
                            {(hoveredKey === profile.key || selectedProfile === profile.key) && (
                                <p className="text-[8px] text-gray-500 mt-0.5 leading-relaxed">
                                    {profile.description}
                                </p>
                            )}

                            {/* Active detectors */}
                            <div className="flex flex-wrap gap-0.5 mt-1">
                                {profile.enabled_detectors.map((d) => (
                                    <span
                                        key={d}
                                        className="text-[7px] font-mono px-1 py-0 rounded bg-[#30363d] text-gray-400"
                                    >
                                        {d}
                                    </span>
                                ))}
                            </div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
