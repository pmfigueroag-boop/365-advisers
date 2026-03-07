# 365 Advisers — Implementation Tracker

> **Single source of truth** for all system improvements, integrations, and evolutions.
> Updated every session. No idea gets lost.

---

## Legend

| Field | Description |
|:--|:--|
| **ID** | Unique identifier: `CAT-NNN` |
| **Feature** | Short title |
| **Description** | What it does / why it matters |
| **Status** | `PLANNED` · `DESIGNED` · `READY` · `IN_PROGRESS` · `DONE` · `DEFERRED` |
| **Priority** | `P0` (critical) · `P1` (high) · `P2` (medium) · `P3` (low) |
| **Deps** | IDs this item depends on |
| **Created** | Date added |
| **Notes** | Context, links, session refs |

---

## Data Sources

| ID | Feature | Description | Status | Priority | Deps | Created | Notes |
|:--|:--|:--|:--|:--|:--|:--|:--|
| DS-001 | External Data Provider Layer | Modular adapter architecture for external data | DONE | P0 | — | 2026-03-07 | Phase 1–6 complete |
| DS-002 | FRED Integration | Federal Reserve macro indicators adapter | DONE | P1 | DS-001 | 2026-03-07 | `adapters/fred.py` |
| DS-003 | Finnhub Integration | Market data & sentiment from Finnhub | DONE | P1 | DS-001 | 2026-03-07 | `adapters/finnhub.py` |
| DS-004 | Quiver Quantitative | Congressional trades, lobbying, contracts | DONE | P1 | DS-001 | 2026-03-07 | `adapters/quiver.py` |
| DS-005 | SEC EDGAR Ingestion | Filing events, 8-K/10-K/10-Q parsing | DONE | P1 | DS-001 | 2026-03-07 | `adapters/sec_edgar.py` |
| DS-006 | GDELT Event Ingestion | Geopolitical event stream | DONE | P1 | DS-001 | 2026-03-07 | `adapters/gdelt.py` |
| DS-007 | Alternative Data Sources | Social sentiment, patent filings, satellite | PLANNED | P3 | DS-001 | 2026-03-07 | Future exploration |
| DS-008 | Real-time WebSocket Feeds | Live price/order flow via WebSocket | PLANNED | P2 | DS-001 | 2026-03-07 | For execution layer |

---

## Source Awareness

| ID | Feature | Description | Status | Priority | Deps | Created | Notes |
|:--|:--|:--|:--|:--|:--|:--|:--|
| SA-001 | Source Coverage Metadata | CoverageTracker + completeness scoring | DONE | P0 | DS-001 | 2026-03-07 | `coverage/` package |
| SA-002 | SSE source_coverage Event | Pipeline emits coverage before scoring | DONE | P0 | SA-001 | 2026-03-07 | Part 2.5 in pipeline |
| SA-003 | CoverageBadge Component | Tiered completeness pill badge | DONE | P1 | SA-002 | 2026-03-07 | Terminal view |
| SA-004 | SourceStatusStrip Component | Horizontal source indicator dots | DONE | P1 | SA-002 | 2026-03-07 | Deep Analysis view |
| SA-005 | WarningBanner Component | Expandable alert for missing sources | DONE | P1 | SA-002 | 2026-03-07 | Deep Analysis view |
| SA-006 | Source Health Dashboard | Enhanced panel with sparklines | DONE | P1 | DS-001 | 2026-03-07 | System Intelligence |
| SA-007 | Coverage History Persistence | Store coverage reports per analysis | DONE | P2 | SA-001 | 2026-03-07 | `persistence/repository.py` |
| SA-008 | Stale Data Policy | FallbackRouter stale-data handling | DONE | P1 | DS-001 | 2026-03-07 | Configurable per domain |

---

## CIO Memo Enhancements

| ID | Feature | Description | Status | Priority | Deps | Created | Notes |
|:--|:--|:--|:--|:--|:--|:--|:--|
| CM-001 | CIO Memo Filing Context | SEC EDGAR filings in CIO narrative | DONE | P1 | DS-005 | 2026-03-07 | Optional section |
| CM-002 | CIO Memo Geopolitical Context | GDELT risk in CIO narrative | DONE | P1 | DS-006 | 2026-03-07 | Optional section |
| CM-003 | CIO Memo Macro Context | Extended FRED data in narrative | DONE | P1 | DS-002 | 2026-03-07 | Optional section |
| CM-004 | CIO Memo Sentiment Context | News sentiment enrichment | DONE | P1 | DS-003 | 2026-03-07 | Optional section |
| CM-005 | Multi-language Memo Output | Generate memo in EN/ES configurable | PLANNED | P3 | — | 2026-03-07 | Currently ES only |
| CM-006 | CIO Memo PDF Export | Institutional-grade PDF generation | PLANNED | P2 | — | 2026-03-07 | Print CSS exists |

