'use client';

import React from 'react';

const STAB_COLORS = {
    robust: '#4ade80', moderate: '#facc15', weak: '#fb923c', overfit: '#f87171',
};
const COST_COLORS = {
    resilient: '#4ade80', moderate: '#facc15', fragile: '#f87171',
};
const ALPHA_COLORS = {
    pure_alpha: '#4ade80', mixed: '#facc15', factor_beta: '#f87171',
};

function DistributionBar({ data, colors, title }) {
    const total = Object.values(data).reduce((a, b) => a + b, 0);
    if (total === 0) return null;

    return (
        <div style={styles.distBlock}>
            <div style={styles.distTitle}>{title}</div>
            {Object.entries(data).map(([label, count]) => {
                const pct = (count / total) * 100;
                return (
                    <div key={label} style={styles.distRow}>
                        <span style={styles.distLabel}>
                            <span style={{
                                display: 'inline-block', width: '8px', height: '8px',
                                borderRadius: '2px', marginRight: '6px',
                                background: colors[label] || '#94a3b8',
                            }} />
                            {label.replace('_', ' ').toUpperCase()}
                        </span>
                        <div style={styles.distBarOuter}>
                            <div style={{
                                ...styles.distBar,
                                width: `${pct}%`,
                                background: colors[label] || '#94a3b8',
                            }} />
                        </div>
                        <span style={styles.distValue}>{count}</span>
                    </div>
                );
            })}
        </div>
    );
}

export default function SystemHealth({ data }) {
    if (!data) return null;

    return (
        <div>
            <div style={styles.sectionHeader}>
                <h3 style={styles.sectionTitle}>💚 System Health</h3>
                {data.active_degradation_alerts > 0 && (
                    <span style={styles.alertBadge}>
                        {data.active_degradation_alerts} alerts
                    </span>
                )}
            </div>

            {/* Health Summary Cards */}
            <div style={styles.cards}>
                <div style={styles.card}>
                    <div style={styles.cardValue}>
                        {data.avg_stability_score?.toFixed(2) || '—'}
                    </div>
                    <div style={styles.cardLabel}>Avg Stability</div>
                </div>
                <div style={styles.card}>
                    <div style={styles.cardValue}>
                        {data.avg_half_life_days ? `${data.avg_half_life_days.toFixed(0)}d` : '—'}
                    </div>
                    <div style={styles.cardLabel}>Avg Half-Life</div>
                </div>
                <div style={styles.card}>
                    <div style={{
                        ...styles.cardValue,
                        color: data.avg_cost_drag_bps > 20 ? '#f87171' : '#4ade80',
                    }}>
                        {data.avg_cost_drag_bps?.toFixed(0) || 0}bp
                    </div>
                    <div style={styles.cardLabel}>Avg Cost Drag</div>
                </div>
                <div style={styles.card}>
                    <div style={{
                        ...styles.cardValue,
                        color: data.pending_recalibrations > 0 ? '#facc15' : '#4ade80',
                    }}>
                        {data.pending_recalibrations}
                    </div>
                    <div style={styles.cardLabel}>Pending Recal</div>
                </div>
            </div>

            {/* Distribution Charts */}
            <div style={styles.distributions}>
                <DistributionBar
                    data={data.stability_distribution || {}}
                    colors={STAB_COLORS}
                    title="Signal Stability"
                />
                <DistributionBar
                    data={data.alpha_source_distribution || {}}
                    colors={ALPHA_COLORS}
                    title="Alpha Source"
                />
                <DistributionBar
                    data={data.cost_distribution || {}}
                    colors={COST_COLORS}
                    title="Cost Resilience"
                />
            </div>

            {/* Recalibration Suggestions */}
            {(data.recalibration_suggestions || []).length > 0 && (
                <div style={styles.recalSection}>
                    <div style={styles.recalTitle}>Recalibration Queue</div>
                    {data.recalibration_suggestions.slice(0, 5).map((sug, i) => (
                        <div key={i} style={styles.recalItem}>
                            <span style={styles.recalSignal}>{sug.signal_id}</span>
                            <span style={styles.recalAction}>{sug.action}</span>
                            <span style={{
                                ...styles.recalPriority,
                                color: sug.priority === 'high' ? '#f87171' : '#facc15',
                            }}>
                                {sug.priority?.toUpperCase()}
                            </span>
                        </div>
                    ))}
                </div>
            )}

            {/* Fast Decay Warning */}
            {data.signals_with_fast_decay > 0 && (
                <div style={styles.warningBanner}>
                    ⚡ {data.signals_with_fast_decay} signal{data.signals_with_fast_decay > 1 ? 's' : ''} with
                    fast alpha decay ({'<'}10 days half-life)
                </div>
            )}

            {/* All Clear */}
            {data.active_degradation_alerts === 0 &&
                data.pending_recalibrations === 0 &&
                data.signals_with_fast_decay === 0 && (
                    <div style={styles.allClear}>
                        ✅ System healthy — no active alerts or pending recalibrations
                    </div>
                )}
        </div>
    );
}

