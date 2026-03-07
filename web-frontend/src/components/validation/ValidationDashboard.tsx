// @ts-nocheck
'use client';

import React, { useState, useEffect } from 'react';
import SignalLeaderboard from './SignalLeaderboard';
import DetectorPerformance from './DetectorPerformance';
import OpportunityTracking from './OpportunityTracking';
import SystemHealth from './SystemHealth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ValidationDashboard() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [lastRefresh, setLastRefresh] = useState(null);

    const fetchDashboard = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_URL}/validation/intelligence`);
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const json = await res.json();
            setData(json);
            setLastRefresh(new Date());
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDashboard();
    }, []);

    if (loading && !data) {
        return (
            <div style={styles.loadingContainer}>
                <div style={styles.spinner} />
                <p style={styles.loadingText}>Loading QVF Intelligence...</p>
            </div>
        );
    }

    return (
        <div style={styles.container}>
            {/* Header */}
            <div style={styles.header}>
                <div>
                    <h2 style={styles.title}>
                        <span style={styles.titleIcon}>🧠</span>
                        QVF Intelligence Dashboard
                    </h2>
                    <p style={styles.subtitle}>
                        Quantitative Validation Framework — Signal Health Monitor
                    </p>
                </div>
                <div style={styles.headerRight}>
                    {lastRefresh && (
                        <span style={styles.timestamp}>
                            Updated {lastRefresh.toLocaleTimeString()}
                        </span>
                    )}
                    <button
                        onClick={fetchDashboard}
                        style={styles.refreshBtn}
                        disabled={loading}
                    >
                        {loading ? '⟳' : '↻'} Refresh
                    </button>
                </div>
            </div>

            {error && (
                <div style={styles.errorBanner}>
                    ⚠️ {error}
                </div>
            )}

            {data && (
                <div style={styles.grid}>
                    <div style={styles.section}>
                        <SignalLeaderboard data={data.leaderboard} />
                    </div>
                    <div style={styles.section}>
                        <DetectorPerformance data={data.detector_performance} />
                    </div>
                    <div style={styles.section}>
                        <OpportunityTracking data={data.opportunity_tracking} />
                    </div>
                    <div style={styles.section}>
                        <SystemHealth data={data.system_health} />
                    </div>
                </div>
            )}
        </div>
    );
}

const styles = {
    container: {
        padding: '0',
        maxWidth: '100%',
    },
    header: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '24px',
        paddingBottom: '16px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
    },
    title: {
        fontSize: '20px',
        fontWeight: '700',
        color: '#e2e8f0',
        margin: '0 0 4px 0',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
    },
    titleIcon: {
        fontSize: '22px',
    },
    subtitle: {
        fontSize: '12px',
        color: '#64748b',
        margin: 0,
        letterSpacing: '0.05em',
        textTransform: 'uppercase',
    },
    headerRight: {
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
    },
    timestamp: {
        fontSize: '11px',
        color: '#64748b',
    },
    refreshBtn: {
        background: 'rgba(59,130,246,0.15)',
        color: '#60a5fa',
        border: '1px solid rgba(59,130,246,0.3)',
        borderRadius: '6px',
        padding: '6px 14px',
        fontSize: '12px',
        fontWeight: '600',
        cursor: 'pointer',
        transition: 'all 0.2s',
    },
    grid: {
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '20px',
    },
    section: {
        background: 'rgba(15,23,42,0.6)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '12px',
        padding: '20px',
        backdropFilter: 'blur(12px)',
    },
    loadingContainer: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '80px 0',
        gap: '16px',
    },
    spinner: {
        width: '32px',
        height: '32px',
        border: '3px solid rgba(59,130,246,0.2)',
        borderTop: '3px solid #3b82f6',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
    },
    loadingText: {
        color: '#64748b',
        fontSize: '13px',
    },
    errorBanner: {
        background: 'rgba(239,68,68,0.1)',
        border: '1px solid rgba(239,68,68,0.3)',
        borderRadius: '8px',
        padding: '10px 16px',
        color: '#fca5a5',
        fontSize: '13px',
        marginBottom: '16px',
    },
};
