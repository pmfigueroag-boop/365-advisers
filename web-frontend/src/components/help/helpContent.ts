/**
 * helpContent.ts
 * ──────────────────────────────────────────────────────────────────────────
 * Central Help Content Registry — single source of truth for all
 * contextual help text in the IDEA module.
 *
 * Usage:
 *   import { HELP } from "@/components/help/helpContent";
 *   <HelpTooltip topic="signal_strength" />
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export interface HelpEntry {
    title: string;
    description: string;
    extended?: string;
    category?: "metric" | "detector" | "control" | "column" | "universe" | "filter" | "ranking";
    related?: string[];
}

// ─── Registry ─────────────────────────────────────────────────────────────────

export const HELP: Record<string, HelpEntry> = {

    // ── Signal Metrics ────────────────────────────────────────────────────

    signal_strength: {
        title: "Signal Strength",
        description: "Measures the immediate intensity of the detected signal (0–100%).",
        extended:
            "Higher values indicate stronger technical or fundamental signals at the moment of detection. " +
            "A 100% reading means every sub-signal in the detector fired. " +
            "Use this to gauge how clear and actionable the opportunity is right now.",
        category: "metric",
        related: ["confidence_score", "priority_rank"],
    },

    confidence_score: {
        title: "Reliability",
        description: "How trustworthy this idea is, based on signal confirmation quality (0–100%).",
        extended:
            "Reliability increases when multiple strong signals align. It is independent from signal strength — " +
            "an idea can be strong but unreliable (e.g., based on a single volatile data point), or weak but " +
            "highly reliable (e.g., confirmed across many indicators). High reliability (>80%) means the detection " +
            "is well-confirmed.",
        category: "metric",
        related: ["signal_strength", "confidence_level"],
    },

    confidence_level: {
        title: "Confidence Level",
        description: "Categorical assessment of idea confidence: High, Medium, or Low.",
        extended:
            "HIGH (≥60% of signals activated) — strong probability. " +
            "MEDIUM (40–60%) — moderate, validate with a full analysis. " +
            "LOW (<40%) — weak signal, treat as exploratory.",
        category: "metric",
        related: ["confidence_score", "signal_strength"],
    },

    alpha_score: {
        title: "Alpha Score",
        description: "Composite attractiveness score combining multiple signal dimensions.",
        extended:
            "The Alpha Score integrates the CASE (Composite Alpha Score Engine) output when available. " +
            "It blends signal strength, confidence, and market regime relevance to estimate the overall " +
            "potential of the idea. Higher alpha scores indicate opportunities with better risk-adjusted potential.",
        category: "metric",
        related: ["signal_strength", "confidence_score"],
    },

    priority_rank: {
        title: "Priority Rank",
        description: "Position in the opportunity ranking (#1 = best).",
        extended:
            "Ideas are ranked by a weighted composite of signal strength, confidence score, and a multi-detector " +
            "bonus. When the same ticker triggers multiple detectors (signal confluence), it receives a ranking " +
            "boost because the opportunity is confirmed across independent evaluation dimensions.",
        category: "ranking",
        related: ["multi_detector_bonus", "ranking_formula"],
    },

    // ── Detectors ─────────────────────────────────────────────────────────

    detector_value: {
        title: "Value Detector",
        description: "Identifies undervalued assets using fundamental ratios.",
        extended:
            "Evaluates P/E, EV/EBITDA, P/B, and Free Cash Flow yield against sector benchmarks and historical " +
            "averages. Strong signal when ≥3 of 4 metrics are below thresholds, indicating a fundamental " +
            "discount relative to intrinsic value.",
        category: "detector",
    },

    detector_quality: {
        title: "Quality Detector",
        description: "Detects high-quality businesses with strong competitive moats.",
        extended:
            "Measures ROIC, operating margins, earnings quality, ROE, and leverage. Strong signal when " +
            "ROIC >15%, margins are expanding, and D/E <0.5. Indicates durable competitive advantage " +
            "and franchise value.",
        category: "detector",
    },

    detector_growth: {
        title: "Growth Detector",
        description: "Spots companies with accelerating revenue and earnings growth.",
        extended:
            "Evaluates revenue growth rate, earnings momentum, and return on invested capital trajectory. " +
            "Strong signal when both revenue and earnings growth exceed market averages with improving margins. " +
            "Captures companies in a positive inflection.",
        category: "detector",
    },

    detector_momentum: {
        title: "Momentum Detector",
        description: "Identifies assets with confirmed positive price momentum.",
        extended:
            "Technical signals: Golden Cross (SMA50 > SMA200), RSI in the 50–70 sweet spot, positive MACD, " +
            "high relative volume, and price trading above EMA20. Strong signal indicates a confirmed uptrend " +
            "supported by multiple technical indicators.",
        category: "detector",
    },

    detector_reversal: {
        title: "Reversal Detector",
        description: "Detects potential trend reversals after excessive selloffs.",
        extended:
            "Looks for oversold RSI (<30), low stochastic readings, price near the lower Bollinger Band, and " +
            "volume capitulation patterns. Requires minimum 2 confirming signals. Higher risk profile — " +
            "potential bounce after extreme market pessimism.",
        category: "detector",
    },

    detector_event: {
        title: "Event Detector",
        description: "Captures catalyst-driven opportunities and regime changes.",
        extended:
            "Detects significant score changes between analyses, earnings surprises, revenue acceleration, " +
            "volatility squeezes, and high-beta setups. Captures events that historically precede meaningful " +
            "price moves. Best used to complement other detectors.",
        category: "detector",
    },

    // ── Table Columns ─────────────────────────────────────────────────────

    col_rank: {
        title: "Rank (#)",
        description: "Position in the Opportunity Ranking, sorted by composite score.",
        category: "column",
    },

    col_ticker: {
        title: "Ticker",
        description: "The stock symbol and company name. Click any row to preview details.",
        category: "column",
    },

    col_strategy: {
        title: "Strategy",
        description: "The detector type that generated this idea (Value, Quality, Growth, etc.).",
        extended:
            "A single ticker can appear multiple times if several detectors fire independently. " +
            "This signal confluence indicates a stronger opportunity.",
        category: "column",
    },

    col_confidence: {
        title: "Confidence",
        description: "Categorical confidence: High (≥60%), Medium (40–60%), or Low (<40%).",
        category: "column",
    },

    col_strength: {
        title: "Strength",
        description: "Percentage of the detector's sub-signals that fired (0–100%).",
        category: "column",
    },

    col_reliability: {
        title: "Reliability",
        description: "How well-confirmed the detection is, based on signal quality (0–100%).",
        category: "column",
        related: ["confidence_score"],
    },

    col_actions: {
        title: "Actions",
        description: "Analyze = run full Investment Committee pipeline. ✕ = dismiss from list.",
        category: "column",
    },

    // ── Scan Controls ─────────────────────────────────────────────────────

    scan_universe: {
        title: "Universe Scan",
        description: "Auto-discovers 300+ tickers from multiple sources and scans for opportunities.",
        extended:
            "The engine discovers tickers from S&P 500, NASDAQ 100, sector leaders, your portfolio, " +
            "and recent strong ideas. After deduplication, all discovered tickers are evaluated by every " +
            "active detector in parallel. Typical scan takes 10–30 seconds.",
        category: "control",
        related: ["scan_watchlist", "universe_discovery"],
    },

    scan_watchlist: {
        title: "Scan Watchlist",
        description: "Scans only the tickers in your current watchlist.",
        extended:
            "Faster than a Universe Scan because it evaluates a smaller set of tickers. Best for " +
            "monitoring positions you already track.",
        category: "control",
        related: ["scan_universe"],
    },

    // ── Universe Discovery ────────────────────────────────────────────────

    universe_discovery: {
        title: "Universe Discovery",
        description: "Autonomous system that discovers which tickers to scan.",
        extended:
            "Uses 6 pluggable providers: Static Index (S&P 500, NASDAQ 100), Screener (market cap filter), " +
            "Sector Rotation (11 GICS sectors), Portfolio (your positions), Idea History (recent strong ideas), " +
            "and Custom (user watchlist). Results are deduplicated and capped to avoid overload.",
        category: "universe",
    },

    source_breakdown: {
        title: "Source Breakdown",
        description: "Shows how many tickers came from each universe source after a scan.",
        extended:
            "The green dots indicate active sources. Numbers show ticker count per source. " +
            "'Found → unique' shows total before and after deduplication. The time in ms is discovery latency.",
        category: "universe",
    },

    // ── Filters ───────────────────────────────────────────────────────────

    filter_strategy: {
        title: "Strategy Filter",
        description: "Show only ideas from a specific detector type.",
        extended:
            "Click a strategy chip to filter. Click again to clear. Useful when scanning for " +
            "a particular investment style (e.g., only Value opportunities).",
        category: "filter",
    },

    filter_sort: {
        title: "Sort Order",
        description: "Sort by Score (default, strongest first) or by Ticker (alphabetical).",
        category: "filter",
    },

    filter_search: {
        title: "Ticker Search",
        description: "Filter the ranking table by ticker symbol. Type to filter in real-time.",
        category: "filter",
    },

    // ── Ranking ───────────────────────────────────────────────────────────

    opportunity_ranking: {
        title: "Opportunity Ranking",
        description: "Ranked list of investment ideas sorted by composite attractiveness score.",
        extended:
            "Each idea is scored by: signal_strength × weight_strength + confidence_score × weight_confidence. " +
            "Tickers that fire across multiple detectors receive a ranking bonus (signal confluence). " +
            "#1 = the strongest opportunity in the current scan.",
        category: "ranking",
    },

    multi_detector_bonus: {
        title: "Multi-Detector Bonus",
        description: "Ranking boost when the same ticker triggers multiple independent detectors.",
        extended:
            "If AAPL triggers Value, Quality, and Momentum detectors, each idea is individually ranked, " +
            "but a confluence bonus reflects that the opportunity is confirmed across independent dimensions. " +
            "Strong confluence is one of the most reliable signals in the system.",
        category: "ranking",
    },

    // ── Preview Panel ─────────────────────────────────────────────────────

    preview_detected_by: {
        title: "Detected By",
        description: "The specific detector that generated this idea.",
        category: "metric",
    },

    preview_signals: {
        title: "Key Signals",
        description: "The individual sub-signals that fired within the detector.",
        extended:
            "Each signal has a strength level: Strong (high confidence), Moderate (partial confirmation), " +
            "or Weak (marginal signal). More strong signals = higher reliability score.",
        category: "metric",
    },

    preview_strength: {
        title: "Signal Strength",
        description: "Percentage of detector sub-signals that confirmed the opportunity.",
        category: "metric",
        related: ["signal_strength"],
    },
};

// ─── Lookup helper ────────────────────────────────────────────────────────────

const FALLBACK: HelpEntry = {
    title: "Help",
    description: "No additional information available for this topic.",
};

/** Safe lookup — never throws, returns fallback for unknown keys. */
export function getHelp(topic: string): HelpEntry {
    return HELP[topic] ?? FALLBACK;
}
