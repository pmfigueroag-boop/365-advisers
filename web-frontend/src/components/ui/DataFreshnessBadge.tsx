'use client';
import React, { useState, useCallback } from 'react';

/**
 * DataFreshnessBadge — visual indicator for data source transparency.
 *
 * Shows whether data is LIVE, CACHED, or STALE with a refresh button.
 * Integrates with the `_data_freshness` metadata from API responses.
 *
 * Usage:
 *   <DataFreshnessBadge freshness={data._data_freshness} onRefresh={() => refetch(true)} />
 */

interface FreshnessInfo {
  source: 'live' | 'cached' | 'error';
  fetched_at: string;
  age_seconds: number;
  ttl_seconds: number;
  domain?: string;
}

interface DataFreshnessBadgeProps {
  /** Freshness data from API _data_freshness field. Can be a single domain or multi-domain */
  freshness?: FreshnessInfo | Record<string, FreshnessInfo> | null;
  /** Callback triggered when user clicks refresh (should call API with force_refresh=true) */
  onRefresh?: () => void;
  /** Show compact version (icon only) */
  compact?: boolean;
  /** Additional CSS class */
  className?: string;
}

/** Determine the status level from freshness data */
function getStatus(info: FreshnessInfo): 'live' | 'cached' | 'stale' | 'error' {
  if (info.source === 'error') return 'error';
  if (info.source === 'live' && info.age_seconds < 60) return 'live';
  if (info.age_seconds <= info.ttl_seconds) return 'cached';
  return 'stale';
}

function formatAge(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h`;
}

const STATUS_CONFIG = {
  live:   { icon: '🟢', label: 'LIVE',   color: '#22c55e', bg: 'rgba(34,197,94,0.10)' },
  cached: { icon: '🟡', label: 'CACHED', color: '#eab308', bg: 'rgba(234,179,8,0.10)' },
  stale:  { icon: '🔴', label: 'STALE',  color: '#ef4444', bg: 'rgba(239,68,68,0.10)' },
  error:  { icon: '⚠️', label: 'ERROR',  color: '#94a3b8', bg: 'rgba(148,163,184,0.10)' },
} as const;

export default function DataFreshnessBadge({
  freshness,
  onRefresh,
  compact = false,
  className = '',
}: DataFreshnessBadgeProps) {
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = useCallback(async () => {
    if (!onRefresh || refreshing) return;
    setRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setTimeout(() => setRefreshing(false), 1000);
    }
  }, [onRefresh, refreshing]);

  if (!freshness) return null;

  // Support both single-domain and multi-domain freshness
  let entries: { domain: string; info: FreshnessInfo }[] = [];
  if ('source' in freshness) {
    // Single domain
    entries = [{ domain: (freshness as FreshnessInfo).domain || 'data', info: freshness as FreshnessInfo }];
  } else {
    // Multi-domain (e.g., { fundamental: {...}, technical: {...} })
    entries = Object.entries(freshness).map(([domain, info]) => ({
      domain,
      info: info as FreshnessInfo,
    }));
  }

  if (entries.length === 0) return null;

  // Determine overall status (worst of all domains)
  const statusPriority = { stale: 0, error: 1, cached: 2, live: 3 };
  const worstStatus = entries.reduce<'live' | 'cached' | 'stale' | 'error'>((worst, entry) => {
    const s = getStatus(entry.info);
    return statusPriority[s] < statusPriority[worst] ? s : worst;
  }, 'live');

  const config = STATUS_CONFIG[worstStatus];

  // Format tooltip content
  const tooltipLines = entries.map((e) => {
    const s = getStatus(e.info);
    const conf = STATUS_CONFIG[s];
    return `${e.domain}: ${conf.label} (${formatAge(e.info.age_seconds)} ago)`;
  });

  if (compact) {
    return (
      <span
        className={className}
        title={tooltipLines.join('\n')}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          cursor: 'default',
          fontSize: '0.75rem',
        }}
      >
        {config.icon}
      </span>
    );
  }

  return (
    <div
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '3px 10px',
        borderRadius: '9999px',
        background: config.bg,
        border: `1px solid ${config.color}33`,
        fontSize: '0.7rem',
        fontWeight: 600,
        letterSpacing: '0.04em',
        color: config.color,
        fontFamily: 'var(--font-mono, monospace)',
        userSelect: 'none',
      }}
      title={tooltipLines.join('\n')}
    >
      <span style={{ fontSize: '0.6rem' }}>{config.icon}</span>
      <span>{config.label}</span>

      {/* Show age for cached/stale */}
      {worstStatus !== 'live' && entries.length > 0 && (
        <span style={{ opacity: 0.7, fontWeight: 400 }}>
          · {formatAge(entries.reduce((max, e) => Math.max(max, e.info.age_seconds), 0))} ago
        </span>
      )}

      {/* Refresh button */}
      {onRefresh && (
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          style={{
            background: 'transparent',
            border: 'none',
            cursor: refreshing ? 'wait' : 'pointer',
            padding: '0 2px',
            fontSize: '0.75rem',
            color: config.color,
            opacity: refreshing ? 0.5 : 0.8,
            transition: 'opacity 0.2s, transform 0.3s',
            transform: refreshing ? 'rotate(360deg)' : 'rotate(0deg)',
            lineHeight: 1,
          }}
          title="Force refresh (bypass cache)"
        >
          🔄
        </button>
      )}
    </div>
  );
}
