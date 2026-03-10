"use client";

/**
 * HelpTooltip.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Reusable contextual help component for the IDEA module.
 *
 * - Hover → short description tooltip
 * - Click → extended popover with detailed explanation
 * - Keyboard accessible (Tab, Escape)
 * - ARIA: role="tooltip", aria-describedby
 *
 * Usage:
 *   <HelpTooltip topic="signal_strength" />
 *   <HelpTooltip topic="detector_value" side="right" />
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { HelpCircle } from "lucide-react";
import { getHelp, type HelpEntry } from "./helpContent";

// ─── Types ────────────────────────────────────────────────────────────────────

interface HelpTooltipProps {
    /** Key in the HelpContentRegistry */
    topic: string;
    /** Tooltip position relative to the icon */
    side?: "top" | "bottom" | "left" | "right";
    /** Compact mode — smaller icon for inline labels */
    compact?: boolean;
    /** Override the icon size (default: 12 for compact, 14 for normal) */
    size?: number;
    /** Additional className on the wrapper */
    className?: string;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function HelpTooltip({
    topic,
    side = "top",
    compact = false,
    size,
    className = "",
}: HelpTooltipProps) {
    const help: HelpEntry = getHelp(topic);
    const iconSize = size ?? (compact ? 11 : 13);

    const [showTooltip, setShowTooltip] = useState(false);
    const [showPopover, setShowPopover] = useState(false);
    const popoverRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLButtonElement>(null);

    const tooltipId = `help-tooltip-${topic}`;
    const popoverId = `help-popover-${topic}`;

    // Close popover on outside click
    useEffect(() => {
        if (!showPopover) return;
        const handleOutside = (e: MouseEvent) => {
            if (
                popoverRef.current &&
                !popoverRef.current.contains(e.target as Node) &&
                triggerRef.current &&
                !triggerRef.current.contains(e.target as Node)
            ) {
                setShowPopover(false);
            }
        };
        document.addEventListener("mousedown", handleOutside);
        return () => document.removeEventListener("mousedown", handleOutside);
    }, [showPopover]);

    // Close popover on Escape
    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === "Escape") {
                setShowPopover(false);
                setShowTooltip(false);
            }
        },
        [],
    );

    // Position classes
    const positionClasses: Record<string, string> = {
        top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
        bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
        left: "right-full top-1/2 -translate-y-1/2 mr-2",
        right: "left-full top-1/2 -translate-y-1/2 ml-2",
    };

    return (
        <span className={`relative inline-flex items-center ${className}`}>
            {/* Trigger */}
            <button
                ref={triggerRef}
                type="button"
                aria-describedby={showPopover ? popoverId : showTooltip ? tooltipId : undefined}
                aria-label={`Help: ${help.title}`}
                className={`
                    inline-flex items-center justify-center rounded-full
                    text-gray-600 hover:text-[#d4af37] focus:text-[#d4af37]
                    focus:outline-none focus:ring-1 focus:ring-[#d4af37]/40 focus:ring-offset-0
                    transition-colors cursor-help
                    ${compact ? "p-0" : "p-0.5"}
                `}
                onMouseEnter={() => {
                    if (!showPopover) setShowTooltip(true);
                }}
                onMouseLeave={() => setShowTooltip(false)}
                onFocus={() => {
                    if (!showPopover) setShowTooltip(true);
                }}
                onBlur={() => setShowTooltip(false)}
                onClick={(e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    setShowPopover(!showPopover);
                    setShowTooltip(false);
                }}
                onKeyDown={handleKeyDown}
            >
                <HelpCircle size={iconSize} />
            </button>

            {/* Hover Tooltip — short description */}
            {showTooltip && !showPopover && (
                <div
                    id={tooltipId}
                    role="tooltip"
                    className={`
                        absolute z-[100] ${positionClasses[side]}
                        bg-[#1c2128] border border-[#30363d] rounded-lg shadow-xl
                        px-3 py-2 min-w-[180px] max-w-[240px]
                        pointer-events-none
                    `}
                    style={{ animation: "fadeIn 0.12s ease" }}
                >
                    <span className="block text-[10px] font-black uppercase tracking-wider text-[#d4af37] mb-0.5">
                        {help.title}
                    </span>
                    <span className="block text-[10px] text-gray-400 leading-relaxed">
                        {help.description}
                    </span>
                    {help.extended && (
                        <span className="block text-[8px] text-gray-600 mt-1 italic">
                            Click for more details
                        </span>
                    )}
                </div>
            )}

            {/* Click Popover — extended description */}
            {showPopover && (
                <div
                    ref={popoverRef}
                    id={popoverId}
                    role="dialog"
                    aria-label={help.title}
                    className={`
                        absolute z-[110] ${positionClasses[side]}
                        bg-[#1c2128] border border-[#d4af37]/30 rounded-xl shadow-2xl
                        px-4 py-3 min-w-[240px] max-w-[320px]
                    `}
                    style={{ animation: "fadeSlideIn 0.15s ease both" }}
                    onKeyDown={handleKeyDown}
                >
                    <div className="flex items-center justify-between mb-2">
                        <span className="block text-[10px] font-black uppercase tracking-wider text-[#d4af37]">
                            {help.title}
                        </span>
                        {help.category && (
                            <span className="text-[8px] font-mono text-gray-600 bg-[#0d1117] rounded px-1.5 py-0.5 border border-[#21262d]">
                                {help.category}
                            </span>
                        )}
                    </div>
                    <span className="block text-[10px] text-gray-300 leading-relaxed mb-2">
                        {help.description}
                    </span>
                    {help.extended && (
                        <span className="block text-[10px] text-gray-500 leading-relaxed border-t border-[#21262d] pt-2">
                            {help.extended}
                        </span>
                    )}
                    {help.related && help.related.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-[#21262d]">
                            <span className="block text-[8px] font-black uppercase tracking-wider text-gray-600 mb-1">
                                Related
                            </span>
                            <div className="flex flex-wrap gap-1">
                                {help.related.map((r) => (
                                    <span
                                        key={r}
                                        className="text-[8px] text-gray-500 bg-[#0d1117] rounded px-1.5 py-0.5 border border-[#21262d]"
                                    >
                                        {r.replace(/_/g, " ")}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </span>
    );
}
