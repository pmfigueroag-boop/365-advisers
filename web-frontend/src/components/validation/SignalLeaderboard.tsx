'use client';

import React, { useState } from 'react';

const BADGE_STYLES = {
    robust: { bg: 'rgba(34,197,94,0.15)', color: '#4ade80', label: 'ROBUST' },
    moderate: { bg: 'rgba(250,204,21,0.15)', color: '#facc15', label: 'MOD' },
    weak: { bg: 'rgba(251,146,60,0.15)', color: '#fb923c', label: 'WEAK' },
    overfit: { bg: 'rgba(239,68,68,0.15)', color: '#f87171', label: 'OVER' },
    resilient: { bg: 'rgba(34,197,94,0.15)', color: '#4ade80', label: 'RSLNT' },
    fragile: { bg: 'rgba(239,68,68,0.15)', color: '#f87171', label: 'FRAG' },
    pure_alpha: { bg: 'rgba(34,197,94,0.15)', color: '#4ade80', label: 'PURE' },
    mixed: { bg: 'rgba(250,204,21,0.15)', color: '#facc15', label: 'MIX' },
    factor_beta: { bg: 'rgba(239,68,68,0.15)', color: '#f87171', label: 'FAC' },
};

const TIER_COLORS = {
    A: '#4ade80', B: '#facc15', C: '#fb923c', D: '#f87171',
};

function Badge({ type }) {
    const style = BADGE_STYLES[type] || BADGE_STYLES.moderate;
    return (
        <span style={{
            background: style.bg,
            color: style.color,
            padding: '2px 6px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: '700',
            letterSpacing: '0.03em',
        }}>
            {style.label}
        </span>
    );
}

