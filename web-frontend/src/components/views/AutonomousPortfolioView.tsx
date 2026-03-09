'use client';

import React, { useState } from 'react';

// ── Types ───────────────────────────────────────────────────────────────────

interface APMPosition { ticker: string; weight: number; alpha_score: number; justification: string; factor_exposures: Record<string, number>; sector: string; signals_used: string[]; }
interface APMPortfolio { objective: string; positions: APMPosition[]; allocation_method: string; total_weight: number; expected_return: number; expected_volatility: number; sharpe_ratio: number; regime_context: string; rationale: string; }
interface RebalanceAction { ticker: string; direction: string; current_weight: number; target_weight: number; weight_change: number; reason: string; }
interface RebalanceRecommendation { triggers_fired: string[]; urgency: string; actions: RebalanceAction[]; summary: string; should_rebalance: boolean; }
interface RiskViolation { violation_type: string; severity: string; title: string; description: string; affected_tickers: string[]; current_value: number; threshold: number; remediation: string; }
interface PortfolioRiskReport { portfolio_volatility: number; max_drawdown: number; var_95: number; cvar_95: number; concentration_hhi: number; sector_exposures: Record<string, number>; violations: RiskViolation[]; risk_score: number; within_limits: boolean; }
interface PerformanceSnapshot { total_return: number; annualized_return: number; volatility: number; sharpe_ratio: number; max_drawdown: number; alpha_vs_benchmark: number; beta: number; information_ratio: number; tracking_error: number; benchmark_name: string; benchmark_return: number; period_days: number; }
interface APMDashboard { portfolios: APMPortfolio[]; rebalance: RebalanceRecommendation | null; risk_report: PortfolioRiskReport | null; performance: PerformanceSnapshot | null; explanations: string[]; asset_count: number; active_regime: string; }

// ── Demo Data ───────────────────────────────────────────────────────────────

