'use client';

import React, { useState, useCallback } from 'react';

// ── Types ───────────────────────────────────────────────────────────────────

interface RegimeFactor {
    name: string;
    value: number | null;
    signal: string;
    weight: number;
    description: string;
}

interface RegimeClassification {
    regime: string;
    confidence: number;
    probabilities: Record<string, number>;
    contributing_factors: RegimeFactor[];
    summary: string;
}

interface DetectedOpportunity {
    ticker: string;
    opportunity_type: string;
    alpha_score: number;
    confidence: number;
    signals: string[];
    justification: string;
    regime_alignment: string;
}

interface SuggestedPosition {
    ticker: string;
    weight: number;
    justification: string;
    factor_exposures: Record<string, number>;
}

interface PortfolioSuggestion {
    style: string;
    positions: SuggestedPosition[];
    rationale: string;
    expected_return_profile: string;
    risk_level: string;
    regime_suitability: string;
}

interface RiskAlert {
    alert_type: string;
    severity: string;
    title: string;
    description: string;
    affected_tickers: string[];
    metrics: Record<string, number>;
    source_signals: string[];
}

interface InvestmentInsight {
    what_happened: string;
    why_it_happened: string;
    what_it_means: string;
    category: string;
    confidence: number;
    related_tickers: string[];
    factors_used: string[];
}

interface BrainDashboard {
    regime: RegimeClassification;
    opportunities: DetectedOpportunity[];
    portfolios: PortfolioSuggestion[];
    risk_alerts: RiskAlert[];
    insights: InvestmentInsight[];
    asset_count: number;
    analysis_timestamp: string;
}

// ── Demo Data ───────────────────────────────────────────────────────────────

