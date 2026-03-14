# CASE Predictive Validation Report

**Generated:** 2026-03-14 10:32  
**Universe:** 47 tickers · **Outcomes:** 141 data points  
**Horizons:** 5D, 20D, 60D · **Benchmark:** SPY  
**Execution Time:** 377.7s

---

## 1. CASE Score Distribution

| Ticker | CASE | Environment | Signals | Sector |
|:--|--:|:--|--:|:--|
| **AAPL** | 78.0 | Strong Opportunity | 11/50 | Technology |
| **CSCO** | 78.0 | Strong Opportunity | 9/50 | Technology |
| **V** | 78.0 | Strong Opportunity | 12/50 | Financial Services |
| **MA** | 78.0 | Strong Opportunity | 12/50 | Financial Services |
| **GS** | 78.0 | Strong Opportunity | 9/50 | Financial Services |
| **JNJ** | 73.0 | Strong Opportunity | 11/50 | Healthcare |
| **CRM** | 67.5 | Strong Opportunity | 10/50 | Technology |
| **BAC** | 66.8 | Strong Opportunity | 11/50 | Financial Services |
| **MSFT** | 66.0 | Strong Opportunity | 12/50 | Technology |
| **GOOGL** | 66.0 | Strong Opportunity | 13/50 | Communication Services |
| **META** | 66.0 | Strong Opportunity | 11/50 | Communication Services |
| **AVGO** | 66.0 | Strong Opportunity | 12/50 | Technology |
| **ADBE** | 66.0 | Strong Opportunity | 14/50 | Technology |
| **BLK** | 66.0 | Strong Opportunity | 10/50 | Financial Services |
| **LLY** | 60.0 | Strong Opportunity | 8/50 | Healthcare |
| **CAT** | 60.0 | Strong Opportunity | 7/50 | Industrials |
| **GE** | 60.0 | Strong Opportunity | 9/50 | Industrials |
| **PEP** | 60.0 | Strong Opportunity | 6/50 | Consumer Defensive |
| **NEE** | 60.0 | Strong Opportunity | 6/50 | Utilities |
| **JPM** | 58.5 | Neutral | 10/50 | Financial Services |
| **UNH** | 55.0 | Neutral | 8/50 | Healthcare |
| **MRK** | 55.0 | Neutral | 6/50 | Healthcare |
| **NKE** | 55.0 | Neutral | 5/50 | Consumer Cyclical |
| **HON** | 55.0 | Neutral | 5/50 | Industrials |
| **PG** | 55.0 | Neutral | 6/50 | Consumer Defensive |
| **KO** | 55.0 | Neutral | 6/50 | Consumer Defensive |
| **DUK** | 55.0 | Neutral | 4/50 | Utilities |
| **APD** | 55.0 | Neutral | 4/50 | Basic Materials |
| **PLD** | 55.0 | Neutral | 4/50 | Real Estate |
| **AMT** | 55.0 | Neutral | 6/50 | Real Estate |
| **BA** | 54.0 | Neutral | 7/50 | Industrials |
| **NVDA** | 50.0 | Neutral | 12/50 | Technology |
| **CVX** | 49.5 | Neutral | 4/50 | Energy |
| **UPS** | 46.5 | Neutral | 7/50 | Industrials |
| **CMCSA** | 45.9 | Neutral | 10/50 | Communication Services |
| **INTC** | 45.0 | Neutral | 7/50 | Technology |
| **PFE** | 45.0 | Neutral | 5/50 | Healthcare |
| **XOM** | 45.0 | Neutral | 5/50 | Energy |
| **COP** | 45.0 | Neutral | 5/50 | Energy |
| **COST** | 45.0 | Neutral | 7/50 | Consumer Defensive |
| **ABBV** | 42.0 | Neutral | 7/50 | Healthcare |
| **SBUX** | 40.5 | Neutral | 6/50 | Consumer Cyclical |
| **SLB** | 40.5 | Neutral | 6/50 | Energy |
| **DIS** | 40.5 | Neutral | 6/50 | Communication Services |
| **TSLA** | 40.0 | Neutral | 4/50 | Consumer Cyclical |
| **NFLX** | 40.0 | Neutral | 9/50 | Communication Services |
| **AMZN** | 35.0 | Weak | 7/50 | Consumer Cyclical |

