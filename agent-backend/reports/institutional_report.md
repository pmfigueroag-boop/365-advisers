# Alpha Validation System — Institutional Report
**Generated:** 2026-03-21 00:04

---

## Executive Summary

| Metric | Value |
|:--|--:|
| **Verdict** | ✅ **VALID** |
| Universe Size | 94 stocks |
| Total Years | 10Y |
| Total Evaluations | 46,645 |
| Walk-Forward Windows | 14 |
| OOS BUY Trades | 22,335 |
| OOS Avg T+20d | +1.10% |
| OOS Hit Rate | 55.6% |
| OOS Sharpe (20d) | 0.12 |
| Excess Return | +0.06% |
| Net Alpha (cost-adj) | -0.14% |
| t-stat | 6.92 |
| p-value | 0.0000 |

---

## Walk-Forward Performance

| Window | Test Period | OOS Trades | Avg T+20d | Hit Rate | Sharpe | Excess |
|:--|:--|--:|--:|--:|--:|--:|
| W0 | 2019-03→2019-09 | 1689 | +0.54% | 56% | 0.07 | -0.05% |
| W1 | 2019-09→2020-03 | 1577 | -2.85% | 48% | -0.23 | -0.32% |
| W2 | 2020-03→2020-09 | 1819 | +4.05% | 65% | 0.42 | +0.01% |
| W3 | 2020-09→2021-03 | 1470 | +4.54% | 66% | 0.49 | +1.01% |
| W4 | 2021-03→2021-09 | 1399 | +0.94% | 54% | 0.16 | -0.28% |
| W5 | 2021-09→2022-03 | 1555 | +0.68% | 52% | 0.09 | +0.18% |
| W6 | 2022-03→2022-09 | 1805 | -1.52% | 44% | -0.17 | +0.09% |
| W7 | 2022-09→2023-03 | 1797 | +1.53% | 54% | 0.16 | +0.27% |
| W8 | 2023-03→2023-08 | 1685 | +0.90% | 56% | 0.13 | -0.22% |
| W9 | 2023-08→2024-02 | 1645 | +1.72% | 58% | 0.23 | -0.18% |
| W10 | 2024-02→2024-08 | 1461 | +1.44% | 59% | 0.20 | +0.14% |
| W11 | 2024-08→2025-02 | 1351 | +0.83% | 53% | 0.11 | +0.16% |
| W12 | 2025-02→2025-08 | 1598 | +1.04% | 56% | 0.11 | +0.25% |
| W13 | 2025-08→2026-02 | 1484 | +1.63% | 57% | 0.19 | +0.08% |

**Window consistency:** 9/14 profitable (64%)

---

## Statistical Significance

### Raw Alpha
- Mean OOS return: **+0.0277** (+2.77%)
- Std: 0.1090
- t-stat: **11.05** (n=1894)
- p-value: **0.0000** ✅ significant
- 95% CI: [+0.0228, +0.0326]

### Excess Return vs Benchmark
- Mean excess: **+0.0173** (+1.73%)
- t-stat: **6.92**
- p-value: **0.0000** ✅ significant
- 95% CI: [+0.0124, +0.0223]

### Bootstrap Resampling (1000 iterations)
- Mean of means: +0.0174
- 95% CI: [+0.0124, +0.0224]
- % positive: **100.0%**
- Robust: ✅ CI excludes zero

---

## Robustness Tests

### Noise Injection
- Baseline alpha: +0.0173
- Noisy alpha: +0.0109
- Degradation: 37.3%
- Robust: ✅ (< 50% degradation)

### Parameter Perturbation
| Perturbation | Alpha | Degradation | Robust |
|:--|--:|--:|:--|
| Threshold -20% (0.280) | +0.0059 | 65.9% | ❌ |
| Threshold -10% (0.315) | +0.0106 | 38.7% | ✅ |
| Threshold +10% (0.385) | +0.0231 | -33.4% | ✅ |
| Threshold +20% (0.420) | +0.0335 | -93.1% | ❌ |

---

## Subsample Analysis

| Subsample | N | Mean Return | Hit Rate | Sharpe | Consistent |
|:--|--:|--:|--:|--:|:--|
| Sector: Unknown | 1894 | +2.77% | 60% | 0.25 | ✅ |
| Period: Early OOS | 947 | +3.10% | 58% | 0.25 | ✅ |
| Period: Late OOS | 947 | +2.44% | 62% | 0.28 | ✅ |

---

## Cross-Sectional Analysis (Quintile Portfolios)

| Quintile | Avg T+20d Return |
|:--|--:|
| ⬆️ Top (Q1) | +1.18% |
| Q2 (Q2) | +0.89% |
| Q3 (Q3) | +0.99% |
| Q4 (Q4) | +1.09% |
| ⬇️ Bottom (Q5) | +0.99% |

- **Long-Short Spread:** +0.19%
- **Monotonicity Score:** 50% (1.0 = perfect)

---

## Alpha Decay by Horizon

| Horizon | Avg OOS Return |
|:--|--:|
| T+5 | +0.70% |
| T+10 | +1.36% |
| T+20 | +2.77% |
| T+60 | +6.34% |

---

## Final Verdict: ✅ VALID

Alpha is statistically significant (t>2) with positive evidence across most tests. Suitable for production with monitoring.