const DEMO: APMDashboard = {
    portfolios: [
        {
            objective: 'growth', allocation_method: 'max_sharpe', total_weight: 1, expected_return: 0.148, expected_volatility: 0.192, sharpe_ratio: 1.12, regime_context: 'expansion', rationale: 'High-conviction growth assets with strong momentum and alpha signals.',
            positions: [
                { ticker: 'NVDA', weight: 0.22, alpha_score: 88, justification: 'AI leadership with strong momentum', factor_exposures: { momentum: 0.91, growth: 0.85 }, sector: 'Technology', signals_used: ['Alpha=88', 'Tier=elite'] },
                { ticker: 'AAPL', weight: 0.18, alpha_score: 82, justification: 'Quality tech with macro alignment', factor_exposures: { quality: 0.82, momentum: 0.65 }, sector: 'Technology', signals_used: ['Alpha=82', 'Sector aligned'] },
                { ticker: 'MSFT', weight: 0.16, alpha_score: 79, justification: 'Cloud and AI infrastructure leader', factor_exposures: { quality: 0.88, growth: 0.72 }, sector: 'Technology', signals_used: ['Alpha=79'] },
                { ticker: 'AMZN', weight: 0.14, alpha_score: 75, justification: 'E-commerce and cloud growth', factor_exposures: { momentum: 0.68, growth: 0.78 }, sector: 'Technology', signals_used: ['Alpha=75'] },
                { ticker: 'TSLA', weight: 0.12, alpha_score: 71, justification: 'EV + energy storage momentum', factor_exposures: { momentum: 0.82, sentiment: 0.75 }, sector: 'Auto', signals_used: ['Alpha=71', 'Sentiment driven'] },
                { ticker: 'META', weight: 0.10, alpha_score: 69, justification: 'AI investment cycle catalyst', factor_exposures: { event: 0.72, momentum: 0.55 }, sector: 'Technology', signals_used: ['Alpha=69'] },
                { ticker: 'LLY', weight: 0.08, alpha_score: 67, justification: 'Pharma growth from GLP-1', factor_exposures: { growth: 0.85, quality: 0.72 }, sector: 'Healthcare', signals_used: ['Alpha=67'] },
            ],
        },
        {
            objective: 'value', allocation_method: 'risk_parity', total_weight: 1, expected_return: 0.098, expected_volatility: 0.128, sharpe_ratio: 0.94, regime_context: 'expansion', rationale: 'Undervalued, high-quality assets with margin of safety.',
            positions: [
                { ticker: 'JPM', weight: 0.18, alpha_score: 76, justification: 'Deep value financial', factor_exposures: { value: 0.82, quality: 0.68 }, sector: 'Financials', signals_used: ['Alpha=76'] },
                { ticker: 'BRK.B', weight: 0.16, alpha_score: 72, justification: 'Conglomerate discount', factor_exposures: { value: 0.92, quality: 0.85 }, sector: 'Financials', signals_used: ['Alpha=72'] },
                { ticker: 'JNJ', weight: 0.15, alpha_score: 68, justification: 'Healthcare value', factor_exposures: { value: 0.75, quality: 0.8 }, sector: 'Healthcare', signals_used: ['Alpha=68'] },
                { ticker: 'CVX', weight: 0.14, alpha_score: 65, justification: 'Energy value', factor_exposures: { value: 0.78, macro: 0.5 }, sector: 'Energy', signals_used: ['Alpha=65'] },
                { ticker: 'BAC', weight: 0.12, alpha_score: 62, justification: 'Banking value play', factor_exposures: { value: 0.72, macro: 0.4 }, sector: 'Financials', signals_used: ['Alpha=62'] },
                { ticker: 'PFE', weight: 0.13, alpha_score: 58, justification: 'Pharma deep value', factor_exposures: { value: 0.88 }, sector: 'Healthcare', signals_used: ['Alpha=58'] },
                { ticker: 'INTC', weight: 0.12, alpha_score: 55, justification: 'Semiconductor turnaround', factor_exposures: { value: 0.85, event: 0.45 }, sector: 'Technology', signals_used: ['Alpha=55'] },
            ],
        },
        {
            objective: 'income', allocation_method: 'equal_risk_contribution', total_weight: 1, expected_return: 0.068, expected_volatility: 0.098, sharpe_ratio: 0.82, regime_context: 'expansion', rationale: 'Stable, cash-generative assets with consistent income.',
            positions: [
                { ticker: 'O', weight: 0.18, alpha_score: 55, justification: 'Monthly dividend REIT', factor_exposures: { dividend: 0.92, quality: 0.6 }, sector: 'Real Estate', signals_used: [] },
                { ticker: 'ABBV', weight: 0.17, alpha_score: 62, justification: 'Pharma dividend growth', factor_exposures: { dividend: 0.78, quality: 0.72 }, sector: 'Healthcare', signals_used: [] },
                { ticker: 'VZ', weight: 0.16, alpha_score: 48, justification: 'High yield telecom', factor_exposures: { dividend: 0.85 }, sector: 'Telecom', signals_used: [] },
                { ticker: 'XOM', weight: 0.16, alpha_score: 58, justification: 'Energy dividend', factor_exposures: { dividend: 0.7, macro: 0.4 }, sector: 'Energy', signals_used: [] },
                { ticker: 'KO', weight: 0.17, alpha_score: 52, justification: 'Dividend aristocrat', factor_exposures: { quality: 0.85, dividend: 0.9 }, sector: 'Consumer Staples', signals_used: [] },
                { ticker: 'PG', weight: 0.16, alpha_score: 54, justification: 'Consumer staple moat', factor_exposures: { quality: 0.88, dividend: 0.72 }, sector: 'Consumer Staples', signals_used: [] },
            ],
        },
        {
            objective: 'balanced', allocation_method: 'factor_diversification', total_weight: 1, expected_return: 0.112, expected_volatility: 0.142, sharpe_ratio: 0.98, regime_context: 'expansion', rationale: 'Diversified blend of growth and value.',
            positions: [
                { ticker: 'AAPL', weight: 0.14, alpha_score: 82, justification: 'Quality growth', factor_exposures: { quality: 0.82, momentum: 0.65 }, sector: 'Technology', signals_used: [] },
                { ticker: 'JPM', weight: 0.13, alpha_score: 76, justification: 'Value financial', factor_exposures: { value: 0.82 }, sector: 'Financials', signals_used: [] },
                { ticker: 'UNH', weight: 0.12, alpha_score: 74, justification: 'Healthcare quality', factor_exposures: { quality: 0.85, growth: 0.62 }, sector: 'Healthcare', signals_used: [] },
                { ticker: 'MSFT', weight: 0.12, alpha_score: 79, justification: 'Tech quality', factor_exposures: { quality: 0.88, growth: 0.72 }, sector: 'Technology', signals_used: [] },
                { ticker: 'JNJ', weight: 0.12, alpha_score: 68, justification: 'Defensive value', factor_exposures: { value: 0.75, quality: 0.8 }, sector: 'Healthcare', signals_used: [] },
                { ticker: 'PG', weight: 0.12, alpha_score: 54, justification: 'Staple stability', factor_exposures: { quality: 0.88 }, sector: 'Consumer Staples', signals_used: [] },
                { ticker: 'NVDA', weight: 0.13, alpha_score: 88, justification: 'Growth alpha', factor_exposures: { momentum: 0.91 }, sector: 'Technology', signals_used: [] },
                { ticker: 'XOM', weight: 0.12, alpha_score: 58, justification: 'Energy value', factor_exposures: { value: 0.7, macro: 0.4 }, sector: 'Energy', signals_used: [] },
            ],
        },
        {
            objective: 'defensive', allocation_method: 'min_variance', total_weight: 1, expected_return: 0.055, expected_volatility: 0.078, sharpe_ratio: 0.75, regime_context: 'expansion', rationale: 'Low-volatility, high-quality assets for capital preservation.',
            positions: [
                { ticker: 'JNJ', weight: 0.20, alpha_score: 68, justification: 'Healthcare defensive', factor_exposures: { quality: 0.9, low_volatility: 0.85 }, sector: 'Healthcare', signals_used: [] },
                { ticker: 'PG', weight: 0.20, alpha_score: 54, justification: 'Consumer moat', factor_exposures: { quality: 0.88, low_volatility: 0.82 }, sector: 'Consumer Staples', signals_used: [] },
                { ticker: 'WMT', weight: 0.16, alpha_score: 52, justification: 'Retail defensive', factor_exposures: { quality: 0.72, low_volatility: 0.78 }, sector: 'Consumer Staples', signals_used: [] },
                { ticker: 'UNH', weight: 0.15, alpha_score: 74, justification: 'Quality healthcare', factor_exposures: { quality: 0.85 }, sector: 'Healthcare', signals_used: [] },
                { ticker: 'KO', weight: 0.15, alpha_score: 52, justification: 'Dividend aristocrat', factor_exposures: { quality: 0.85, low_volatility: 0.88 }, sector: 'Consumer Staples', signals_used: [] },
                { ticker: 'NEE', weight: 0.14, alpha_score: 48, justification: 'Utility stability', factor_exposures: { low_volatility: 0.92 }, sector: 'Utilities', signals_used: [] },
            ],
        },
        {
            objective: 'opportunistic', allocation_method: 'volatility_targeting', total_weight: 1, expected_return: 0.185, expected_volatility: 0.255, sharpe_ratio: 1.05, regime_context: 'expansion', rationale: 'High-alpha, event-driven plays for maximum risk-adjusted return.',
            positions: [
                { ticker: 'NVDA', weight: 0.25, alpha_score: 88, justification: 'AI momentum leader', factor_exposures: { momentum: 0.91, sentiment: 0.68 }, sector: 'Technology', signals_used: [] },
                { ticker: 'TSLA', weight: 0.22, alpha_score: 71, justification: 'Sentiment-driven momentum', factor_exposures: { sentiment: 0.82, momentum: 0.78 }, sector: 'Auto', signals_used: [] },
                { ticker: 'META', weight: 0.20, alpha_score: 69, justification: 'Event catalyst play', factor_exposures: { event: 0.85, momentum: 0.62 }, sector: 'Technology', signals_used: [] },
                { ticker: 'COIN', weight: 0.18, alpha_score: 65, justification: 'Crypto proxy', factor_exposures: { sentiment: 0.78, volatility: 0.85 }, sector: 'Financials', signals_used: [] },
                { ticker: 'PLTR', weight: 0.15, alpha_score: 62, justification: 'Gov AI contracts', factor_exposures: { event: 0.72 }, sector: 'Technology', signals_used: [] },
            ],
        },
    ],
    rebalance: {
        triggers_fired: ['alpha_shift', 'weight_drift'], urgency: 'moderate', should_rebalance: true, summary: 'NVDA: alpha shifted 12pts. | Weight drift in 3 positions exceeds 5%.',
        actions: [
            { ticker: 'NVDA', direction: 'buy', current_weight: 0.20, target_weight: 0.24, weight_change: 0.04, reason: 'Alpha shifted by 12 points (76 → 88)' },
            { ticker: 'INTC', direction: 'sell', current_weight: 0.14, target_weight: 0.08, weight_change: -0.06, reason: 'Alpha declined, weight drift from target' },
            { ticker: 'COIN', direction: 'buy', current_weight: 0.0, target_weight: 0.05, weight_change: 0.05, reason: 'New high-alpha candidate (score 65) not in current portfolio' },
        ],
    },
    risk_report: {
        portfolio_volatility: 0.192, max_drawdown: -0.082, var_95: -0.018, cvar_95: -0.025, concentration_hhi: 0.148, within_limits: true, risk_score: 38,
        sector_exposures: { Technology: 0.52, Healthcare: 0.12, Financials: 0.15, Auto: 0.08, 'Consumer Staples': 0.08, Energy: 0.05 },
        violations: [
            { violation_type: 'sector_overweight', severity: 'warning', title: 'Technology Sector Overweight', description: 'Technology at 52% exceeds 40% limit.', affected_tickers: ['NVDA', 'AAPL', 'MSFT', 'META'], current_value: 0.52, threshold: 0.40, remediation: 'Reduce Technology exposure by rotating into other sectors.' },
        ],
    },
    performance: { total_return: 0.142, annualized_return: 0.168, volatility: 0.185, sharpe_ratio: 1.15, max_drawdown: -0.082, alpha_vs_benchmark: 0.062, beta: 1.12, information_ratio: 0.85, tracking_error: 0.068, benchmark_name: 'S&P 500', benchmark_return: 0.08, period_days: 252 },
    explanations: [
        'Constructed 6 portfolios using 25 alpha candidates in expansion regime.',
        'Optimised weights using regime-adjusted allocation methods.',
        'Risk assessment: score=38/100, 1 violation(s), HHI=0.148.',
        'Rebalance recommended (moderate urgency): 2 trigger(s) fired, 3 action(s).',
        'Performance: return=14.20%, Sharpe=1.15, alpha=6.20%.',
        'Growth portfolio: top positions NVDA, AAPL, MSFT selected via max_sharpe method.',
        '⚠️ Technology Sector Overweight: Technology at 52% exceeds 40% limit. Recommendation: Reduce Technology exposure by rotating into other sectors.',
        'Portfolios tilted toward growth and cyclical sectors — expansion regime supports risk-on positioning.',
    ],
    asset_count: 25,
    active_regime: 'expansion',
};