export default function SignalLeaderboard({ data }) {
    const [view, setView] = useState('top');

    if (!data) return null;

    const signals = view === 'top' ? (data.top_signals || [])
        : view === 'bottom' ? (data.bottom_signals || [])
            : (data.degrading_signals || []);

    return (
        <div>
            <div style={styles.sectionHeader}>
                <h3 style={styles.sectionTitle}>🏆 Signal Leaderboard</h3>
            </div>

            {/* Summary Cards */}
            <div style={styles.cards}>
                <div style={styles.card}>
                    <div style={styles.cardValue}>{data.total_signals}</div>
                    <div style={styles.cardLabel}>Total Signals</div>
                </div>
                <div style={styles.card}>
                    <div style={{ ...styles.cardValue, color: data.avg_sharpe >= 1 ? '#4ade80' : '#facc15' }}>
                        {data.avg_sharpe?.toFixed(2)}
                    </div>
                    <div style={styles.cardLabel}>Avg Sharpe</div>
                </div>
                <div style={styles.card}>
                    <div style={{ ...styles.cardValue, color: data.degrading_count > 0 ? '#f87171' : '#4ade80' }}>
                        {data.degrading_count} {data.degrading_count > 0 ? '⚠️' : '✓'}
                    </div>
                    <div style={styles.cardLabel}>Degrading</div>
                </div>
                <div style={styles.card}>
                    <div style={{ ...styles.cardValue, color: '#4ade80' }}>
                        {data.pure_alpha_count}
                    </div>
                    <div style={styles.cardLabel}>Pure Alpha</div>
                </div>
            </div>

            {/* View Tabs */}
            <div style={styles.tabs}>
                {['top', 'bottom', 'degrading'].map(tab => (
                    <button
                        key={tab}
                        onClick={() => setView(tab)}
                        style={{
                            ...styles.tab,
                            ...(view === tab ? styles.tabActive : {}),
                        }}
                    >
                        {tab === 'top' ? '🔝 Top' : tab === 'bottom' ? '🔻 Bottom' : '⚠️ Degrading'}
                        {tab === 'degrading' && data.degrading_count > 0 && (
                            <span style={styles.alertBadge}>{data.degrading_count}</span>
                        )}
                    </button>
                ))}
            </div>

            {/* Signal Table */}
            {view !== 'degrading' ? (
                <div style={styles.tableWrap}>
                    <table style={styles.table}>
                        <thead>
                            <tr>
                                <th style={styles.th}>Signal</th>
                                <th style={{ ...styles.th, textAlign: 'center' }}>Tier</th>
                                <th style={{ ...styles.th, textAlign: 'right' }}>Sharpe</th>
                                <th style={{ ...styles.th, textAlign: 'right' }}>HR</th>
                                <th style={{ ...styles.th, textAlign: 'right' }}>Alpha</th>
                                <th style={{ ...styles.th, textAlign: 'center' }}>Stab</th>
                                <th style={{ ...styles.th, textAlign: 'center' }}>Cost</th>
                                <th style={{ ...styles.th, textAlign: 'center' }}>α</th>
                            </tr>
                        </thead>
                        <tbody>
                            {signals.map((s, i) => (
                                <tr key={i} style={styles.row}>
                                    <td style={styles.td}>
                                        <span style={styles.signalId}>{s.signal_id}</span>
                                    </td>
                                    <td style={{ ...styles.td, textAlign: 'center' }}>
                                        <span style={{
                                            color: TIER_COLORS[s.quality_tier] || '#94a3b8',
                                            fontWeight: '700',
                                        }}>
                                            {s.quality_tier}
                                        </span>
                                    </td>
                                    <td style={{ ...styles.td, textAlign: 'right', fontFamily: 'monospace' }}>
                                        {s.sharpe_20d?.toFixed(2)}
                                    </td>
                                    <td style={{ ...styles.td, textAlign: 'right', fontFamily: 'monospace' }}>
                                        {(s.hit_rate_20d * 100).toFixed(0)}%
                                    </td>
                                    <td style={{
                                        ...styles.td, textAlign: 'right', fontFamily: 'monospace',
                                        color: s.avg_alpha_20d >= 0 ? '#4ade80' : '#f87171',
                                    }}>
                                        {s.avg_alpha_20d >= 0 ? '+' : ''}{(s.avg_alpha_20d * 10000).toFixed(0)}bp
                                    </td>
                                    <td style={{ ...styles.td, textAlign: 'center' }}>
                                        {s.stability_class && <Badge type={s.stability_class} />}
                                    </td>
                                    <td style={{ ...styles.td, textAlign: 'center' }}>
                                        {s.cost_resilience && <Badge type={s.cost_resilience} />}
                                    </td>
                                    <td style={{ ...styles.td, textAlign: 'center' }}>
                                        {s.alpha_source && <Badge type={s.alpha_source} />}
                                    </td>
                                </tr>
                            ))}
                            {signals.length === 0 && (
                                <tr><td colSpan={8} style={{ ...styles.td, textAlign: 'center', color: '#64748b' }}>
                                    No signals to display
                                </td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            ) : (
                <div style={styles.alertList}>
                    {(data.degrading_signals || []).map((alert, i) => (
                        <div key={i} style={{
                            ...styles.alertItem,
                            borderLeft: `3px solid ${alert.severity === 'critical' ? '#ef4444' : '#eab308'}`,
                        }}>
                            <div style={styles.alertHeader}>
                                <span style={styles.alertSignal}>{alert.signal_id}</span>
                                <span style={{
                                    ...styles.alertSeverity,
                                    color: alert.severity === 'critical' ? '#f87171' : '#facc15',
                                }}>
                                    {alert.severity?.toUpperCase()}
                                </span>
                            </div>
                            <div style={styles.alertDetail}>
                                {alert.metric}: {alert.peak_value?.toFixed(2)} → {alert.current_value?.toFixed(2)}
                                <span style={{ color: '#f87171' }}> ({alert.decline_pct?.toFixed(0)}% decline)</span>
                            </div>
                        </div>
                    ))}
                    {(data.degrading_signals || []).length === 0 && (
                        <div style={{ textAlign: 'center', color: '#64748b', padding: '20px', fontSize: '13px' }}>
                            ✓ No degradation alerts
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

const styles = {
    sectionHeader: { marginBottom: '16px' },
    sectionTitle: {
        fontSize: '15px', fontWeight: '700', color: '#e2e8f0', margin: 0,
    },
    cards: {
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px',
        marginBottom: '16px',
    },
    card: {
        background: 'rgba(255,255,255,0.03)',
        borderRadius: '8px', padding: '12px 10px', textAlign: 'center',
        border: '1px solid rgba(255,255,255,0.05)',
    },
    cardValue: {
        fontSize: '22px', fontWeight: '700', color: '#e2e8f0',
        fontFamily: 'monospace',
    },
    cardLabel: {
        fontSize: '10px', color: '#64748b', textTransform: 'uppercase',
        letterSpacing: '0.05em', marginTop: '4px',
    },
    tabs: {
        display: 'flex', gap: '6px', marginBottom: '12px',
    },
    tab: {
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '6px', padding: '6px 12px', fontSize: '11px',
        color: '#94a3b8', cursor: 'pointer', fontWeight: '600',
        display: 'flex', alignItems: 'center', gap: '6px',
        transition: 'all 0.15s',
    },
    tabActive: {
        background: 'rgba(59,130,246,0.15)',
        borderColor: 'rgba(59,130,246,0.3)',
        color: '#60a5fa',
    },
    alertBadge: {
        background: '#ef4444', color: '#fff', borderRadius: '10px',
        padding: '1px 6px', fontSize: '10px', fontWeight: '700',
    },
    tableWrap: { overflowX: 'auto' },
    table: {
        width: '100%', borderCollapse: 'collapse', fontSize: '12px',
    },
    th: {
        padding: '8px 6px', color: '#64748b', fontSize: '10px',
        textTransform: 'uppercase', letterSpacing: '0.05em',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        textAlign: 'left', fontWeight: '600',
    },
    td: {
        padding: '7px 6px', borderBottom: '1px solid rgba(255,255,255,0.03)',
        color: '#cbd5e1',
    },
    row: {
        transition: 'background 0.15s',
    },
    signalId: {
        fontSize: '11px', fontFamily: 'monospace', color: '#94a3b8',
    },
    alertList: {
        display: 'flex', flexDirection: 'column', gap: '8px',
    },
    alertItem: {
        background: 'rgba(255,255,255,0.02)',
        borderRadius: '6px', padding: '10px 12px',
    },
    alertHeader: {
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: '4px',
    },
    alertSignal: {
        fontFamily: 'monospace', fontSize: '12px', color: '#e2e8f0',
        fontWeight: '600',
    },
    alertSeverity: {
        fontSize: '10px', fontWeight: '700', letterSpacing: '0.03em',
    },
    alertDetail: {
        fontSize: '11px', color: '#94a3b8',
    },
};
