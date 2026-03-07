// @ts-nocheck
'use client';

import React from 'react';

export default function OpportunityTracking({ data }: { data: any }) {
    if (!data) return null;

    const summary = data.summary;

    return (
        <div>
            <div style={styles.sectionHeader}>
                <h3 style={styles.sectionTitle}>📈 Opportunity Tracking</h3>
            </div>

            {/* Summary Cards */}
            <div style={styles.cards}>
                <div style={styles.card}>
                    <div style={styles.cardValue}>{data.total_ideas || 0}</div>
                    <div style={styles.cardLabel}>Total Ideas</div>
                </div>
                <div style={styles.card}>
                    <div style={{
                        ...styles.cardValue,
                        color: data.hit_rate_20d >= 0.55 ? '#4ade80' : data.hit_rate_20d >= 0.45 ? '#facc15' : '#f87171',
                    }}>
                        {(data.hit_rate_20d * 100).toFixed(0)}%
                    </div>
                    <div style={styles.cardLabel}>Hit Rate 20D</div>
                </div>
                <div style={styles.card}>
                    <div style={{
                        ...styles.cardValue,
                        color: data.avg_return_20d >= 0 ? '#4ade80' : '#f87171',
                    }}>
                        {data.avg_return_20d >= 0 ? '+' : ''}{(data.avg_return_20d * 100).toFixed(1)}%
                    </div>
                    <div style={styles.cardLabel}>Avg Return</div>
                </div>
                <div style={styles.card}>
                    <div style={{
                        ...styles.cardValue,
                        color: data.avg_excess_20d >= 0 ? '#4ade80' : '#f87171',
                    }}>
                        {data.avg_excess_20d >= 0 ? '+' : ''}{(data.avg_excess_20d * 100).toFixed(1)}%
                    </div>
                    <div style={styles.cardLabel}>Avg Excess</div>
                </div>
            </div>

            {/* Performance Gauge */}
            <div style={styles.gaugeSection}>
                <div style={styles.gaugeBg}>
                    <div style={{
                        ...styles.gaugeFill,
                        width: `${Math.min(Math.max(data.hit_rate_20d * 100, 0), 100)}%`,
                        background: data.hit_rate_20d >= 0.55
                            ? 'linear-gradient(90deg, #22c55e, #4ade80)'
                            : data.hit_rate_20d >= 0.45
                                ? 'linear-gradient(90deg, #eab308, #facc15)'
                                : 'linear-gradient(90deg, #dc2626, #f87171)',
                    }} />
                </div>
                <div style={styles.gaugeLabels}>
                    <span>0%</span>
                    <span style={{ color: data.hit_rate_20d >= 0.50 ? '#4ade80' : '#fb923c' }}>
                        {(data.hit_rate_20d * 100).toFixed(1)}% Hit Rate
                    </span>
                    <span>100%</span>
                </div>
            </div>

            {/* Best / Worst Ideas */}
            {summary && (summary.best_idea || summary.worst_idea) && (
                <div style={styles.ideaRow}>
                    {summary.best_idea && (
                        <div style={{ ...styles.ideaCard, borderLeft: '3px solid #22c55e' }}>
                            <div style={styles.ideaLabel}>🏆 Best Idea</div>
                            <div style={styles.ideaValue}>{summary.best_idea}</div>
                        </div>
                    )}
                    {summary.worst_idea && (
                        <div style={{ ...styles.ideaCard, borderLeft: '3px solid #ef4444' }}>
                            <div style={styles.ideaLabel}>💔 Worst Idea</div>
                            <div style={{ ...styles.ideaValue, color: '#fb923c' }}>{summary.worst_idea}</div>
                        </div>
                    )}
                </div>
            )}

            {/* Tracking Progress */}
            {summary && (
                <div style={styles.progressSection}>
                    <div style={styles.progressRow}>
                        <span style={styles.progressLabel}>Tracked</span>
                        <div style={styles.progressBar}>
                            <div style={{
                                ...styles.progressFill,
                                width: `${summary.total_ideas > 0 ? (summary.total_tracked / summary.total_ideas) * 100 : 0}%`,
                            }} />
                        </div>
                        <span style={styles.progressValue}>
                            {summary.total_tracked}/{summary.total_ideas}
                        </span>
                    </div>
                    <div style={styles.progressRow}>
                        <span style={styles.progressLabel}>Complete</span>
                        <div style={styles.progressBar}>
                            <div style={{
                                ...styles.progressFill,
                                width: `${summary.total_tracked > 0 ? (summary.total_complete / summary.total_tracked) * 100 : 0}%`,
                                background: '#818cf8',
                            }} />
                        </div>
                        <span style={styles.progressValue}>
                            {summary.total_complete}/{summary.total_tracked}
                        </span>
                    </div>
                </div>
            )}

            {data.total_ideas === 0 && (
                <div style={styles.empty}>
                    No opportunity data available yet
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
    gaugeSection: { marginBottom: '16px' },
    gaugeBg: {
        height: '10px', background: 'rgba(255,255,255,0.05)',
        borderRadius: '5px', overflow: 'hidden',
    },
    gaugeFill: {
        height: '100%', borderRadius: '5px', transition: 'width 0.8s ease',
    },
    gaugeLabels: {
        display: 'flex', justifyContent: 'space-between', marginTop: '4px',
        fontSize: '10px', color: '#64748b',
    },
    ideaRow: {
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px',
        marginBottom: '16px',
    },
    ideaCard: {
        background: 'rgba(255,255,255,0.02)',
        borderRadius: '6px', padding: '10px 12px',
    },
    ideaLabel: {
        fontSize: '10px', color: '#64748b', textTransform: 'uppercase',
        letterSpacing: '0.05em', marginBottom: '4px',
    },
    ideaValue: {
        fontSize: '13px', fontWeight: '600', color: '#4ade80',
        fontFamily: 'monospace',
    },
    progressSection: {
        background: 'rgba(255,255,255,0.02)',
        borderRadius: '8px', padding: '12px',
    },
    progressRow: {
        display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px',
    },
    progressLabel: {
        fontSize: '10px', color: '#94a3b8', fontWeight: '600',
        textTransform: 'uppercase', width: '65px', letterSpacing: '0.03em',
    },
    progressBar: {
        flex: 1, height: '6px', background: 'rgba(255,255,255,0.05)',
        borderRadius: '3px', overflow: 'hidden',
    },
    progressFill: {
        height: '100%', borderRadius: '3px',
        background: '#3b82f6', transition: 'width 0.5s ease',
    },
    progressValue: {
        fontSize: '10px', color: '#94a3b8', fontFamily: 'monospace', minWidth: '50px',
        textAlign: 'right',
    },
    empty: {
        textAlign: 'center', color: '#64748b', padding: '30px', fontSize: '13px',
    },
};