const DEMO_DATA: BrainDashboard = {
    regime: {
        regime: 'expansion',
        confidence: 0.72,
        probabilities: {
            expansion: 0.42, slowdown: 0.18, recession: 0.05,
            recovery: 0.15, high_volatility: 0.08, liquidity_expansion: 0.12,
        },
        contributing_factors: [
            { name: 'GDP Growth', value: 2.8, signal: 'bullish', weight: 0.2, description: 'Strong growth at 2.8%' },
            { name: 'Inflation', value: 3.1, signal: 'neutral', weight: 0.15, description: 'Moderate inflation at 3.1%' },
            { name: 'VIX', value: 16.2, signal: 'bullish', weight: 0.15, description: 'Low volatility — VIX at 16.2' },
            { name: 'PMI', value: 56.3, signal: 'bullish', weight: 0.1, description: 'Expansionary PMI at 56.3' },
            { name: 'Unemployment', value: 3.7, signal: 'bullish', weight: 0.1, description: 'Low unemployment at 3.7%' },
        ],
        summary: 'Economy in expansion phase with strong growth and favorable conditions. Key drivers: GDP Growth, VIX, PMI.',
    },
    opportunities: [
        { ticker: 'NVDA', opportunity_type: 'momentum_breakout', alpha_score: 88.5, confidence: 0.82, signals: ['Momentum factor: 91', 'Composite Alpha: 88.5'], justification: 'NVDA exhibiting momentum breakout with strong trend confirmation.', regime_alignment: 'Aligned with expansion regime' },
        { ticker: 'AAPL', opportunity_type: 'macro_aligned', alpha_score: 82.3, confidence: 0.78, signals: ['Sector Technology favored in expansion regime', 'Alpha tier: strong_alpha'], justification: 'AAPL in Technology sector is well-positioned for the current expansion regime.', regime_alignment: 'Strong alignment with expansion' },
        { ticker: 'JPM', opportunity_type: 'undervalued', alpha_score: 76.1, confidence: 0.71, signals: ['Value factor score: 74', 'Composite Alpha: 76'], justification: 'JPM shows deep value characteristics with strong financials.', regime_alignment: 'Aligned with expansion regime' },
        { ticker: 'TSLA', opportunity_type: 'sentiment_driven', alpha_score: 71.8, confidence: 0.65, signals: ['Sentiment score: 62 (bullish)', 'Polarity: 0.58'], justification: 'TSLA experiencing significant bullish sentiment shift.', regime_alignment: 'Neutral' },
        { ticker: 'META', opportunity_type: 'event_catalyst', alpha_score: 69.4, confidence: 0.68, signals: ['Event score: 55', 'Bullish events: 3'], justification: 'META has 3 bullish corporate events creating a catalyst-driven opportunity.', regime_alignment: 'Aligned' },
    ],
    portfolios: [
        {
            style: 'growth', positions: [
                { ticker: 'NVDA', weight: 0.25, justification: 'Strong momentum breakout', factor_exposures: { momentum: 0.9, value: 0.1, volatility: 0.4 } },
                { ticker: 'AAPL', weight: 0.20, justification: 'Macro-aligned alpha leader', factor_exposures: { macro: 0.8, quality: 0.4, value: 0.3 } },
                { ticker: 'MSFT', weight: 0.18, justification: 'Quality growth with strong earnings', factor_exposures: { quality: 0.8, momentum: 0.5 } },
                { ticker: 'TSLA', weight: 0.15, justification: 'Sentiment-driven momentum', factor_exposures: { sentiment: 0.8, momentum: 0.5 } },
                { ticker: 'AMZN', weight: 0.12, justification: 'Cloud growth catalyst', factor_exposures: { momentum: 0.6, value: 0.3 } },
                { ticker: 'META', weight: 0.10, justification: 'Event catalyst play', factor_exposures: { event: 0.9, value: 0.3 } },
            ],
            rationale: 'Targets high-momentum, innovative companies with strong alpha scores.',
            expected_return_profile: 'High growth potential (12-20% expected).',
            risk_level: 'moderate',
            regime_suitability: 'Highly Suitable',
        },
        {
            style: 'value', positions: [
                { ticker: 'JPM', weight: 0.22, justification: 'Deep value financial', factor_exposures: { value: 0.8, quality: 0.5 } },
                { ticker: 'BRK.B', weight: 0.20, justification: 'Conglomerate discount', factor_exposures: { value: 0.9, quality: 0.7 } },
                { ticker: 'JNJ', weight: 0.18, justification: 'Healthcare value', factor_exposures: { value: 0.7, quality: 0.6 } },
                { ticker: 'PFE', weight: 0.15, justification: 'Pharma deep value', factor_exposures: { value: 0.85 } },
                { ticker: 'BAC', weight: 0.13, justification: 'Banking value play', factor_exposures: { value: 0.75, macro: 0.3 } },
                { ticker: 'CVX', weight: 0.12, justification: 'Energy value', factor_exposures: { value: 0.7, macro: 0.4 } },
            ],
            rationale: 'Focuses on undervalued companies with strong fundamentals.',
            expected_return_profile: 'Moderate returns with margin of safety.',
            risk_level: 'low',
            regime_suitability: 'Suitable',
        },
        {
            style: 'income', positions: [
                { ticker: 'VZ', weight: 0.20, justification: 'High yield telecom', factor_exposures: { value: 0.6 } },
                { ticker: 'O', weight: 0.20, justification: 'Monthly dividend REIT', factor_exposures: { value: 0.5, quality: 0.4 } },
                { ticker: 'ABBV', weight: 0.18, justification: 'Pharma dividend growth', factor_exposures: { quality: 0.6, value: 0.4 } },
                { ticker: 'T', weight: 0.15, justification: 'High yield telecom', factor_exposures: { value: 0.5 } },
                { ticker: 'XOM', weight: 0.15, justification: 'Energy dividend', factor_exposures: { value: 0.5, macro: 0.3 } },
                { ticker: 'KO', weight: 0.12, justification: 'Consumer staple dividend aristocrat', factor_exposures: { quality: 0.8 } },
            ],
            rationale: 'Prioritises stable, dividend-paying companies.',
            expected_return_profile: 'Stable income (4-6% yield).',
            risk_level: 'low',
            regime_suitability: 'Moderate',
        },
        {
            style: 'defensive', positions: [
                { ticker: 'JNJ', weight: 0.22, justification: 'Healthcare defensive quality', factor_exposures: { quality: 0.9, value: 0.4 } },
                { ticker: 'PG', weight: 0.20, justification: 'Consumer staple moat', factor_exposures: { quality: 0.85 } },
                { ticker: 'WMT', weight: 0.18, justification: 'Retail defensive', factor_exposures: { quality: 0.7, value: 0.3 } },
                { ticker: 'UNH', weight: 0.15, justification: 'Healthcare leader', factor_exposures: { quality: 0.8, momentum: 0.3 } },
                { ticker: 'KO', weight: 0.13, justification: 'Dividend aristocrat', factor_exposures: { quality: 0.75 } },
                { ticker: 'NEE', weight: 0.12, justification: 'Utility defensive', factor_exposures: { value: 0.5, quality: 0.4 } },
            ],
            rationale: 'Low-volatility, high-quality companies for capital preservation.',
            expected_return_profile: 'Capital preservation focus.',
            risk_level: 'low',
            regime_suitability: 'Not Recommended',
        },
        {
            style: 'opportunistic', positions: [
                { ticker: 'META', weight: 0.25, justification: 'Event catalyst play', factor_exposures: { event: 0.9, momentum: 0.4 } },
                { ticker: 'TSLA', weight: 0.22, justification: 'Sentiment-driven momentum', factor_exposures: { sentiment: 0.8, momentum: 0.5 } },
                { ticker: 'NVDA', weight: 0.20, justification: 'AI momentum play', factor_exposures: { momentum: 0.9, sentiment: 0.5 } },
                { ticker: 'COIN', weight: 0.18, justification: 'Crypto proxy', factor_exposures: { sentiment: 0.7, volatility: 0.6 } },
                { ticker: 'PLTR', weight: 0.15, justification: 'Government AI contracts', factor_exposures: { event: 0.6, momentum: 0.5 } },
            ],
            rationale: 'Event-driven and sentiment-powered plays for higher alpha.',
            expected_return_profile: 'High asymmetry potential.',
            risk_level: 'elevated',
            regime_suitability: 'Suitable',
        },
    ],
    risk_alerts: [
        { alert_type: 'sector_overheating', severity: 'moderate', title: 'Technology Sector Overheating', description: 'Technology has 4 high-alpha assets (avg score 78). Concentrated momentum increases drawdown risk.', affected_tickers: ['NVDA', 'AAPL', 'MSFT', 'META'], metrics: { sector_avg_alpha: 78, high_alpha_count: 4 }, source_signals: ['Technology concentration'] },
        { alert_type: 'drawdown_warning', severity: 'low', title: 'Moderately Elevated Put/Call Ratio', description: 'Put/Call ratio at 1.2 suggests above-average hedging activity.', affected_tickers: [], metrics: { put_call_ratio: 1.2 }, source_signals: ['PCR=1.2'] },
    ],
    insights: [
        { what_happened: 'Market regime classified as expansion with 72% confidence.', why_it_happened: 'Strong economic growth supports risk assets and cyclical sectors.', what_it_means: 'Consider overweighting equities, particularly technology and industrials. Reduce defensive allocations.', category: 'regime', confidence: 0.72, related_tickers: [], factors_used: ['GDP Growth', 'VIX', 'PMI'] },
        { what_happened: 'NVDA identified as top opportunity (Alpha Score: 89, Type: momentum_breakout).', why_it_happened: 'Momentum factor: 91 | Composite Alpha: 88.5', what_it_means: 'NVDA exhibiting momentum breakout with strong trend confirmation.', category: 'opportunity', confidence: 0.82, related_tickers: ['NVDA'], factors_used: ['Momentum factor', 'Composite Alpha'] },
        { what_happened: 'Overall market sentiment is optimistic (average score: 35). 8 bullish, 2 bearish.', why_it_happened: 'Composite sentiment across 12 assets reflects current market psychology.', what_it_means: 'Positive sentiment supports current trends but monitor for signs of excess.', category: 'sentiment', confidence: 0.65, related_tickers: [], factors_used: ['Sentiment composite score', 'Polarity analysis'] },
        { what_happened: 'Goldilocks conditions: GDP at 2.8% with controlled inflation at 3.1%.', why_it_happened: 'Strong growth with stable prices supports corporate earnings and risk appetite.', what_it_means: 'Favorable for equities. Growth and quality factors typically outperform in this environment.', category: 'macro', confidence: 0.7, related_tickers: [], factors_used: ['GDP=2.8%', 'CPI=3.1%'] },
    ],
    asset_count: 25,
    analysis_timestamp: new Date().toISOString(),
};