**Stats:** Mean=56.4, Median=55.0, Min=35.0, Max=78.0

---

## 2. Hit Rate by CASE Bucket

### 5D Horizon

| CASE Bucket | N | Hit Rate | Avg Return | Median Return | Excess Return |
|:--|--:|--:|--:|--:|--:|
| 20–40 (Weak) | 1 | 🔴 0.0% | -2.60% | -2.60% | -1.10% |
| 40–60 (Neutral) | 27 | 🔴 29.6% | -0.98% | -1.39% | +0.52% |
| 60–80 (Strong) | 19 | 🔴 15.8% | -2.74% | -3.22% | -1.24% |

### 20D Horizon

| CASE Bucket | N | Hit Rate | Avg Return | Median Return | Excess Return |
|:--|--:|--:|--:|--:|--:|
| 20–40 (Weak) | 1 | 🟢 100.0% | +4.04% | +4.04% | +6.83% |
| 40–60 (Neutral) | 27 | 🔴 25.9% | -1.61% | -3.02% | +1.18% |
| 60–80 (Strong) | 19 | 🔴 15.8% | -4.17% | -4.44% | -1.39% |

### 60D Horizon

| CASE Bucket | N | Hit Rate | Avg Return | Median Return | Excess Return |
|:--|--:|--:|--:|--:|--:|
| 20–40 (Weak) | 1 | 🔴 0.0% | -6.68% | -6.68% | -4.26% |
| 40–60 (Neutral) | 27 | 🟢 74.1% | +7.39% | +4.54% | +9.82% |
| 60–80 (Strong) | 19 | 🔴 26.3% | -5.74% | -7.10% | -3.32% |

---

## 3. Monotonicity Analysis

_Does higher CASE → higher returns?_

**5D:** ⚠️ 1 violation(s)
  - 60–80 (Strong) (avg=-0.0274) < 40–60 (Neutral) (avg=-0.0098)

**20D:** ⚠️ 2 violation(s)
  - 40–60 (Neutral) (avg=-0.0161) < 20–40 (Weak) (avg=0.0404)
  - 60–80 (Strong) (avg=-0.0417) < 40–60 (Neutral) (avg=-0.0161)

**60D:** ⚠️ 1 violation(s)
  - 60–80 (Strong) (avg=-0.0574) < 40–60 (Neutral) (avg=0.0739)

---

## 4. Sector Analysis (20D Horizon)

| Sector | N | Avg CASE | Hit Rate | Avg Return |
|:--|--:|--:|--:|--:|
| Utilities | 2 | 57.5 | 100.0% | +4.05% |
| Energy | 4 | 45.0 | 75.0% | +3.06% |
| Communication Services | 5 | 51.7 | 20.0% | +1.95% |
| Basic Materials | 1 | 55.0 | 0.0% | -1.21% |
| Technology | 8 | 64.6 | 25.0% | -1.27% |
| Consumer Cyclical | 4 | 42.6 | 50.0% | -2.52% |
| Healthcare | 6 | 55.0 | 0.0% | -2.57% |
| Consumer Defensive | 4 | 53.8 | 25.0% | -2.64% |
| Real Estate | 2 | 55.0 | 0.0% | -2.70% |
| Industrials | 5 | 55.1 | 0.0% | -8.62% |
| Financial Services | 6 | 70.9 | 0.0% | -8.79% |

---

## 5. Overall Summary

| Horizon | N | Hit Rate | Avg Return | Avg Excess |
|:--|--:|--:|--:|--:|
| 5D | 47 | 23.4% | -1.73% | -0.23% |
| 20D | 47 | 23.4% | -2.53% | +0.26% |
| 60D | 47 | 53.2% | +1.78% | +4.21% |

---

## 6. Verdict

- ❌ High CASE (≥60) hit rate: 15.8% ≤ 55% threshold
- ❌ Return spread (high vs low CASE): -8.22% ≤ 2% threshold
- ⚠️ 20D monotonicity violated (2 violations)


**Score: 0/3 criteria passed.**

> [!WARNING]
> CASE shows **weak/no predictive signal**. Thresholds and weights need recalibration.
