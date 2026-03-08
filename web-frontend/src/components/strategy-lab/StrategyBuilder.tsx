"use client";

/**
 * StrategyBuilder.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Visual strategy editor — 8 configuration tabs mapping to StrategyConfig.
 *
 * Tabs: Identity | Signals | Scoring | Entry Rules | Exit Rules |
 *       Regime Filters | Portfolio | Rebalance
 */

import { useState, useCallback } from "react";
import {
    Save,
    Play,
    ArrowLeft,
    Plus,
    Trash2,
    ChevronDown,
    Tag,
    Radio,
    BarChart3,
    DoorOpen,
    DoorClosed,
    CloudLightning,
    Briefcase,
    RefreshCw,
    Copy,
    FlaskConical,
    Check,
    AlertTriangle,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

type BuilderTab = "identity" | "signals" | "scoring" | "entry" | "exit" | "regime" | "portfolio" | "rebalance";

interface StrategyFormData {
    // Identity
    name: string;
    description: string;
    category: string;
    horizon: string;
    tags: string[];
    benchmark: string;
    // Signals
    required_categories: string[];
    preferred_signals: string[];
    min_signal_strength: number;
    min_confidence: string;
    composition_logic: string;
    min_active_signals: number;
    // Scoring
    min_case_score: number;
    min_opportunity_score: number;
    min_business_quality: number;
    min_uos: number;
    max_freshness_class: string;
    // Entry Rules
    entry_rules: Array<{ field: string; operator: string; value: number | string; priority: number; label: string }>;
    // Exit Rules
    exit_rules: Array<{ rule_type: string; params: Record<string, number> }>;
    // Regime
    regime_rules: Array<{ regime: string; action: string; sizing_override: number | null }>;
    // Portfolio
    max_positions: number;
    max_single_position: number;
    max_sector_exposure: number;
    sizing_method: string;
    max_turnover: number;
    // Rebalance
    rebalance_frequency: string;
    rebalance_trigger: string;
    drift_threshold: number;
}

interface StrategyBuilderProps {
    strategyId: string | null;
    initialConfig?: Record<string, unknown>;
    onBack: () => void;
    onSave: (name: string, description: string, config: Record<string, unknown>) => Promise<string | null>;
    onRunBacktest: (strategyId: string) => void;
}

// ── Constants ──────────────────────────────────────────────────────────────

const CATEGORIES = [
    { value: "momentum", label: "Momentum" },
    { value: "value", label: "Value" },
    { value: "quality", label: "Quality" },
    { value: "multi_factor", label: "Multi-Factor" },
    { value: "event_driven", label: "Event-Driven" },
    { value: "thematic", label: "Thematic" },
    { value: "low_vol", label: "Low Volatility" },
];

const HORIZONS = [
    { value: "short", label: "Short (< 1 month)" },
    { value: "medium", label: "Medium (1-6 months)" },
    { value: "long", label: "Long (6+ months)" },
];

const SIGNAL_CATEGORIES = [
    "momentum", "value", "quality", "sentiment", "technical",
    "macro", "event", "flow",
];

const COMPOSITION_LOGIC = [
    { value: "all_required", label: "ALL signals required" },
    { value: "any_required", label: "ANY signal sufficient" },
    { value: "weighted", label: "Weighted combination" },
];

const CONFIDENCE_LEVELS = [
    { value: "low", label: "Low" },
    { value: "medium", label: "Medium" },
    { value: "high", label: "High" },
];

const ENTRY_FIELDS = ["case_score", "opportunity_score", "crowding", "uos", "freshness_score", "signal_strength"];
const ENTRY_OPERATORS = ["gt", "gte", "lt", "lte", "eq"];
const OPERATOR_LABELS: Record<string, string> = { gt: ">", gte: "≥", lt: "<", lte: "≤", eq: "=" };

const EXIT_TYPES = [
    { value: "trailing_stop", label: "Trailing Stop", param_key: "pct", param_label: "Stop %" },
    { value: "time_stop", label: "Time Stop", param_key: "days", param_label: "Days" },
    { value: "target_reached", label: "Target Reached", param_key: "return_pct", param_label: "Target %" },
    { value: "signal_reversal", label: "Signal Reversal", param_key: "", param_label: "" },
];

const REGIMES = ["bull", "bear", "high_vol", "low_vol", "range"];
const REGIME_ACTIONS = [
    { value: "full_exposure", label: "Full Exposure" },
    { value: "reduce_50", label: "Reduce 50%" },
    { value: "no_new_entries", label: "No New Entries" },
    { value: "exit_all", label: "Exit All" },
];

const SIZING_METHODS = [
    { value: "equal", label: "Equal Weight" },
    { value: "vol_parity", label: "Volatility Parity" },
    { value: "rank_weighted", label: "Rank Weighted" },
    { value: "risk_budget", label: "Risk Budget" },
];

const REBALANCE_FREQUENCIES = [
    { value: "daily", label: "Daily" },
    { value: "weekly", label: "Weekly" },
    { value: "biweekly", label: "Biweekly" },
    { value: "monthly", label: "Monthly" },
];

const REBALANCE_TRIGGERS = [
    { value: "calendar", label: "Calendar" },
    { value: "drift_based", label: "Drift-Based" },
    { value: "signal_based", label: "Signal-Based" },
];

const BUILDER_TABS: { id: BuilderTab; label: string; icon: React.ReactNode }[] = [
    { id: "identity", label: "Identity", icon: <Tag size={11} /> },
    { id: "signals", label: "Signals", icon: <Radio size={11} /> },
    { id: "scoring", label: "Scoring", icon: <BarChart3 size={11} /> },
    { id: "entry", label: "Entry Rules", icon: <DoorOpen size={11} /> },
    { id: "exit", label: "Exit Rules", icon: <DoorClosed size={11} /> },
    { id: "regime", label: "Regime", icon: <CloudLightning size={11} /> },
    { id: "portfolio", label: "Portfolio", icon: <Briefcase size={11} /> },
    { id: "rebalance", label: "Rebalance", icon: <RefreshCw size={11} /> },
];

// ── Default form data ──────────────────────────────────────────────────────

function defaultForm(initialConfig?: Record<string, unknown>): StrategyFormData {
    const cfg = initialConfig ?? {};
    const signals = (cfg.signals ?? {}) as Record<string, unknown>;
    const thresholds = (cfg.thresholds ?? {}) as Record<string, unknown>;
    const portfolio = (cfg.portfolio ?? {}) as Record<string, unknown>;
    const rebalance = (cfg.rebalance ?? {}) as Record<string, unknown>;
    const meta = (cfg.metadata ?? {}) as Record<string, unknown>;

    return {
        name: (cfg.name as string) ?? "",
        description: (cfg.description as string) ?? "",
        category: (meta.category as string) ?? "multi_factor",
        horizon: (meta.horizon as string) ?? "medium",
        tags: (meta.tags as string[]) ?? [],
        benchmark: (meta.benchmark as string) ?? "SPY",
        required_categories: (signals.required_categories as string[]) ?? [],
        preferred_signals: (signals.preferred_signals as string[]) ?? [],
        min_signal_strength: (signals.min_signal_strength as number) ?? 0,
        min_confidence: (signals.min_confidence as string) ?? "low",
        composition_logic: (signals.composition_logic as string) ?? "all_required",
        min_active_signals: (signals.min_active_signals as number) ?? 1,
        min_case_score: (thresholds.min_case_score as number) ?? 0,
        min_opportunity_score: (thresholds.min_opportunity_score as number) ?? 0,
        min_business_quality: (thresholds.min_business_quality as number) ?? 0,
        min_uos: (thresholds.min_uos as number) ?? 0,
        max_freshness_class: (thresholds.max_freshness_class as string) ?? "stale",
        entry_rules: (cfg.entry_rules as StrategyFormData["entry_rules"]) ?? [],
        exit_rules: (cfg.exit_rules as StrategyFormData["exit_rules"]) ?? [],
        regime_rules: (cfg.regime_rules as StrategyFormData["regime_rules"]) ?? [],
        max_positions: (portfolio.max_positions as number) ?? 20,
        max_single_position: (portfolio.max_single_position as number) ?? 0.10,
        max_sector_exposure: (portfolio.max_sector_exposure as number) ?? 0.25,
        sizing_method: (portfolio.sizing_method as string) ?? "vol_parity",
        max_turnover: (portfolio.max_turnover as number) ?? 0.50,
        rebalance_frequency: (rebalance.frequency as string) ?? "weekly",
        rebalance_trigger: (rebalance.trigger_type as string) ?? "calendar",
        drift_threshold: (rebalance.drift_threshold as number) ?? 0.05,
    };
}

function formToConfig(form: StrategyFormData): Record<string, unknown> {
    return {
        signals: {
            required_categories: form.required_categories,
            preferred_signals: form.preferred_signals,
            min_signal_strength: form.min_signal_strength,
            min_confidence: form.min_confidence,
            composition_logic: form.composition_logic,
            min_active_signals: form.min_active_signals,
        },
        thresholds: {
            min_case_score: form.min_case_score,
            min_opportunity_score: form.min_opportunity_score,
            min_business_quality: form.min_business_quality,
            min_uos: form.min_uos,
            max_freshness_class: form.max_freshness_class,
        },
        portfolio: {
            max_positions: form.max_positions,
            max_single_position: form.max_single_position,
            max_sector_exposure: form.max_sector_exposure,
            sizing_method: form.sizing_method,
            max_turnover: form.max_turnover,
        },
        rebalance: {
            frequency: form.rebalance_frequency,
            trigger_type: form.rebalance_trigger,
            drift_threshold: form.drift_threshold,
        },
        entry_rules: form.entry_rules,
        exit_rules: form.exit_rules,
        regime_rules: form.regime_rules,
        metadata: {
            category: form.category,
            horizon: form.horizon,
            tags: form.tags,
            benchmark: form.benchmark,
        },
    };
}

// ── Reusable UI atoms ──────────────────────────────────────────────────────

function Label({ children }: { children: React.ReactNode }) {
    return <label className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-1 block">{children}</label>;
}

function SliderField({
    label, value, min, max, step, suffix, onChange,
}: {
    label: string; value: number; min: number; max: number; step: number; suffix?: string;
    onChange: (v: number) => void;
}) {
    return (
        <div>
            <Label>{label}</Label>
            <div className="flex items-center gap-3">
                <input
                    type="range" min={min} max={max} step={step} value={value}
                    onChange={(e) => onChange(parseFloat(e.target.value))}
                    className="flex-1 accent-[#d4af37] h-1"
                />
                <span className="text-xs font-mono text-[#d4af37] min-w-[3rem] text-right">
                    {suffix === "%" ? `${(value * 100).toFixed(0)}%` : value}
                </span>
            </div>
        </div>
    );
}

function SelectField({
    label, value, options, onChange,
}: {
    label: string; value: string;
    options: { value: string; label: string }[];
    onChange: (v: string) => void;
}) {
    return (
        <div>
            <Label>{label}</Label>
            <div className="relative">
                <select
                    value={value} onChange={(e) => onChange(e.target.value)}
                    className="w-full bg-[#161b22] border border-[#30363d] px-3 py-2 pr-8 rounded-xl text-xs focus:outline-none focus:border-[#d4af37] transition-all appearance-none text-gray-300"
                >
                    {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                <ChevronDown size={12} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none" />
            </div>
        </div>
    );
}

function CheckboxGroup({
    label, options, selected, onChange,
}: {
    label: string; options: string[]; selected: string[];
    onChange: (v: string[]) => void;
}) {
    const toggle = (opt: string) => {
        onChange(selected.includes(opt) ? selected.filter((s) => s !== opt) : [...selected, opt]);
    };
    return (
        <div>
            <Label>{label}</Label>
            <div className="flex flex-wrap gap-2 mt-1">
                {options.map((opt) => (
                    <button key={opt} type="button" onClick={() => toggle(opt)}
                        className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all border ${selected.includes(opt)
                                ? "bg-[#d4af37]/15 border-[#d4af37]/40 text-[#d4af37]"
                                : "border-[#30363d] text-gray-500 hover:border-gray-500"
                            }`}
                    >
                        {selected.includes(opt) && <Check size={9} className="inline mr-1" />}
                        {opt}
                    </button>
                ))}
            </div>
        </div>
    );
}

function TextField({
    label, value, placeholder, onChange,
}: {
    label: string; value: string; placeholder?: string;
    onChange: (v: string) => void;
}) {
    return (
        <div>
            <Label>{label}</Label>
            <input type="text" value={value} placeholder={placeholder}
                onChange={(e) => onChange(e.target.value)}
                className="w-full bg-[#161b22] border border-[#30363d] px-3 py-2 rounded-xl text-xs focus:outline-none focus:border-[#d4af37] transition-all placeholder:text-gray-600 text-gray-300"
            />
        </div>
    );
}

function TextAreaField({
    label, value, placeholder, onChange,
}: {
    label: string; value: string; placeholder?: string;
    onChange: (v: string) => void;
}) {
    return (
        <div>
            <Label>{label}</Label>
            <textarea value={value} placeholder={placeholder} rows={3}
                onChange={(e) => onChange(e.target.value)}
                className="w-full bg-[#161b22] border border-[#30363d] px-3 py-2 rounded-xl text-xs focus:outline-none focus:border-[#d4af37] transition-all placeholder:text-gray-600 text-gray-300 resize-none"
            />
        </div>
    );
}

// ── Tab Content Components ─────────────────────────────────────────────────

function IdentityTab({ form, setForm }: { form: StrategyFormData; setForm: (f: StrategyFormData) => void }) {
    const [tagInput, setTagInput] = useState("");
    const addTag = () => {
        const t = tagInput.trim();
        if (t && !form.tags.includes(t)) { setForm({ ...form, tags: [...form.tags, t] }); setTagInput(""); }
    };
    return (
        <div className="space-y-4">
            <TextField label="Strategy Name" value={form.name} placeholder="e.g. Momentum Bull Strategy" onChange={(v) => setForm({ ...form, name: v })} />
            <TextAreaField label="Description" value={form.description} placeholder="Describe the strategy thesis..." onChange={(v) => setForm({ ...form, description: v })} />
            <div className="grid grid-cols-2 gap-4">
                <SelectField label="Category" value={form.category} options={CATEGORIES} onChange={(v) => setForm({ ...form, category: v })} />
                <SelectField label="Horizon" value={form.horizon} options={HORIZONS} onChange={(v) => setForm({ ...form, horizon: v })} />
            </div>
            <TextField label="Benchmark" value={form.benchmark} placeholder="SPY" onChange={(v) => setForm({ ...form, benchmark: v })} />
            {/* Tags */}
            <div>
                <Label>Tags</Label>
                <div className="flex gap-2">
                    <input type="text" value={tagInput} placeholder="Add tag..."
                        onChange={(e) => setTagInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addTag())}
                        className="flex-1 bg-[#161b22] border border-[#30363d] px-3 py-1.5 rounded-lg text-xs focus:outline-none focus:border-[#d4af37] transition-all placeholder:text-gray-600 text-gray-300"
                    />
                    <button type="button" onClick={addTag} className="px-3 py-1.5 rounded-lg text-[10px] border border-[#30363d] text-gray-400 hover:text-[#d4af37] hover:border-[#d4af37]/40 transition-all">
                        <Plus size={12} />
                    </button>
                </div>
                {form.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                        {form.tags.map((t) => (
                            <span key={t} className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#d4af37]/10 text-[#d4af37] text-[10px]">
                                {t}
                                <button onClick={() => setForm({ ...form, tags: form.tags.filter((x) => x !== t) })} className="hover:text-red-400">×</button>
                            </span>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function SignalsTab({ form, setForm }: { form: StrategyFormData; setForm: (f: StrategyFormData) => void }) {
    return (
        <div className="space-y-4">
            <CheckboxGroup label="Required Signal Categories" options={SIGNAL_CATEGORIES} selected={form.required_categories} onChange={(v) => setForm({ ...form, required_categories: v })} />
            <SelectField label="Composition Logic" value={form.composition_logic} options={COMPOSITION_LOGIC} onChange={(v) => setForm({ ...form, composition_logic: v })} />
            <div className="grid grid-cols-2 gap-4">
                <SliderField label="Min Signal Strength" value={form.min_signal_strength} min={0} max={1} step={0.05} suffix="%" onChange={(v) => setForm({ ...form, min_signal_strength: v })} />
                <SelectField label="Min Confidence" value={form.min_confidence} options={CONFIDENCE_LEVELS} onChange={(v) => setForm({ ...form, min_confidence: v })} />
            </div>
            <SliderField label="Min Active Signals" value={form.min_active_signals} min={1} max={10} step={1} onChange={(v) => setForm({ ...form, min_active_signals: v })} />
        </div>
    );
}

function ScoringTab({ form, setForm }: { form: StrategyFormData; setForm: (f: StrategyFormData) => void }) {
    return (
        <div className="space-y-4">
            <SliderField label="Min CASE Score" value={form.min_case_score} min={0} max={100} step={5} onChange={(v) => setForm({ ...form, min_case_score: v })} />
            <SliderField label="Min Opportunity Score" value={form.min_opportunity_score} min={0} max={100} step={5} onChange={(v) => setForm({ ...form, min_opportunity_score: v })} />
            <SliderField label="Min Business Quality" value={form.min_business_quality} min={0} max={100} step={5} onChange={(v) => setForm({ ...form, min_business_quality: v })} />
            <SliderField label="Min UOS (Unified Opportunity Score)" value={form.min_uos} min={0} max={100} step={5} onChange={(v) => setForm({ ...form, min_uos: v })} />
            <SelectField label="Max Freshness Class" value={form.max_freshness_class} options={[{ value: "fresh", label: "Fresh only" }, { value: "stale", label: "Accept stale" }]} onChange={(v) => setForm({ ...form, max_freshness_class: v })} />
        </div>
    );
}

function EntryRulesTab({ form, setForm }: { form: StrategyFormData; setForm: (f: StrategyFormData) => void }) {
    const addRule = () => setForm({ ...form, entry_rules: [...form.entry_rules, { field: "case_score", operator: "gte", value: 50, priority: form.entry_rules.length, label: "" }] });
    const removeRule = (i: number) => setForm({ ...form, entry_rules: form.entry_rules.filter((_, j) => j !== i) });
    const updateRule = (i: number, updates: Partial<StrategyFormData["entry_rules"][0]>) => {
        const rules = [...form.entry_rules];
        rules[i] = { ...rules[i], ...updates };
        setForm({ ...form, entry_rules: rules });
    };

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <Label>Entry Conditions</Label>
                <button type="button" onClick={addRule} className="flex items-center gap-1 px-3 py-1 rounded-lg text-[10px] border border-[#30363d] text-gray-400 hover:text-[#d4af37] hover:border-[#d4af37]/40 transition-all">
                    <Plus size={10} /> Add Rule
                </button>
            </div>
            {form.entry_rules.length === 0 && (
                <p className="text-[11px] text-gray-600 py-4 text-center">No entry rules. Strategy will accept all qualifying signals.</p>
            )}
            {form.entry_rules.map((rule, i) => (
                <div key={i} className="flex items-center gap-2 p-3 rounded-xl bg-[#161b22] border border-[#30363d]">
                    <select value={rule.field} onChange={(e) => updateRule(i, { field: e.target.value })} className="bg-transparent border border-[#30363d] rounded-lg px-2 py-1 text-[10px] text-gray-300 focus:outline-none focus:border-[#d4af37]">
                        {ENTRY_FIELDS.map((f) => <option key={f} value={f}>{f}</option>)}
                    </select>
                    <select value={rule.operator} onChange={(e) => updateRule(i, { operator: e.target.value })} className="bg-transparent border border-[#30363d] rounded-lg px-2 py-1 text-[10px] text-gray-300 focus:outline-none focus:border-[#d4af37] w-14">
                        {ENTRY_OPERATORS.map((o) => <option key={o} value={o}>{OPERATOR_LABELS[o]}</option>)}
                    </select>
                    <input type="number" value={rule.value} onChange={(e) => updateRule(i, { value: parseFloat(e.target.value) || 0 })}
                        className="bg-transparent border border-[#30363d] rounded-lg px-2 py-1 text-[10px] text-[#d4af37] font-mono w-16 focus:outline-none focus:border-[#d4af37]" />
                    <input type="text" value={rule.label} placeholder="label..." onChange={(e) => updateRule(i, { label: e.target.value })}
                        className="flex-1 bg-transparent border border-[#30363d] rounded-lg px-2 py-1 text-[10px] text-gray-400 focus:outline-none focus:border-[#d4af37] placeholder:text-gray-700" />
                    <button onClick={() => removeRule(i)} className="p-1 text-gray-600 hover:text-red-400 transition-colors"><Trash2 size={12} /></button>
                </div>
            ))}
        </div>
    );
}

function ExitRulesTab({ form, setForm }: { form: StrategyFormData; setForm: (f: StrategyFormData) => void }) {
    const addRule = () => setForm({ ...form, exit_rules: [...form.exit_rules, { rule_type: "trailing_stop", params: { pct: 0.15 } }] });
    const removeRule = (i: number) => setForm({ ...form, exit_rules: form.exit_rules.filter((_, j) => j !== i) });
    const updateRule = (i: number, updates: Partial<StrategyFormData["exit_rules"][0]>) => {
        const rules = [...form.exit_rules];
        rules[i] = { ...rules[i], ...updates };
        setForm({ ...form, exit_rules: rules });
    };

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <Label>Exit Conditions</Label>
                <button type="button" onClick={addRule} className="flex items-center gap-1 px-3 py-1 rounded-lg text-[10px] border border-[#30363d] text-gray-400 hover:text-[#d4af37] hover:border-[#d4af37]/40 transition-all">
                    <Plus size={10} /> Add Rule
                </button>
            </div>
            {form.exit_rules.length === 0 && (
                <p className="text-[11px] text-gray-600 py-4 text-center">No exit rules. Positions will be held until rebalance.</p>
            )}
            {form.exit_rules.map((rule, i) => {
                const exitType = EXIT_TYPES.find((t) => t.value === rule.rule_type) ?? EXIT_TYPES[0];
                return (
                    <div key={i} className="flex items-center gap-2 p-3 rounded-xl bg-[#161b22] border border-[#30363d]">
                        <select value={rule.rule_type} onChange={(e) => {
                            const et = EXIT_TYPES.find((t) => t.value === e.target.value);
                            updateRule(i, { rule_type: e.target.value, params: et?.param_key ? { [et.param_key]: 0.15 } : {} });
                        }} className="bg-transparent border border-[#30363d] rounded-lg px-2 py-1 text-[10px] text-gray-300 focus:outline-none focus:border-[#d4af37]">
                            {EXIT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                        </select>
                        {exitType.param_key && (
                            <>
                                <span className="text-[9px] text-gray-600">{exitType.param_label}:</span>
                                <input type="number" step="0.01"
                                    value={rule.params[exitType.param_key] ?? 0}
                                    onChange={(e) => updateRule(i, { params: { [exitType.param_key]: parseFloat(e.target.value) || 0 } })}
                                    className="bg-transparent border border-[#30363d] rounded-lg px-2 py-1 text-[10px] text-[#d4af37] font-mono w-20 focus:outline-none focus:border-[#d4af37]"
                                />
                            </>
                        )}
                        <div className="flex-1" />
                        <button onClick={() => removeRule(i)} className="p-1 text-gray-600 hover:text-red-400 transition-colors"><Trash2 size={12} /></button>
                    </div>
                );
            })}
        </div>
    );
}

function RegimeTab({ form, setForm }: { form: StrategyFormData; setForm: (f: StrategyFormData) => void }) {
    // Ensure all regimes have an entry
    const ensureAllRegimes = useCallback(() => {
        const existing = new Set(form.regime_rules.map((r) => r.regime));
        const missing = REGIMES.filter((r) => !existing.has(r));
        if (missing.length > 0) {
            setForm({
                ...form,
                regime_rules: [
                    ...form.regime_rules,
                    ...missing.map((regime) => ({ regime, action: "full_exposure", sizing_override: null })),
                ],
            });
        }
    }, [form, setForm]);

    const updateRegime = (regime: string, updates: Partial<StrategyFormData["regime_rules"][0]>) => {
        const rules = form.regime_rules.map((r) => r.regime === regime ? { ...r, ...updates } : r);
        setForm({ ...form, regime_rules: rules });
    };

    const regimeMap = Object.fromEntries(form.regime_rules.map((r) => [r.regime, r]));

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <Label>Regime Actions</Label>
                <button type="button" onClick={ensureAllRegimes} className="flex items-center gap-1 px-3 py-1 rounded-lg text-[10px] border border-[#30363d] text-gray-400 hover:text-[#d4af37] hover:border-[#d4af37]/40 transition-all">
                    <Plus size={10} /> Fill All Regimes
                </button>
            </div>
            <div className="space-y-2">
                {REGIMES.map((regime) => {
                    const rule = regimeMap[regime];
                    const colors: Record<string, string> = {
                        bull: "text-green-400", bear: "text-red-400", high_vol: "text-orange-400",
                        low_vol: "text-blue-400", range: "text-gray-400",
                    };
                    return (
                        <div key={regime} className="flex items-center gap-3 p-3 rounded-xl bg-[#161b22] border border-[#30363d]">
                            <span className={`text-xs font-bold uppercase w-20 ${colors[regime] ?? "text-gray-400"}`}>
                                {regime.replace("_", " ")}
                            </span>
                            {rule ? (
                                <>
                                    <select value={rule.action} onChange={(e) => updateRegime(regime, { action: e.target.value })}
                                        className="bg-transparent border border-[#30363d] rounded-lg px-2 py-1 text-[10px] text-gray-300 focus:outline-none focus:border-[#d4af37] flex-1">
                                        {REGIME_ACTIONS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
                                    </select>
                                    <div className="flex items-center gap-1">
                                        <span className="text-[9px] text-gray-600">Size:</span>
                                        <input type="number" step="0.01" min="0" max="1"
                                            value={rule.sizing_override ?? ""}
                                            placeholder="—"
                                            onChange={(e) => updateRegime(regime, { sizing_override: e.target.value ? parseFloat(e.target.value) : null })}
                                            className="bg-transparent border border-[#30363d] rounded-lg px-2 py-1 text-[10px] text-[#d4af37] font-mono w-14 focus:outline-none focus:border-[#d4af37] placeholder:text-gray-700"
                                        />
                                    </div>
                                </>
                            ) : (
                                <span className="text-[10px] text-gray-600 italic">Not configured</span>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function PortfolioTab({ form, setForm }: { form: StrategyFormData; setForm: (f: StrategyFormData) => void }) {
    return (
        <div className="space-y-4">
            <SelectField label="Sizing Method" value={form.sizing_method} options={SIZING_METHODS} onChange={(v) => setForm({ ...form, sizing_method: v })} />
            <SliderField label="Max Positions" value={form.max_positions} min={3} max={50} step={1} onChange={(v) => setForm({ ...form, max_positions: v })} />
            <SliderField label="Max Single Position" value={form.max_single_position} min={0.02} max={0.30} step={0.01} suffix="%" onChange={(v) => setForm({ ...form, max_single_position: v })} />
            <SliderField label="Max Sector Exposure" value={form.max_sector_exposure} min={0.10} max={0.50} step={0.05} suffix="%" onChange={(v) => setForm({ ...form, max_sector_exposure: v })} />
            <SliderField label="Max Turnover per Rebalance" value={form.max_turnover} min={0.10} max={1.0} step={0.05} suffix="%" onChange={(v) => setForm({ ...form, max_turnover: v })} />
        </div>
    );
}

function RebalanceTab({ form, setForm }: { form: StrategyFormData; setForm: (f: StrategyFormData) => void }) {
    return (
        <div className="space-y-4">
            <SelectField label="Frequency" value={form.rebalance_frequency} options={REBALANCE_FREQUENCIES} onChange={(v) => setForm({ ...form, rebalance_frequency: v })} />
            <SelectField label="Trigger Type" value={form.rebalance_trigger} options={REBALANCE_TRIGGERS} onChange={(v) => setForm({ ...form, rebalance_trigger: v })} />
            {form.rebalance_trigger === "drift_based" && (
                <SliderField label="Drift Threshold" value={form.drift_threshold} min={0.01} max={0.20} step={0.01} suffix="%" onChange={(v) => setForm({ ...form, drift_threshold: v })} />
            )}
        </div>
    );
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function StrategyBuilder({
    strategyId,
    initialConfig,
    onBack,
    onSave,
    onRunBacktest,
}: StrategyBuilderProps) {
    const [activeTab, setActiveTab] = useState<BuilderTab>("identity");
    const [form, setForm] = useState<StrategyFormData>(() => defaultForm(initialConfig));
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    const handleSave = useCallback(async () => {
        if (!form.name.trim()) return;
        setSaving(true);
        setSaved(false);
        try {
            const config = formToConfig(form);
            const id = await onSave(form.name, form.description, config);
            if (id) { setSaved(true); setTimeout(() => setSaved(false), 2000); }
        } finally {
            setSaving(false);
        }
    }, [form, onSave]);

    const handleRunBacktest = useCallback(() => {
        if (strategyId) onRunBacktest(strategyId);
    }, [strategyId, onRunBacktest]);

    // Tab completeness indicators
    const tabStatus: Record<BuilderTab, boolean> = {
        identity: !!form.name.trim(),
        signals: form.required_categories.length > 0,
        scoring: form.min_case_score > 0 || form.min_opportunity_score > 0,
        entry: form.entry_rules.length > 0,
        exit: form.exit_rules.length > 0,
        regime: form.regime_rules.length > 0,
        portfolio: true,
        rebalance: true,
    };

    return (
        <div className="space-y-4">
            {/* ── Toolbar ── */}
            <div className="flex items-center justify-between">
                <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-[#d4af37] transition-colors">
                    <ArrowLeft size={14} /> Back to Lab
                </button>
                <div className="flex gap-2">
                    <button onClick={handleSave} disabled={saving || !form.name.trim()}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold border border-[#d4af37]/40 text-[#d4af37] hover:bg-[#d4af37]/10 transition-all disabled:opacity-40">
                        {saving ? <RefreshCw size={12} className="animate-spin" /> : saved ? <Check size={12} /> : <Save size={12} />}
                        {saved ? "Saved!" : "Save"}
                    </button>
                    {strategyId && (
                        <button onClick={handleRunBacktest}
                            className="flex items-center gap-1.5 bg-gradient-to-r from-[#d4af37] to-[#e8c84a] text-black font-bold px-4 py-2 rounded-xl text-xs hover:brightness-110 transition-all">
                            <Play size={12} /> Run Backtest
                        </button>
                    )}
                </div>
            </div>

            {/* ── 8-Tab Navigation ── */}
            <div className="flex gap-1 p-1 glass-card border-[#30363d] rounded-xl overflow-x-auto">
                {BUILDER_TABS.map((tab) => (
                    <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                        className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[8px] font-bold uppercase tracking-widest transition-all whitespace-nowrap ${activeTab === tab.id
                                ? "bg-[#d4af37]/15 text-[#d4af37] border border-[#d4af37]/30"
                                : "text-gray-500 hover:text-gray-300 hover:bg-white/5"
                            }`}
                    >
                        {tab.icon}
                        {tab.label}
                        {tabStatus[tab.id] && <span className="w-1.5 h-1.5 rounded-full bg-green-400/80 ml-0.5" />}
                    </button>
                ))}
            </div>

            {/* ── Tab Content ── */}
            <div className="glass-card border-[#30363d] rounded-2xl p-5">
                {activeTab === "identity" && <IdentityTab form={form} setForm={setForm} />}
                {activeTab === "signals" && <SignalsTab form={form} setForm={setForm} />}
                {activeTab === "scoring" && <ScoringTab form={form} setForm={setForm} />}
                {activeTab === "entry" && <EntryRulesTab form={form} setForm={setForm} />}
                {activeTab === "exit" && <ExitRulesTab form={form} setForm={setForm} />}
                {activeTab === "regime" && <RegimeTab form={form} setForm={setForm} />}
                {activeTab === "portfolio" && <PortfolioTab form={form} setForm={setForm} />}
                {activeTab === "rebalance" && <RebalanceTab form={form} setForm={setForm} />}
            </div>

            {/* ── Validation warnings ── */}
            {!form.name.trim() && (
                <div className="flex items-center gap-2 text-[11px] text-yellow-500/80">
                    <AlertTriangle size={12} />
                    Strategy needs a name before saving.
                </div>
            )}
        </div>
    );
}