const styles = {
    sectionHeader: {
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: '16px',
    },
    sectionTitle: {
        fontSize: '15px', fontWeight: '700', color: '#e2e8f0', margin: 0,
    },
    alertBadge: {
        background: 'rgba(239,68,68,0.15)', color: '#f87171',
        padding: '3px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: '700',
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
        fontSize: '20px', fontWeight: '700', color: '#e2e8f0',
        fontFamily: 'monospace',
    },
    cardLabel: {
        fontSize: '10px', color: '#64748b', textTransform: 'uppercase',
        letterSpacing: '0.05em', marginTop: '4px',
    },
    distributions: {
        display: 'flex', flexDirection: 'column', gap: '12px',
        marginBottom: '16px',
    },
    distBlock: {
        background: 'rgba(255,255,255,0.02)',
        borderRadius: '8px', padding: '12px',
    },
    distTitle: {
        fontSize: '11px', color: '#64748b', fontWeight: '600',
        textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px',
    },
    distRow: {
        display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px',
    },
    distLabel: {
        display: 'flex', alignItems: 'center',
        fontSize: '10px', fontWeight: '600', color: '#94a3b8', width: '100px',
        letterSpacing: '0.03em',
    },
    distBarOuter: {
        flex: 1, height: '8px', background: 'rgba(255,255,255,0.05)',
        borderRadius: '4px', overflow: 'hidden',
    },
    distBar: {
        height: '100%', borderRadius: '4px', transition: 'width 0.6s ease',
        minWidth: '2px',
    },
    distValue: {
        fontSize: '12px', color: '#e2e8f0', fontWeight: '700',
        fontFamily: 'monospace', minWidth: '24px', textAlign: 'right',
    },
    recalSection: {
        background: 'rgba(250,204,21,0.05)',
        border: '1px solid rgba(250,204,21,0.15)',
        borderRadius: '8px', padding: '12px', marginBottom: '12px',
    },
    recalTitle: {
        fontSize: '11px', color: '#facc15', fontWeight: '600',
        textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px',
    },
    recalItem: {
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '5px 0', borderBottom: '1px solid rgba(255,255,255,0.03)',
        fontSize: '11px',
    },
    recalSignal: {
        fontFamily: 'monospace', color: '#e2e8f0', fontWeight: '600', flex: 1,
    },
    recalAction: {
        color: '#94a3b8', flex: 2, textAlign: 'center',
    },
    recalPriority: {
        fontSize: '10px', fontWeight: '700', letterSpacing: '0.03em', width: '50px',
        textAlign: 'right',
    },
    warningBanner: {
        background: 'rgba(251,146,60,0.1)',
        border: '1px solid rgba(251,146,60,0.25)',
        borderRadius: '8px', padding: '10px 14px',
        color: '#fb923c', fontSize: '12px', fontWeight: '500',
        marginBottom: '12px',
    },
    allClear: {
        textAlign: 'center', color: '#4ade80', padding: '16px',
        fontSize: '13px', fontWeight: '500',
        background: 'rgba(34,197,94,0.05)',
        borderRadius: '8px',
    },
};
