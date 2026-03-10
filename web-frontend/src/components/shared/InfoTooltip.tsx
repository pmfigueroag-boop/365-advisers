"use client";

/**
 * InfoTooltip.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Lightweight contextual help tooltip that appears on hover.
 * Designed for section headers and metric labels in the Terminal view.
 *
 * Usage:
 *   <InfoTooltip text="Explanation of this panel">
 *       <span>Visible label</span>
 *   </InfoTooltip>
 */

import { Info } from "lucide-react";
import { type ReactNode } from "react";

interface InfoTooltipProps {
    /** Tooltip explanation text */
    text: string;
    /** Content to wrap (the label or section header) */
    children: ReactNode;
    /** Show a small ⓘ icon next to children */
    showIcon?: boolean;
    /** Tooltip position relative to trigger */
    position?: "top" | "bottom" | "left" | "right";
    /** Max width of the tooltip popup (px) */
    maxWidth?: number;
}

export default function InfoTooltip({
    text,
    children,
    showIcon = true,
    position = "top",
    maxWidth = 240,
}: InfoTooltipProps) {
    // Position classes
    const posClasses: Record<string, string> = {
        top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
        bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
        left: "right-full top-1/2 -translate-y-1/2 mr-2",
        right: "left-full top-1/2 -translate-y-1/2 ml-2",
    };

    // Arrow classes
    const arrowClasses: Record<string, string> = {
        top: "top-full left-1/2 -translate-x-1/2 border-t-[#30363d] border-x-transparent border-b-transparent",
        bottom: "bottom-full left-1/2 -translate-x-1/2 border-b-[#30363d] border-x-transparent border-t-transparent",
        left: "left-full top-1/2 -translate-y-1/2 border-l-[#30363d] border-y-transparent border-r-transparent",
        right: "right-full top-1/2 -translate-y-1/2 border-r-[#30363d] border-y-transparent border-l-transparent",
    };

    return (
        <div className="group/tip relative inline-flex items-center gap-1 cursor-help">
            {children}
            {showIcon && (
                <Info
                    size={10}
                    className="text-gray-700 group-hover/tip:text-[#d4af37]/60 transition-colors flex-shrink-0"
                />
            )}
            <div
                className={`
                    absolute ${posClasses[position]} z-[60]
                    pointer-events-none
                    opacity-0 scale-95 group-hover/tip:opacity-100 group-hover/tip:scale-100
                    transition-all duration-200 ease-out
                `}
                style={{ width: maxWidth }}
            >
                <div
                    className="p-2.5 rounded-lg border border-[#30363d] text-[10px] leading-relaxed text-gray-300 normal-case tracking-normal font-normal"
                    style={{
                        background: "linear-gradient(135deg, #1c2128 0%, #161b22 100%)",
                        boxShadow: "0 8px 32px -4px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.03)",
                        backdropFilter: "blur(12px)",
                    }}
                >
                    {text}
                </div>
                {/* Arrow */}
                <div className={`absolute w-0 h-0 border-4 ${arrowClasses[position]}`} />
            </div>
        </div>
    );
}