// ── Utility Components ──────────────────────────────────────────────────────

const REGIME_COLORS: Record<string, string> = {
    expansion: '#22c55e',
    slowdown: '#eab308',
    recession: '#ef4444',
    recovery: '#3b82f6',
    high_volatility: '#f97316',
    liquidity_expansion: '#a855f7',
};

const SEVERITY_COLORS: Record<string, string> = {
    critical: '#ef4444',
    high: '#f97316',
    moderate: '#eab308',
    low: '#6b7280',
};

const SUITABILITY_COLORS: Record<string, string> = {
    'Highly Suitable': '#22c55e',
    'Suitable': '#3b82f6',
    'Moderate': '#eab308',
    'Not Recommended': '#ef4444',
};

const OPP_TYPE_LABELS: Record<string, string> = {
    undervalued: '💎 Undervalued',
    momentum_breakout: '🚀 Momentum',
    sentiment_driven: '📊 Sentiment',
    macro_aligned: '🌎 Macro',
    event_catalyst: '⚡ Event',
};

const CATEGORY_ICONS: Record<string, string> = {
    regime: '🌐',
    opportunity: '🎯',
    risk: '⚠️',
    sentiment: '📈',
    macro: '🏛️',
};

function ConfidenceBar({ value, color = '#d4a017' }: { value: number; color?: string }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ width: `${value * 100}%`, height: '100%', background: color, borderRadius: '3px', transition: 'width 0.5s ease' }} />
            </div>
            <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', minWidth: '32px', textAlign: 'right' }}>{(value * 100).toFixed(0)}%</span>
        </div>
    );
}

