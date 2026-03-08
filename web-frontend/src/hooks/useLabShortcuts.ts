"use client";

/**
 * useLabShortcuts.ts
 * ──────────────────────────────────────────────────────────────────────────
 * Global keyboard shortcuts for the Strategy Lab terminal.
 *
 * Shortcuts:
 *   Shift+1–5  → Navigate between views
 *   Ctrl+K     → Open command palette
 *   Escape     → Close command palette / collapse panels
 */

import { useEffect, useCallback } from "react";
import type { LabSubView } from "@/hooks/useStrategyLab";

const VIEW_KEYS: Record<string, LabSubView> = {
    "1": "home",
    "2": "builder",
    "3": "backtest",
    "4": "compare",
    "5": "portfolio",
};

interface UseLabShortcutsOptions {
    onNavigate: (view: LabSubView) => void;
    onTogglePalette: () => void;
    onEscape?: () => void;
    enabled?: boolean;
}

export function useLabShortcuts({
    onNavigate,
    onTogglePalette,
    onEscape,
    enabled = true,
}: UseLabShortcutsOptions) {
    const handleKeyDown = useCallback(
        (e: KeyboardEvent) => {
            if (!enabled) return;

            // Don't capture when typing in inputs/textareas
            const tag = (e.target as HTMLElement)?.tagName;
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
                // Allow Escape even in inputs
                if (e.key === "Escape") {
                    onEscape?.();
                    return;
                }
                return;
            }

            // Shift+1–5 → Navigate views
            if (e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
                const view = VIEW_KEYS[e.key];
                if (view) {
                    e.preventDefault();
                    onNavigate(view);
                    return;
                }
            }

            // Ctrl+K / Cmd+K → Command palette
            if ((e.ctrlKey || e.metaKey) && e.key === "k") {
                e.preventDefault();
                onTogglePalette();
                return;
            }

            // Escape → Close palette / panels
            if (e.key === "Escape") {
                onEscape?.();
                return;
            }
        },
        [enabled, onNavigate, onTogglePalette, onEscape],
    );

    useEffect(() => {
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [handleKeyDown]);
}
