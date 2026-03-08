"use client";

/**
 * CommandPalette.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Bloomberg-inspired command palette (Ctrl+K / Cmd+K).
 * Fuzzy search over navigation, actions, and strategies.
 * Supports keyboard navigation (↑/↓ + Enter) and mouse click.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
    Search,
    Home,
    Wrench,
    LineChart,
    GitCompare,
    Briefcase,
    Plus,
    Zap,
    BarChart3,
    Command,
    CornerDownLeft,
    ArrowUp,
    ArrowDown,
} from "lucide-react";
import type { LabSubView, StrategyItem } from "@/hooks/useStrategyLab";

// ── Command definitions ──────────────────────────────────────────────────

interface PaletteCommand {
    id: string;
    label: string;
    description: string;
    icon: React.ReactNode;
    shortcut?: string;
    category: "navigate" | "action" | "strategy";
    action: () => void;
}

interface CommandPaletteProps {
    open: boolean;
    onClose: () => void;
    onNavigate: (view: LabSubView) => void;
    onNewStrategy?: () => void;
    onOpenStrategy?: (id: string) => void;
    strategies?: StrategyItem[];
}

// ── Fuzzy match ──────────────────────────────────────────────────────────

function fuzzyMatch(query: string, text: string): boolean {
    if (!query) return true;
    const q = query.toLowerCase();
    const t = text.toLowerCase();
    let qi = 0;
    for (let ti = 0; ti < t.length && qi < q.length; ti++) {
        if (t[ti] === q[qi]) qi++;
    }
    return qi === q.length;
}

// ── Main component ──────────────────────────────────────────────────────

export default function CommandPalette({
    open,
    onClose,
    onNavigate,
    onNewStrategy,
    onOpenStrategy,
    strategies = [],
}: CommandPaletteProps) {
    const [query, setQuery] = useState("");
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const listRef = useRef<HTMLDivElement>(null);

    // Build command list
    const commands = useMemo<PaletteCommand[]>(() => {
        const cmds: PaletteCommand[] = [
            // Navigation
            { id: "nav-home", label: "Lab Home", description: "Strategy overview & templates", icon: <Home size={14} />, shortcut: "⇧1", category: "navigate", action: () => onNavigate("home") },
            { id: "nav-builder", label: "Strategy Builder", description: "Configure signals, rules, risk", icon: <Wrench size={14} />, shortcut: "⇧2", category: "navigate", action: () => onNavigate("builder") },
            { id: "nav-backtest", label: "Backtest Report", description: "Run & analyze backtests", icon: <LineChart size={14} />, shortcut: "⇧3", category: "navigate", action: () => onNavigate("backtest") },
            { id: "nav-compare", label: "Strategy Compare", description: "Side-by-side comparison", icon: <GitCompare size={14} />, shortcut: "⇧4", category: "navigate", action: () => onNavigate("compare") },
            { id: "nav-portfolio", label: "Portfolio Builder", description: "Multi-strategy allocation", icon: <Briefcase size={14} />, shortcut: "⇧5", category: "navigate", action: () => onNavigate("portfolio") },
            // Actions
            { id: "act-new", label: "New Strategy", description: "Create a new strategy from scratch", icon: <Plus size={14} />, category: "action", action: () => onNewStrategy?.() },
            { id: "act-backtest-all", label: "Quick Metrics", description: "View lab analytics overview", icon: <BarChart3 size={14} />, category: "action", action: () => onNavigate("home") },
        ];

        // Dynamic: strategy open commands
        for (const s of strategies.slice(0, 10)) {
            cmds.push({
                id: `strat-${s.strategy_id}`,
                label: s.name,
                description: `${s.category ?? "strategy"} · v${s.version} · ${s.lifecycle_state}`,
                icon: <Zap size={14} />,
                category: "strategy",
                action: () => onOpenStrategy?.(s.strategy_id),
            });
        }

        return cmds;
    }, [onNavigate, onNewStrategy, onOpenStrategy, strategies]);

    // Filter by query
    const filtered = useMemo(() => {
        if (!query) return commands;
        return commands.filter(
            (cmd) => fuzzyMatch(query, cmd.label) || fuzzyMatch(query, cmd.description),
        );
    }, [commands, query]);

    // Reset on open/close
    useEffect(() => {
        if (open) {
            setQuery("");
            setSelectedIndex(0);
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [open]);

    // Keep selected in bounds
    useEffect(() => {
        if (selectedIndex >= filtered.length) {
            setSelectedIndex(Math.max(0, filtered.length - 1));
        }
    }, [filtered.length, selectedIndex]);

    // Scroll selected into view
    useEffect(() => {
        const el = listRef.current?.children[selectedIndex] as HTMLElement | undefined;
        el?.scrollIntoView({ block: "nearest" });
    }, [selectedIndex]);

    const executeCommand = useCallback(
        (cmd: PaletteCommand) => {
            cmd.action();
            onClose();
        },
        [onClose],
    );

    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === "ArrowDown") {
                e.preventDefault();
                setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSelectedIndex((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter" && filtered[selectedIndex]) {
                e.preventDefault();
                executeCommand(filtered[selectedIndex]);
            } else if (e.key === "Escape") {
                onClose();
            }
        },
        [filtered, selectedIndex, executeCommand, onClose],
    );

    if (!open) return null;

    // Group by category
    const grouped = {
        navigate: filtered.filter((c) => c.category === "navigate"),
        action: filtered.filter((c) => c.category === "action"),
        strategy: filtered.filter((c) => c.category === "strategy"),
    };

    let globalIndex = -1;

    return (
        <>
            {/* Backdrop */}
            <div className="lab-palette-backdrop" onClick={onClose} />

            {/* Palette */}
            <div className="lab-palette" onKeyDown={handleKeyDown}>
                {/* Search input */}
                <div className="lab-palette-search">
                    <Search size={14} className="text-[#d4af37]" />
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => {
                            setQuery(e.target.value);
                            setSelectedIndex(0);
                        }}
                        placeholder="Search commands, views, strategies..."
                        className="lab-palette-input"
                        autoFocus
                    />
                    <kbd className="lab-palette-kbd">ESC</kbd>
                </div>

                {/* Results */}
                <div className="lab-palette-results" ref={listRef}>
                    {filtered.length === 0 && (
                        <div className="lab-palette-empty">
                            No results for &ldquo;{query}&rdquo;
                        </div>
                    )}

                    {grouped.navigate.length > 0 && (
                        <>
                            <div className="lab-palette-group">NAVIGATE</div>
                            {grouped.navigate.map((cmd) => {
                                globalIndex++;
                                const idx = globalIndex;
                                return (
                                    <button
                                        key={cmd.id}
                                        className={`lab-palette-item ${idx === selectedIndex ? "lab-palette-item-selected" : ""}`}
                                        onClick={() => executeCommand(cmd)}
                                        onMouseEnter={() => setSelectedIndex(idx)}
                                    >
                                        <div className="lab-palette-item-icon">{cmd.icon}</div>
                                        <div className="lab-palette-item-text">
                                            <span className="lab-palette-item-label">{cmd.label}</span>
                                            <span className="lab-palette-item-desc">{cmd.description}</span>
                                        </div>
                                        {cmd.shortcut && (
                                            <kbd className="lab-palette-item-shortcut">{cmd.shortcut}</kbd>
                                        )}
                                    </button>
                                );
                            })}
                        </>
                    )}

                    {grouped.action.length > 0 && (
                        <>
                            <div className="lab-palette-group">ACTIONS</div>
                            {grouped.action.map((cmd) => {
                                globalIndex++;
                                const idx = globalIndex;
                                return (
                                    <button
                                        key={cmd.id}
                                        className={`lab-palette-item ${idx === selectedIndex ? "lab-palette-item-selected" : ""}`}
                                        onClick={() => executeCommand(cmd)}
                                        onMouseEnter={() => setSelectedIndex(idx)}
                                    >
                                        <div className="lab-palette-item-icon">{cmd.icon}</div>
                                        <div className="lab-palette-item-text">
                                            <span className="lab-palette-item-label">{cmd.label}</span>
                                            <span className="lab-palette-item-desc">{cmd.description}</span>
                                        </div>
                                    </button>
                                );
                            })}
                        </>
                    )}

                    {grouped.strategy.length > 0 && (
                        <>
                            <div className="lab-palette-group">STRATEGIES</div>
                            {grouped.strategy.map((cmd) => {
                                globalIndex++;
                                const idx = globalIndex;
                                return (
                                    <button
                                        key={cmd.id}
                                        className={`lab-palette-item ${idx === selectedIndex ? "lab-palette-item-selected" : ""}`}
                                        onClick={() => executeCommand(cmd)}
                                        onMouseEnter={() => setSelectedIndex(idx)}
                                    >
                                        <div className="lab-palette-item-icon">{cmd.icon}</div>
                                        <div className="lab-palette-item-text">
                                            <span className="lab-palette-item-label">{cmd.label}</span>
                                            <span className="lab-palette-item-desc">{cmd.description}</span>
                                        </div>
                                    </button>
                                );
                            })}
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="lab-palette-footer">
                    <span><ArrowUp size={10} /> <ArrowDown size={10} /> Navigate</span>
                    <span><CornerDownLeft size={10} /> Select</span>
                    <span><Command size={10} />K Toggle</span>
                </div>
            </div>
        </>
    );
}