// ── Tab Components ──────────────────────────────────────────────────────────

function RegimeTab({ regime }: { regime: RegimeClassification }) {
    const color = REGIME_COLORS[regime.regime] || '#888';
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Hero Badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px', padding: '24px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px' }}>
                <div style={{ width: '80px', height: '80px', borderRadius: '50%', background: `${color}15`, border: `3px solid ${color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '28px', fontWeight: 700, color, flexShrink: 0 }}>
                    {regime.regime.slice(0, 2).toUpperCase()}
                </div>
                <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '24px', fontWeight: 700, color, textTransform: 'uppercase', letterSpacing: '1px' }}>{regime.regime.replace('_', ' ')}</div>
                    <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.5)', marginTop: '4px' }}>Confidence: {(regime.confidence * 100).toFixed(0)}%</div>
                    <div style={{ marginTop: '8px' }}><ConfidenceBar value={regime.confidence} color={color} /></div>
                </div>
            </div>

            {/* Summary */}
            <div style={{ padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', fontSize: '14px', lineHeight: '1.6', color: 'rgba(255,255,255,0.7)' }}>
                {regime.summary}
            </div>

            {/* Regime Probabilities */}
            <div>
                <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'rgba(255,255,255,0.8)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Regime Probabilities</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '8px' }}>
                    {Object.entries(regime.probabilities).sort((a, b) => b[1] - a[1]).map(([r, p]) => (
                        <div key={r} style={{ padding: '12px', background: regime.regime === r ? `${REGIME_COLORS[r] || '#888'}10` : 'rgba(255,255,255,0.02)', border: `1px solid ${regime.regime === r ? (REGIME_COLORS[r] || '#888') + '40' : 'rgba(255,255,255,0.05)'}`, borderRadius: '8px' }}>
                            <div style={{ fontSize: '12px', color: REGIME_COLORS[r] || '#888', fontWeight: 600, textTransform: 'uppercase' }}>{r.replace('_', ' ')}</div>
                            <ConfidenceBar value={p} color={REGIME_COLORS[r] || '#888'} />
                        </div>
                    ))}
                </div>
            </div>

            {/* Contributing Factors */}
            <div>
                <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'rgba(255,255,255,0.8)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Contributing Factors</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {regime.contributing_factors.map((f, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                            <span style={{ fontSize: '18px' }}>{f.signal === 'bullish' ? '🟢' : f.signal === 'bearish' ? '🔴' : '🟡'}</span>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: '13px', fontWeight: 600, color: 'rgba(255,255,255,0.85)' }}>{f.name}</div>
                                <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.5)' }}>{f.description}</div>
                            </div>
                            {f.value !== null && <span style={{ fontSize: '14px', fontWeight: 600, color: 'rgba(255,255,255,0.9)', fontFamily: 'var(--font-mono, monospace)' }}>{f.value.toFixed(1)}</span>}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

function OpportunityTab({ opportunities }: { opportunities: DetectedOpportunity[] }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '12px' }}>
                {opportunities.map((o, i) => (
                    <div key={i} style={{ padding: '20px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px', transition: 'border-color 0.2s', cursor: 'default' }}
                        onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(212,160,23,0.3)')}
                        onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)')}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <span style={{ fontSize: '18px', fontWeight: 700, color: '#d4a017' }}>{o.ticker}</span>
                                <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: 'rgba(212,160,23,0.15)', color: '#d4a017' }}>{OPP_TYPE_LABELS[o.opportunity_type] || o.opportunity_type}</span>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                                <div style={{ fontSize: '20px', fontWeight: 700, color: '#d4a017' }}>{o.alpha_score.toFixed(0)}</div>
                                <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Alpha</div>
                            </div>
                        </div>
                        <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.6)', lineHeight: '1.5', marginBottom: '12px' }}>{o.justification}</div>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                            {o.signals.map((s, j) => (
                                <span key={j} style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '3px', background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.5)' }}>{s}</span>
                            ))}
                        </div>
                        <ConfidenceBar value={o.confidence} />
                    </div>
                ))}
            </div>
        </div>
    );
}

function PortfolioTab({ portfolios }: { portfolios: PortfolioSuggestion[] }) {
    const [selected, setSelected] = useState(0);
    const portfolio = portfolios[selected];

    if (!portfolio) return null;

    const styleEmoji: Record<string, string> = { growth: '🚀', value: '💎', income: '💰', defensive: '🛡️', opportunistic: '⚡' };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Style selector */}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {portfolios.map((p, i) => (
                    <button key={p.style} onClick={() => setSelected(i)} style={{
                        padding: '8px 16px', borderRadius: '8px', border: `1px solid ${selected === i ? '#d4a017' : 'rgba(255,255,255,0.08)'}`,
                        background: selected === i ? 'rgba(212,160,23,0.12)' : 'rgba(255,255,255,0.02)', color: selected === i ? '#d4a017' : 'rgba(255,255,255,0.6)',
                        cursor: 'pointer', fontSize: '13px', fontWeight: 600, textTransform: 'uppercase', transition: 'all 0.2s',
                    }}>
                        {styleEmoji[p.style] || '📊'} {p.style}
                    </button>
                ))}
            </div>

            {/* Portfolio card */}
            <div style={{ padding: '20px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div>
                        <span style={{ fontSize: '18px', fontWeight: 700, color: '#d4a017', textTransform: 'uppercase' }}>{styleEmoji[portfolio.style]} {portfolio.style} Portfolio</span>
                        <span style={{ marginLeft: '12px', fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: `${SUITABILITY_COLORS[portfolio.regime_suitability] || '#888'}20`, color: SUITABILITY_COLORS[portfolio.regime_suitability] || '#888' }}>{portfolio.regime_suitability}</span>
                    </div>
                    <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: portfolio.risk_level === 'low' ? 'rgba(34,197,94,0.15)' : portfolio.risk_level === 'elevated' ? 'rgba(239,68,68,0.15)' : 'rgba(234,179,8,0.15)', color: portfolio.risk_level === 'low' ? '#22c55e' : portfolio.risk_level === 'elevated' ? '#ef4444' : '#eab308' }}>
                        Risk: {portfolio.risk_level}
                    </span>
                </div>
                <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.5)', marginBottom: '8px' }}>{portfolio.rationale}</div>
                <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.4)', marginBottom: '16px', fontStyle: 'italic' }}>{portfolio.expected_return_profile}</div>

                {/* Positions table */}
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                            <th style={{ textAlign: 'left', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Asset</th>
                            <th style={{ textAlign: 'right', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Weight</th>
                            <th style={{ textAlign: 'left', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Justification</th>
                            <th style={{ textAlign: 'left', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Factor Exposures</th>
                        </tr>
                    </thead>
                    <tbody>
                        {portfolio.positions.map((p, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                <td style={{ padding: '10px 12px', fontSize: '14px', fontWeight: 700, color: '#d4a017' }}>{p.ticker}</td>
                                <td style={{ padding: '10px 12px', fontSize: '14px', fontWeight: 600, color: 'rgba(255,255,255,0.9)', textAlign: 'right', fontFamily: 'var(--font-mono, monospace)' }}>{(p.weight * 100).toFixed(1)}%</td>
                                <td style={{ padding: '10px 12px', fontSize: '12px', color: 'rgba(255,255,255,0.5)', maxWidth: '250px' }}>{p.justification}</td>
                                <td style={{ padding: '10px 12px' }}>
                                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                        {Object.entries(p.factor_exposures).map(([f, v]) => (
                                            <span key={f} style={{ fontSize: '10px', padding: '1px 5px', borderRadius: '3px', background: 'rgba(212,160,23,0.1)', color: 'rgba(212,160,23,0.8)' }}>{f}: {(v * 100).toFixed(0)}%</span>
                                        ))}
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function RiskTab({ alerts }: { alerts: RiskAlert[] }) {
    if (alerts.length === 0) {
        return <div style={{ padding: '40px', textAlign: 'center', color: 'rgba(255,255,255,0.3)', fontSize: '14px' }}>✅ No active risk alerts</div>;
    }
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {alerts.map((a, i) => (
                <div key={i} style={{ padding: '16px 20px', background: 'rgba(255,255,255,0.02)', border: `1px solid ${SEVERITY_COLORS[a.severity] || '#888'}30`, borderLeft: `4px solid ${SEVERITY_COLORS[a.severity] || '#888'}`, borderRadius: '8px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ fontSize: '15px', fontWeight: 700, color: SEVERITY_COLORS[a.severity] || '#888' }}>{a.title}</span>
                        <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '4px', background: `${SEVERITY_COLORS[a.severity] || '#888'}20`, color: SEVERITY_COLORS[a.severity] || '#888', textTransform: 'uppercase', fontWeight: 700 }}>{a.severity}</span>
                    </div>
                    <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.6)', lineHeight: '1.5', marginBottom: '10px' }}>{a.description}</div>
                    {a.affected_tickers.length > 0 && (
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '8px' }}>
                            {a.affected_tickers.map(t => (
                                <span key={t} style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '3px', background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)' }}>{t}</span>
                            ))}
                        </div>
                    )}
                    {Object.keys(a.metrics).length > 0 && (
                        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                            {Object.entries(a.metrics).map(([k, v]) => (
                                <div key={k} style={{ fontSize: '11px' }}>
                                    <span style={{ color: 'rgba(255,255,255,0.4)' }}>{k.replace('_', ' ')}: </span>
                                    <span style={{ color: 'rgba(255,255,255,0.8)', fontWeight: 600, fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}

function InsightsTab({ insights }: { insights: InvestmentInsight[] }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {insights.map((ins, i) => (
                <div key={i} style={{ padding: '20px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                        <span style={{ fontSize: '20px' }}>{CATEGORY_ICONS[ins.category] || '💡'}</span>
                        <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: 'rgba(212,160,23,0.1)', color: '#d4a017', textTransform: 'uppercase', fontWeight: 600 }}>{ins.category}</span>
                        <span style={{ flex: 1 }} />
                        <ConfidenceBar value={ins.confidence} />
                    </div>
                    <div style={{ marginBottom: '12px' }}>
                        <div style={{ fontSize: '14px', fontWeight: 600, color: 'rgba(255,255,255,0.9)', marginBottom: '6px' }}>📋 What happened</div>
                        <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.7)', lineHeight: '1.5' }}>{ins.what_happened}</div>
                    </div>
                    <div style={{ marginBottom: '12px' }}>
                        <div style={{ fontSize: '14px', fontWeight: 600, color: 'rgba(255,255,255,0.9)', marginBottom: '6px' }}>🔍 Why it happened</div>
                        <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.7)', lineHeight: '1.5' }}>{ins.why_it_happened}</div>
                    </div>
                    <div style={{ marginBottom: '12px' }}>
                        <div style={{ fontSize: '14px', fontWeight: 600, color: '#d4a017', marginBottom: '6px' }}>💡 What it means for investors</div>
                        <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.8)', lineHeight: '1.5', fontWeight: 500 }}>{ins.what_it_means}</div>
                    </div>
                    {ins.factors_used.length > 0 && (
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                            {ins.factors_used.map((f, j) => (
                                <span key={j} style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '3px', background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.5)' }}>{f}</span>
                            ))}
                        </div>
                    )}
                    {ins.related_tickers.length > 0 && (
                        <div style={{ display: 'flex', gap: '4px', marginTop: '8px' }}>
                            {ins.related_tickers.map(t => (
                                <span key={t} style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '3px', background: 'rgba(212,160,23,0.1)', color: '#d4a017', fontWeight: 600 }}>{t}</span>
                            ))}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}

// ── Main View ───────────────────────────────────────────────────────────────

const TABS = [
    { key: 'regime', label: 'Market Regime', emoji: '🌐' },
    { key: 'opportunities', label: 'Opportunity Radar', emoji: '🎯' },
    { key: 'portfolios', label: 'Portfolio Suggestions', emoji: '📊' },
    { key: 'risks', label: 'Risk Signals', emoji: '⚠️' },
    { key: 'insights', label: 'Investment Insights', emoji: '💡' },
];

export default function InvestmentBrainView() {
    const [activeTab, setActiveTab] = useState('regime');
    const [data] = useState<BrainDashboard>(DEMO_DATA);

    const regimeColor = REGIME_COLORS[data.regime.regime] || '#888';

    return (
        <div id="investment-brain-dashboard" style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div>
                    <h1 style={{ fontSize: '22px', fontWeight: 700, color: '#d4a017', margin: 0, letterSpacing: '0.5px' }}>
                        🧠 Investment Brain
                    </h1>
                    <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.4)', marginTop: '4px' }}>
                        Financial Decision Intelligence • {data.asset_count} assets analyzed
                    </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                        padding: '6px 14px', borderRadius: '6px',
                        background: `${regimeColor}15`, border: `1px solid ${regimeColor}40`,
                        fontSize: '12px', fontWeight: 700, color: regimeColor, textTransform: 'uppercase',
                    }}>
                        {data.regime.regime.replace('_', ' ')}
                    </div>
                    <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.35)' }}>
                        {new Date(data.analysis_timestamp).toLocaleString()}
                    </div>
                </div>
            </div>

            {/* Summary Bar */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px', marginBottom: '24px' }}>
                {[
                    { label: 'Regime', value: data.regime.regime.replace('_', ' '), color: regimeColor },
                    { label: 'Opportunities', value: data.opportunities.length.toString(), color: '#22c55e' },
                    { label: 'Portfolios', value: data.portfolios.length.toString(), color: '#3b82f6' },
                    { label: 'Risk Alerts', value: data.risk_alerts.length.toString(), color: data.risk_alerts.some(a => a.severity === 'critical') ? '#ef4444' : '#eab308' },
                    { label: 'Insights', value: data.insights.length.toString(), color: '#a855f7' },
                ].map((item) => (
                    <div key={item.label} style={{ padding: '14px 16px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px', textAlign: 'center' }}>
                        <div style={{ fontSize: '22px', fontWeight: 700, color: item.color }}>{item.value}</div>
                        <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', marginTop: '2px', textTransform: 'uppercase' }}>{item.label}</div>
                    </div>
                ))}
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: '4px', marginBottom: '20px', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '0' }}>
                {TABS.map(tab => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        style={{
                            padding: '10px 18px',
                            background: activeTab === tab.key ? 'rgba(212,160,23,0.1)' : 'transparent',
                            border: 'none',
                            borderBottom: activeTab === tab.key ? '2px solid #d4a017' : '2px solid transparent',
                            color: activeTab === tab.key ? '#d4a017' : 'rgba(255,255,255,0.5)',
                            cursor: 'pointer',
                            fontSize: '13px',
                            fontWeight: activeTab === tab.key ? 600 : 400,
                            transition: 'all 0.2s',
                        }}
                    >
                        {tab.emoji} {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            <div>
                {activeTab === 'regime' && <RegimeTab regime={data.regime} />}
                {activeTab === 'opportunities' && <OpportunityTab opportunities={data.opportunities} />}
                {activeTab === 'portfolios' && <PortfolioTab portfolios={data.portfolios} />}
                {activeTab === 'risks' && <RiskTab alerts={data.risk_alerts} />}
                {activeTab === 'insights' && <InsightsTab insights={data.insights} />}
            </div>
        </div>
    );
}