---

## Quant Research

| ID | Feature | Description | Status | Priority | Deps | Created | Notes |
|:--|:--|:--|:--|:--|:--|:--|:--|
| QR-001 | Alpha Signals Library (50+) | 8 categories, 50+ signal detectors | DONE | P0 | — | 2026-03-05 | Fully implemented |
| QR-002 | Composite Alpha Score Engine | CASE with decay, regime, crowding | DONE | P0 | QR-001 | 2026-03-05 | 4-stage pipeline |
| QR-003 | Alpha Decay Model | Signal half-life & freshness tracking | DONE | P1 | QR-001 | 2026-03-05 | Stage 0 in CASE |
| QR-004 | Backtesting Framework | Signal backtest with walk-forward | DONE | P1 | QR-001 | 2026-03-06 | API + frontend tab |
| QR-005 | Quantitative Validation (QVF) | Bias detection, stability, consistency | DONE | P0 | — | 2026-03-06 | Full dashboard |
| QR-006 | Factor Model Integration | Multi-factor risk model (Fama-French+) | PLANNED | P2 | — | 2026-03-07 | Research phase |
| QR-007 | Options-Implied Volatility Surface | IV surface construction & analysis | PLANNED | P2 | DS-001 | 2026-03-07 | Needs options data |

---

## Research Governance

| ID | Feature | Description | Status | Priority | Deps | Created | Notes |
|:--|:--|:--|:--|:--|:--|:--|:--|
| RG-001 | Experiment Tracking | Track research experiments with outcomes | DONE | P1 | — | 2026-03-07 | DB + API |
| RG-002 | Signal Versioning | Version control for signal definitions | DONE | P1 | — | 2026-03-07 | Lineage tracking |
| RG-003 | Weight Configuration Versioning | Track scoring weight changes | DONE | P1 | — | 2026-03-07 | Audit trail |
| RG-004 | Model Lineage Tracking | Full model provenance chain | DONE | P1 | — | 2026-03-07 | DB models |
| RG-005 | Model Monitoring Hub | Unified monitoring + circuit breaker | DONE | P1 | RG-001 | 2026-03-07 | Health scores |
| RG-006 | Concept Drift Detection | Automated drift alerts | DONE | P1 | RG-005 | 2026-03-07 | System view |
| RG-007 | A/B Testing Framework | Compare signal configs live | PLANNED | P2 | RG-001 | 2026-03-07 | Shadow mode |

---

## Strategy Layer

| ID | Feature | Description | Status | Priority | Deps | Created | Notes |
|:--|:--|:--|:--|:--|:--|:--|:--|
| SL-001 | Institutional Opportunity Score | 12-factor, 4-dimension scoring | DONE | P0 | — | 2026-03-04 | Core decision input |
| SL-002 | Position Sizing Model | Volatility parity + conviction | DONE | P0 | SL-001 | 2026-03-04 | Risk-adjusted |
| SL-003 | Decision Matrix | Deterministic position classifier | DONE | P0 | SL-001 | 2026-03-04 | 9 postures |
| SL-004 | Core-Satellite Allocation | Portfolio construction strategy | DONE | P1 | SL-002 | 2026-03-05 | Portfolio engine |
| SL-005 | Scenario Analysis | What-if simulator for portfolios | DONE | P1 | SL-004 | 2026-03-05 | Frontend panel |
| SL-006 | Multi-Strategy Allocation | Kelly, risk parity, mean-variance | PLANNED | P2 | SL-004 | 2026-03-07 | Research |

---

## Execution Realism

| ID | Feature | Description | Status | Priority | Deps | Created | Notes |
|:--|:--|:--|:--|:--|:--|:--|:--|
| ER-001 | Fill Probability Model | Realistic fill simulation | PLANNED | P2 | — | 2026-03-07 | `fill_model.py` stub |
| ER-002 | Slippage Model | Market impact estimation | PLANNED | P2 | — | 2026-03-07 | Size-dependent |
| ER-003 | Transaction Cost Model | Commission + spread modeling | PLANNED | P2 | — | 2026-03-07 | Per-broker config |
| ER-004 | Shadow Portfolio Framework | Paper trading with P&L tracking | DONE | P1 | — | 2026-03-07 | Core modules |

