'use client';

import React from 'react';

export default function DetectorPerformance({ data }) {
    if (!data) return null;

    const detectors = data.detectors || [];
    const byConfidence = data.by_confidence || {};

    return (
        <div>
            <div style={styles.sectionHeader}>
                <h3 style={styles.sectionTitle}>🎯 Detector Performance</h3>
                {data.total_detectors > 0 && (
                    <span style={styles.badge}>{data.total_detectors} active</span>
                )}
            </div>

            {/* Best / Worst badges */}
            {(data.best_detector || data.worst_detector) && (
                <div style={styles.highlightRow}>
                    {data.best_detector && (
                        <div style={styles.highlightCard}>
                            <span style={styles.highlightIcon}>🥇</span>
                            <div>
                                <div style={styles.highlightLabel}>Best Detector</div>
                                <div style={styles.highlightValue}>{data.best_detector}</div>
                            </div>
                        </div>
                    )}
                    {data.worst_detector && (
                        <div style={{ ...styles.highlightCard, borderColor: 'rgba(239,68,68,0.2)' }}>
                            <span style={styles.highlightIcon}>🥉</span>
                            <div>
                                <div style={styles.highlightLabel}>Worst Detector</div>
                                <div style={{ ...styles.highlightValue, color: '#fb923c' }}>{data.worst_detector}</div>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Detector Table */}
            <div style={styles.tableWrap}>
                <table style={styles.table}>
                    <thead>
                        <tr>
                            <th style={styles.th}>Detector</th>
                            <th style={{ ...styles.th, textAlign: 'right' }}>Ideas</th>
                            <th style={{ ...styles.th, textAlign: 'right' }}>Hit Rate</th>
                            <th style={{ ...styles.th, textAlign: 'right' }}>Avg Return</th>
                            <th style={{ ...styles.th, textAlign: 'right' }}>Sharpe</th>
                        </tr>
                    </thead>
                    <tbody>
                        {detectors.map((d, i) => (
                            <tr key={i}>
                                <td style={styles.td}>
                                    <span style={styles.detectorName}>{d.label}</span>
                                </td>
                                <td style={{ ...styles.td, textAlign: 'right', fontFamily: 'monospace' }}>
                                    {d.idea_count}
                                </td>
                                <td style={{ ...styles.td, textAlign: 'right' }}>
                                    <div style={styles.barContainer}>
                                        <div style={{
                                            ...styles.bar,
                                            width: `${Math.min(d.hit_rate * 100, 100)}%`,
                                            background: d.hit_rate >= 0.55 ? '#4ade80' : d.hit_rate >= 0.45 ? '#facc15' : '#f87171',
                                        }} />
                                        <span style={styles.barLabel}>{(d.hit_rate * 100).toFixed(0)}%</span>
                                    </div>
                                </td>
                                <td style={{
                                    ...styles.td, textAlign: 'right', fontFamily: 'monospace',
                                    color: d.avg_return >= 0 ? '#4ade80' : '#f87171',
                                }}>
                                    {d.avg_return >= 0 ? '+' : ''}{(d.avg_return * 100).toFixed(1)}%
                                </td>
                                <td style={{
                                    ...styles.td, textAlign: 'right', fontFamily: 'monospace',
                                    color: d.sharpe >= 1 ? '#4ade80' : d.sharpe >= 0 ? '#facc15' : '#f87171',
                                }}>
                                    {d.sharpe?.toFixed(2)}
                                </td>
                            </tr>
                        ))}
                        {detectors.length === 0 && (
                            <tr><td colSpan={5} style={{ ...styles.td, textAlign: 'center', color: '#64748b' }}>
                                No detector data available
                            </td></tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Confidence Distribution */}
            {Object.keys(byConfidence).length > 0 && (
                <div style={styles.confSection}>
                    <div style={styles.confTitle}>Confidence Distribution</div>
                    {Object.entries(byConfidence).map(([level, acc]) => (
                        <div key={level} style={styles.confRow}>
                            <span style={styles.confLabel}>
                                {level.toUpperCase()}
                            </span>
                            <div style={styles.confBarOuter}>
                                <div style={{
                                    ...styles.confBar,
                                    width: `${Math.min(acc.hit_rate * 100, 100)}%`,
                                    background: level === 'high' ? '#4ade80' : level === 'medium' ? '#facc15' : '#f87171',
                                }} />
                            </div>
                            <span style={styles.confValue}>
                                {(acc.hit_rate * 100).toFixed(0)}% HR (n={acc.idea_count})
                            </span>
                        </div>
                    ))}
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
    badge: {
        background: 'rgba(59,130,246,0.15)', color: '#60a5fa',
        padding: '3px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: '600',
    },
    highlightRow: {
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px',
        marginBottom: '16px',
    },
    highlightCard: {
        display: 'flex', alignItems: 'center', gap: '10px',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(34,197,94,0.2)',
        borderRadius: '8px', padding: '10px 12px',
    },
    highlightIcon: { fontSize: '20px' },
    highlightLabel: {
        fontSize: '10px', color: '#64748b', textTransform: 'uppercase',
        letterSpacing: '0.05em',
    },
    highlightValue: {
        fontSize: '13px', color: '#4ade80', fontWeight: '600', fontFamily: 'monospace',
    },
    tableWrap: { overflowX: 'auto', marginBottom: '16px' },
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
    detectorName: {
        fontFamily: 'monospace', fontSize: '11px', color: '#94a3b8',
    },
    barContainer: {
        display: 'flex', alignItems: 'center', gap: '6px',
        justifyContent: 'flex-end',
    },
    bar: {
        height: '6px', borderRadius: '3px', minWidth: '4px',
        transition: 'width 0.5s ease',
    },
    barLabel: {
        fontSize: '11px', fontFamily: 'monospace', minWidth: '32px',
        textAlign: 'right',
    },
    confSection: {
        background: 'rgba(255,255,255,0.02)',
        borderRadius: '8px', padding: '12px',
    },
    confTitle: {
        fontSize: '11px', color: '#64748b', fontWeight: '600',
        textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px',
    },
    confRow: {
        display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px',
    },
    confLabel: {
        fontSize: '10px', fontWeight: '700', color: '#94a3b8', width: '60px',
        letterSpacing: '0.03em',
    },
    confBarOuter: {
        flex: 1, height: '8px', background: 'rgba(255,255,255,0.05)',
        borderRadius: '4px', overflow: 'hidden',
    },
    confBar: {
        height: '100%', borderRadius: '4px', transition: 'width 0.5s ease',
    },
    confValue: {
        fontSize: '10px', color: '#94a3b8', fontFamily: 'monospace', minWidth: '100px',
    },
};