// ── Utility ─────────────────────────────────────────────────────────────────

const REGIME_COLORS: Record<string, string> = { expansion: '#22c55e', slowdown: '#eab308', recession: '#ef4444', recovery: '#3b82f6', high_volatility: '#f97316', liquidity_expansion: '#a855f7' };
const SEVERITY_COLORS: Record<string, string> = { critical: '#ef4444', warning: '#f97316', info: '#6b7280' };
const URGENCY_COLORS: Record<string, string> = { immediate: '#ef4444', high: '#f97316', moderate: '#eab308', low: '#22c55e' };
const OBJ_EMOJI: Record<string, string> = { growth: '🚀', value: '💎', income: '💰', balanced: '⚖️', defensive: '🛡️', opportunistic: '⚡' };

function Bar({ value, max = 1, color = '#d4a017', label }: { value: number; max?: number; color?: string; label?: string }) {
    const pct = Math.min(Math.abs(value / max) * 100, 100);
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {label && <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', minWidth: '60px' }}>{label}</span>}
            <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '3px', transition: 'width 0.5s ease' }} />
            </div>
            <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', minWidth: '40px', textAlign: 'right', fontFamily: 'var(--font-mono, monospace)' }}>
                {typeof value === 'number' && max === 1 ? `${(value * 100).toFixed(1)}%` : value.toFixed(2)}
            </span>
        </div>
    );
}