---

## UX Improvements

| ID | Feature | Description | Status | Priority | Deps | Created | Notes |
|:--|:--|:--|:--|:--|:--|:--|:--|
| UX-001 | Institutional Terminal UX | 5-view terminal with command palette | DONE | P0 | — | 2026-03-04 | Major refactor |
| UX-002 | Market Intelligence Map | Sector heatmap + filters | DONE | P1 | — | 2026-03-04 | Phase 5 |
| UX-003 | Help Center | Comprehensive help documentation | DONE | P1 | — | 2026-03-05 | Searchable |
| UX-004 | Splitscreen Comparison | Side-by-side ticker comparison | DONE | P1 | — | 2026-03-04 | Phase 5 |
| UX-005 | CSV/Excel Export | Analysis history export | DONE | P2 | — | 2026-03-04 | Phase 5 |
| UX-006 | Onboarding Overlay | First-time user guided tour | PLANNED | P3 | — | 2026-03-07 | Design pending |
| UX-007 | Mobile Responsive Layout | Full mobile optimization | PLANNED | P3 | — | 2026-03-07 | Currently desktop |

---

## System Intelligence

| ID | Feature | Description | Status | Priority | Deps | Created | Notes |
|:--|:--|:--|:--|:--|:--|:--|:--|
| SI-001 | System Intelligence View | Unified system health dashboard | DONE | P0 | — | 2026-03-06 | QVF + drift + health |
| SI-002 | Provider Health Dashboard | EDPL provider monitoring | DONE | P1 | DS-001 | 2026-03-07 | Detailed view |
| SI-003 | Recalibration Log | Model recalibration history | DONE | P1 | — | 2026-03-06 | System view |
| SI-004 | Alerting System | Push notifications for anomalies | PLANNED | P2 | SI-001 | 2026-03-07 | Email/webhook |
| SI-005 | Audit Trail Dashboard | Full decision audit log viewer | PLANNED | P2 | RG-004 | 2026-03-07 | Compliance |

---

## Infrastructure

| ID | Feature | Description | Status | Priority | Deps | Created | Notes |
|:--|:--|:--|:--|:--|:--|:--|:--|
| IF-001 | PostgreSQL Migration | SQLite → PostgreSQL | DONE | P0 | — | 2026-03-05 | Multi-user ready |
| IF-002 | Distributed Idea Generation | Celery + Redis async scanning | DONE | P0 | — | 2026-03-05 | Workers + dispatcher |
| IF-003 | Rate Limiting Middleware | API rate limiting | DONE | P1 | — | 2026-03-04 | Per-endpoint |
| IF-004 | Unified Cache Manager | CacheManager facade | DONE | P1 | — | 2026-03-04 | 4 caches unified |
| IF-005 | Docker Compose Stack | Full containerized deployment | PLANNED | P1 | IF-001 | 2026-03-07 | Backend + frontend + DB |
| IF-006 | CI/CD Pipeline | Automated test + deploy | PLANNED | P1 | IF-005 | 2026-03-07 | GitHub Actions |
| IF-007 | Monitoring & Observability | Structured logging + metrics | PLANNED | P2 | IF-005 | 2026-03-07 | Prometheus/Grafana |
| IF-008 | Authentication & Auth | User login + API keys | PLANNED | P1 | — | 2026-03-07 | Multi-tenant |

---

## How to Use This Tracker

### Adding a new item

1. Find the appropriate category section
2. Assign the next available ID (e.g., `DS-009`)
3. Fill in all fields — especially **Description**, **Priority**, and **Deps**
4. Set Status to `PLANNED`

### Updating status

Change the Status column as work progresses:

```
PLANNED → DESIGNED → READY → IN_PROGRESS → DONE
                                          → DEFERRED
```

### Session rule

> **Every new prompt that designs or plans a feature must create a corresponding tracker entry.**
> **Every completed implementation must update its entry to `DONE`.**

### Priority guide

| Priority | Meaning | Typical timeline |
|:--|:--|:--|
| **P0** | Core — blocks other work | This session |
| **P1** | High — significant value | Next 1–2 sessions |
| **P2** | Medium — valuable but not urgent | Backlog |
| **P3** | Low — nice to have | Exploration |

### Quick stats

To get a summary, count entries by status:

- **DONE**: Features shipped and verified
- **IN_PROGRESS**: Active development
- **READY/DESIGNED**: Ready for implementation
- **PLANNED**: Identified but not yet designed
- **DEFERRED**: Deprioritized

---

*Last updated: 2026-03-07*