// ── Tab: Portfolio Allocation ───────────────────────────────────────────────

function AllocationTab({ portfolios }: { portfolios: APMPortfolio[] }) {
    const [selected, setSelected] = useState(0);
    const p = portfolios[selected];
    if (!p) return null;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {portfolios.map((pf, i) => (
                    <button key={pf.objective} onClick={() => setSelected(i)} style={{
                        padding: '8px 16px', borderRadius: '8px', border: `1px solid ${selected === i ? '#d4a017' : 'rgba(255,255,255,0.08)'}`,
                        background: selected === i ? 'rgba(212,160,23,0.12)' : 'rgba(255,255,255,0.02)', color: selected === i ? '#d4a017' : 'rgba(255,255,255,0.6)',
                        cursor: 'pointer', fontSize: '13px', fontWeight: 600, textTransform: 'uppercase', transition: 'all 0.2s',
                    }}>{OBJ_EMOJI[pf.objective] || '📊'} {pf.objective}</button>
                ))}
            </div>
            <div style={{ padding: '20px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <div>
                        <span style={{ fontSize: '18px', fontWeight: 700, color: '#d4a017', textTransform: 'uppercase' }}>{OBJ_EMOJI[p.objective]} {p.objective} Portfolio</span>
                        <span style={{ marginLeft: '12px', fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: 'rgba(59,130,246,0.15)', color: '#3b82f6' }}>{p.allocation_method.replace(/_/g, ' ')}</span>
                    </div>
                    <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
                        <div><span style={{ color: 'rgba(255,255,255,0.4)' }}>Return </span><span style={{ color: '#22c55e', fontWeight: 700 }}>{(p.expected_return * 100).toFixed(1)}%</span></div>
                        <div><span style={{ color: 'rgba(255,255,255,0.4)' }}>Vol </span><span style={{ color: '#eab308', fontWeight: 700 }}>{(p.expected_volatility * 100).toFixed(1)}%</span></div>
                        <div><span style={{ color: 'rgba(255,255,255,0.4)' }}>Sharpe </span><span style={{ color: '#d4a017', fontWeight: 700 }}>{p.sharpe_ratio.toFixed(2)}</span></div>
                    </div>
                </div>
                <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.5)', marginBottom: '16px' }}>{p.rationale}</div>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead><tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                        <th style={{ textAlign: 'left', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Asset</th>
                        <th style={{ textAlign: 'right', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Weight</th>
                        <th style={{ textAlign: 'right', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Alpha</th>
                        <th style={{ textAlign: 'left', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Sector</th>
                        <th style={{ textAlign: 'left', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Factors</th>
                    </tr></thead>
                    <tbody>{p.positions.map((pos, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                            <td style={{ padding: '10px 12px', fontSize: '14px', fontWeight: 700, color: '#d4a017' }}>{pos.ticker}</td>
                            <td style={{ padding: '10px 12px', textAlign: 'right' }}><Bar value={pos.weight} color="#3b82f6" /></td>
                            <td style={{ padding: '10px 12px', fontSize: '14px', fontWeight: 600, color: 'rgba(255,255,255,0.9)', textAlign: 'right', fontFamily: 'var(--font-mono, monospace)' }}>{pos.alpha_score}</td>
                            <td style={{ padding: '10px 12px', fontSize: '12px', color: 'rgba(255,255,255,0.5)' }}>{pos.sector}</td>
                            <td style={{ padding: '10px 12px' }}>
                                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                    {Object.entries(pos.factor_exposures).map(([f, v]) => (
                                        <span key={f} style={{ fontSize: '10px', padding: '1px 5px', borderRadius: '3px', background: 'rgba(212,160,23,0.1)', color: 'rgba(212,160,23,0.8)' }}>{f}: {(v * 100).toFixed(0)}%</span>
                                    ))}
                                </div>
                            </td>
                        </tr>
                    ))}</tbody>
                </table>
            </div>
        </div>
    );
}

// ── Tab: Performance ────────────────────────────────────────────────────────

function PerformanceTab({ perf }: { perf: PerformanceSnapshot | null }) {
    if (!perf) return <div style={{ padding: '40px', textAlign: 'center', color: 'rgba(255,255,255,0.3)' }}>No performance data available</div>;

    const metrics = [
        { label: 'Total Return', value: `${(perf.total_return * 100).toFixed(2)}%`, color: perf.total_return >= 0 ? '#22c55e' : '#ef4444' },
        { label: 'Annualized Return', value: `${(perf.annualized_return * 100).toFixed(2)}%`, color: perf.annualized_return >= 0 ? '#22c55e' : '#ef4444' },
        { label: 'Volatility', value: `${(perf.volatility * 100).toFixed(2)}%`, color: '#eab308' },
        { label: 'Sharpe Ratio', value: perf.sharpe_ratio.toFixed(2), color: perf.sharpe_ratio > 1 ? '#22c55e' : '#eab308' },
        { label: 'Max Drawdown', value: `${(perf.max_drawdown * 100).toFixed(2)}%`, color: '#ef4444' },
        { label: `Alpha vs ${perf.benchmark_name}`, value: `${(perf.alpha_vs_benchmark * 100).toFixed(2)}%`, color: perf.alpha_vs_benchmark >= 0 ? '#22c55e' : '#ef4444' },
        { label: 'Beta', value: perf.beta.toFixed(2), color: '#3b82f6' },
        { label: 'Information Ratio', value: perf.information_ratio.toFixed(2), color: '#a855f7' },
        { label: 'Tracking Error', value: `${(perf.tracking_error * 100).toFixed(2)}%`, color: '#f97316' },
        { label: `${perf.benchmark_name} Return`, value: `${(perf.benchmark_return * 100).toFixed(2)}%`, color: 'rgba(255,255,255,0.6)' },
    ];

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>
            {metrics.map(m => (
                <div key={m.label} style={{ padding: '16px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', marginBottom: '6px' }}>{m.label}</div>
                    <div style={{ fontSize: '22px', fontWeight: 700, color: m.color, fontFamily: 'var(--font-mono, monospace)' }}>{m.value}</div>
                </div>
            ))}
        </div>
    );
}

// ── Tab: Risk ───────────────────────────────────────────────────────────────

function RiskTab({ report }: { report: PortfolioRiskReport | null }) {
    if (!report) return <div style={{ padding: '40px', textAlign: 'center', color: 'rgba(255,255,255,0.3)' }}>No risk data</div>;

    const scoreColor = report.risk_score < 40 ? '#22c55e' : report.risk_score < 70 ? '#eab308' : '#ef4444';

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Risk Score */}
            <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                <div style={{ width: '100px', height: '100px', borderRadius: '50%', background: `${scoreColor}15`, border: `3px solid ${scoreColor}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', flexShrink: 0 }}>
                    <div style={{ fontSize: '28px', fontWeight: 700, color: scoreColor }}>{report.risk_score.toFixed(0)}</div>
                    <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.4)' }}>/ 100</div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', flex: 1 }}>
                    {[
                        { label: 'Portfolio Vol', value: `${(report.portfolio_volatility * 100).toFixed(1)}%` },
                        { label: 'Max Drawdown', value: `${(report.max_drawdown * 100).toFixed(1)}%` },
                        { label: 'HHI', value: report.concentration_hhi.toFixed(3) },
                        { label: 'VaR (95%)', value: `${(report.var_95 * 100).toFixed(2)}%` },
                        { label: 'CVaR (95%)', value: `${(report.cvar_95 * 100).toFixed(2)}%` },
                        { label: 'Status', value: report.within_limits ? '✅ Within Limits' : '⚠️ Violations' },
                    ].map(m => (
                        <div key={m.label} style={{ padding: '10px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px' }}>
                            <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>{m.label}</div>
                            <div style={{ fontSize: '14px', fontWeight: 600, color: 'rgba(255,255,255,0.9)', fontFamily: 'var(--font-mono, monospace)' }}>{m.value}</div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Sector Exposures */}
            <div>
                <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'rgba(255,255,255,0.8)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Sector Exposures</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {Object.entries(report.sector_exposures).sort((a, b) => b[1] - a[1]).map(([sector, wt]) => (
                        <Bar key={sector} value={wt} color={wt > 0.4 ? '#f97316' : '#3b82f6'} label={sector} />
                    ))}
                </div>
            </div>

            {/* Violations */}
            {report.violations.length > 0 && (
                <div>
                    <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'rgba(255,255,255,0.8)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Violations</h3>
                    {report.violations.map((v, i) => (
                        <div key={i} style={{ padding: '14px 18px', background: 'rgba(255,255,255,0.02)', border: `1px solid ${SEVERITY_COLORS[v.severity] || '#888'}30`, borderLeft: `4px solid ${SEVERITY_COLORS[v.severity] || '#888'}`, borderRadius: '8px', marginBottom: '8px' }}>
                            <div style={{ fontSize: '14px', fontWeight: 700, color: SEVERITY_COLORS[v.severity] || '#888', marginBottom: '4px' }}>{v.title}</div>
                            <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.6)', marginBottom: '6px' }}>{v.description}</div>
                            <div style={{ fontSize: '11px', color: '#22c55e' }}>💡 {v.remediation}</div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Tab: Rebalancing ────────────────────────────────────────────────────────

function RebalanceTab({ rec }: { rec: RebalanceRecommendation | null }) {
    if (!rec) return <div style={{ padding: '40px', textAlign: 'center', color: 'rgba(255,255,255,0.3)' }}>No rebalancing data</div>;

    const urgencyColor = URGENCY_COLORS[rec.urgency] || '#888';

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', padding: '16px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px' }}>
                <div style={{ fontSize: '28px' }}>{rec.should_rebalance ? '🔄' : '✅'}</div>
                <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: rec.should_rebalance ? urgencyColor : '#22c55e' }}>
                        {rec.should_rebalance ? `Rebalance Recommended — ${rec.urgency.toUpperCase()} Urgency` : 'No Rebalancing Required'}
                    </div>
                    <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.5)', marginTop: '4px' }}>{rec.summary}</div>
                </div>
                {rec.triggers_fired.length > 0 && (
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                        {rec.triggers_fired.map(t => (
                            <span key={t} style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '4px', background: 'rgba(234,179,8,0.15)', color: '#eab308', textTransform: 'uppercase' }}>{t.replace('_', ' ')}</span>
                        ))}
                    </div>
                )}
            </div>
            {rec.actions.length > 0 && (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead><tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                        <th style={{ textAlign: 'left', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Ticker</th>
                        <th style={{ textAlign: 'center', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Action</th>
                        <th style={{ textAlign: 'right', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Current</th>
                        <th style={{ textAlign: 'right', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Target</th>
                        <th style={{ textAlign: 'right', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Change</th>
                        <th style={{ textAlign: 'left', padding: '8px 12px', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase' }}>Reason</th>
                    </tr></thead>
                    <tbody>{rec.actions.map((a, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                            <td style={{ padding: '10px 12px', fontWeight: 700, color: '#d4a017' }}>{a.ticker}</td>
                            <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                                <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, background: a.direction === 'buy' ? 'rgba(34,197,94,0.15)' : a.direction === 'sell' ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.05)', color: a.direction === 'buy' ? '#22c55e' : a.direction === 'sell' ? '#ef4444' : 'rgba(255,255,255,0.5)', textTransform: 'uppercase' }}>{a.direction}</span>
                            </td>
                            <td style={{ padding: '10px 12px', textAlign: 'right', fontFamily: 'var(--font-mono, monospace)', color: 'rgba(255,255,255,0.7)' }}>{(a.current_weight * 100).toFixed(1)}%</td>
                            <td style={{ padding: '10px 12px', textAlign: 'right', fontFamily: 'var(--font-mono, monospace)', color: 'rgba(255,255,255,0.9)', fontWeight: 600 }}>{(a.target_weight * 100).toFixed(1)}%</td>
                            <td style={{ padding: '10px 12px', textAlign: 'right', fontFamily: 'var(--font-mono, monospace)', color: a.weight_change > 0 ? '#22c55e' : '#ef4444', fontWeight: 600 }}>{a.weight_change > 0 ? '+' : ''}{(a.weight_change * 100).toFixed(1)}%</td>
                            <td style={{ padding: '10px 12px', fontSize: '12px', color: 'rgba(255,255,255,0.5)', maxWidth: '250px' }}>{a.reason}</td>
                        </tr>
                    ))}</tbody>
                </table>
            )}
        </div>
    );
}

// ── Tab: Explanations ───────────────────────────────────────────────────────

function ExplanationsTab({ explanations }: { explanations: string[] }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {explanations.map((e, i) => (
                <div key={i} style={{ padding: '14px 18px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px', fontSize: '13px', color: 'rgba(255,255,255,0.75)', lineHeight: '1.6' }}>
                    <span style={{ color: '#d4a017', fontWeight: 600, marginRight: '8px' }}>#{i + 1}</span>{e}
                </div>
            ))}
        </div>
    );
}

// ── Main View ───────────────────────────────────────────────────────────────

const TABS = [
    { key: 'allocation', label: 'Portfolio Allocation', emoji: '📊' },
    { key: 'performance', label: 'Performance Metrics', emoji: '📈' },
    { key: 'risk', label: 'Risk Indicators', emoji: '⚠️' },
    { key: 'rebalancing', label: 'Rebalancing Signals', emoji: '🔄' },
    { key: 'explanations', label: 'Decision Explainability', emoji: '🧠' },
];

export default function AutonomousPortfolioView() {
    const [activeTab, setActiveTab] = useState('allocation');
    const [data] = useState<APMDashboard>(DEMO);

    const regimeColor = REGIME_COLORS[data.active_regime] || '#888';

    return (
        <div id="apm-dashboard" style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div>
                    <h1 style={{ fontSize: '22px', fontWeight: 700, color: '#d4a017', margin: 0, letterSpacing: '0.5px' }}>🤖 Autonomous Portfolio Manager</h1>
                    <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.4)', marginTop: '4px' }}>AI-Driven Investment Decision Support • {data.asset_count} assets</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ padding: '6px 14px', borderRadius: '6px', background: `${regimeColor}15`, border: `1px solid ${regimeColor}40`, fontSize: '12px', fontWeight: 700, color: regimeColor, textTransform: 'uppercase' }}>{data.active_regime.replace('_', ' ')}</div>
                    {data.rebalance?.should_rebalance && (
                        <div style={{ padding: '6px 14px', borderRadius: '6px', background: 'rgba(234,179,8,0.12)', border: '1px solid rgba(234,179,8,0.3)', fontSize: '12px', fontWeight: 700, color: '#eab308' }}>🔄 REBALANCE</div>
                    )}
                </div>
            </div>

            {/* Summary */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px', marginBottom: '24px' }}>
                {[
                    { label: 'Portfolios', value: data.portfolios.length.toString(), color: '#3b82f6' },
                    { label: 'Sharpe (Best)', value: Math.max(...data.portfolios.map(p => p.sharpe_ratio)).toFixed(2), color: '#22c55e' },
                    { label: 'Risk Score', value: data.risk_report?.risk_score.toFixed(0) || '—', color: (data.risk_report?.risk_score || 0) < 50 ? '#22c55e' : '#eab308' },
                    { label: 'Rebalance Actions', value: data.rebalance?.actions.length.toString() || '0', color: '#f97316' },
                    { label: 'Alpha', value: data.performance ? `${(data.performance.alpha_vs_benchmark * 100).toFixed(1)}%` : '—', color: '#a855f7' },
                ].map(item => (
                    <div key={item.label} style={{ padding: '14px 16px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px', textAlign: 'center' }}>
                        <div style={{ fontSize: '22px', fontWeight: 700, color: item.color }}>{item.value}</div>
                        <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', marginTop: '2px', textTransform: 'uppercase' }}>{item.label}</div>
                    </div>
                ))}
            </div>

            <div style={{ display: 'flex', gap: '4px', marginBottom: '20px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                {TABS.map(tab => (
                    <button key={tab.key} onClick={() => setActiveTab(tab.key)} style={{
                        padding: '10px 18px', background: activeTab === tab.key ? 'rgba(212,160,23,0.1)' : 'transparent',
                        border: 'none', borderBottom: activeTab === tab.key ? '2px solid #d4a017' : '2px solid transparent',
                        color: activeTab === tab.key ? '#d4a017' : 'rgba(255,255,255,0.5)', cursor: 'pointer', fontSize: '13px',
                        fontWeight: activeTab === tab.key ? 600 : 400, transition: 'all 0.2s',
                    }}>{tab.emoji} {tab.label}</button>
                ))}
            </div>

            <div>
                {activeTab === 'allocation' && <AllocationTab portfolios={data.portfolios} />}
                {activeTab === 'performance' && <PerformanceTab perf={data.performance} />}
                {activeTab === 'risk' && <RiskTab report={data.risk_report} />}
                {activeTab === 'rebalancing' && <RebalanceTab rec={data.rebalance} />}
                {activeTab === 'explanations' && <ExplanationsTab explanations={data.explanations} />}
            </div>
        </div>
    );
}
