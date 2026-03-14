# 365 Advisers — Manual de Usuario

> Manual completo de referencia para el Investment Intelligence Terminal.

---

## Índice

1. [Información General](#1-información-general)
2. [Arquitectura de la Interfaz](#2-arquitectura-de-la-interfaz)
3. [Terminal — Vista Ejecutiva](#3-terminal--vista-ejecutiva)
4. [Market — Inteligencia de Mercado](#4-market--inteligencia-de-mercado)
5. [Ideas — Explorador de Oportunidades](#5-ideas--explorador-de-oportunidades)
6. [Analysis — Análisis Profundo](#6-analysis--análisis-profundo)
7. [Portfolio — Gestión de Portafolio](#7-portfolio--gestión-de-portafolio)
8. [System — Monitoreo del Sistema](#8-system--monitoreo-del-sistema)
9. [Strategy Lab — Laboratorio de Estrategias](#9-strategy-lab--laboratorio-de-estrategias)
10. [Marketplace — Repositorio de Estrategias](#10-marketplace--repositorio-de-estrategias)
11. [AI Assistant — Asistente de Investigación](#11-ai-assistant--asistente-de-investigación)
12. [Pilot — Centro de Comando](#12-pilot--centro-de-comando)
13. [Alpha Engine — Motor Cuantitativo](#13-alpha-engine--motor-cuantitativo)
14. [Herramientas Globales](#14-herramientas-globales)
15. [Interpretación de Señales](#15-interpretación-de-señales)
16. [API de Referencia](#16-api-de-referencia)
17. [Solución de Problemas](#17-solución-de-problemas)

---

## 1. Información General

**365 Advisers** es una plataforma de inteligencia de inversión de grado institucional que combina:

- **4 agentes IA especializados** (Fundamental) con filosofías de inversión distintas
- **Motor técnico determinista** con 15+ indicadores calculados en ~2-3 segundos
- **Alpha Intelligence Stack** de 8 factores cuantitativos
- **Comité de Inversión** automatizado que sintetiza un veredicto unificado

### Requisitos del Sistema

| Componente | Versión Mínima | Puerto | Propósito |
|:---|:---|:---|:---|
| Python | 3.11+ | 8000 | Backend (FastAPI + LangGraph) |
| Node.js | 18+ | 3000 | Frontend (Next.js + Turbopack) |

### Variables de Entorno Requeridas

Crear un archivo `.env` en `agent-backend/`:

```env
GOOGLE_API_KEY=tu-api-key-aquí
# O alternativamente:
GEMINI_API_KEY=tu-api-key-aquí
```

### Iniciar el Sistema

```bash
# Terminal 1: Backend
cd 365-advisers/agent-backend
.\venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
cd 365-advisers/web-frontend
npm run dev
```

Accede a la plataforma en **http://localhost:3000**.

---

## 2. Arquitectura de la Interfaz

La interfaz sigue un diseño de terminal financiero profesional con 4 zonas principales:

| Zona | Descripción |
|:---|:---|
| **Barra Superior** | Logo, campo de búsqueda de ticker, botón Analyze, toolbar (Refresh, Export, Watchlist, Command Palette, Help). |
| **Tabs de Navegación** | 11 vistas especializadas organizadas por tier. |
| **Panel Lateral Izquierdo** | Navegación contextual + Watchlist con señales en tiempo real. Se expande (200px) / colapsa (56px). |
| **Canvas Principal** | Contenido de la vista activa. |

### Navegación por Teclado

| Atajo | Acción |
|:---|:---|
| `Alt+1` | Terminal |
| `Alt+2` | Market |
| `Alt+3` | Ideas |
| `Alt+4` | Analysis |
| `Alt+5` | Portfolio |
| `Alt+6` | System |
| `Alt+7` | Strategy Lab |
| `Alt+8` | Marketplace |
| `Alt+9` | AI Assistant |
| `Alt+0` | Pilot |
| `Ctrl+K` | Command Palette |
| `Shift+?` | Centro de Ayuda |

---

## 3. Terminal — Vista Ejecutiva

**Acceso:** `Alt+1` • Tab "Terminal"

La vista por defecto. Centro de decisión ejecutiva del terminal.

### Estado Vacío (Empty State)
Cuando no hay análisis activo, se muestra un hero premium con gradientes animados y campo de búsqueda autocomplete para activos del S&P 500.

### Después de Analizar

Al ejecutar un análisis, la vista muestra:

- **Verdict Hero** — Veredicto animado (BUY / HOLD / SELL) con efecto de revelación
- **Opportunity Score** — Gauge semicircular con puntuación 0-10
- **Signal Environment** — Régimen de mercado, CASE score, y estado de crowding
- **Barra de progreso** — Seguimiento del pipeline: Market → Fundamental → Technical → Alpha → Decision

### Watchlist Dashboard

Si tienes tickers en tu watchlist, el estado vacío se transforma en un **Coverage Dashboard** con tarjetas de acción rápida para cada ticker, mostrando la última señal conocida y un botón "Run Committee" para re-analizar.

---

## 4. Market — Inteligencia de Mercado

**Acceso:** `Alt+2` • Tab "Market"

Vista panorámica del mercado para contextualizar decisiones.

### Componentes

- **Heatmap Sectorial** — Rendimiento visual por sector e industria
- **Signal Clusters** — Agrupación de señales por patrón
- **Risk Signals** — Monitoreo de triggers de riesgo sistémico
- **Ranking Board** — Clasificación de activos por opportunity score (disponible después de un scan de Ideas)

---

## 5. Ideas — Explorador de Oportunidades

**Acceso:** `Alt+3` • Tab "Ideas"

Motor de generación de ideas de inversión (IGE) que escanea el universo de activos buscando oportunidades por factores.

### Cómo Usar

1. **Scan Universe** — Escanea todos los tickers de tu watchlist
2. **Auto Scan** — Deja que el sistema busque oportunidades automáticamente en un universo más amplio

### Detectores de Estilo

| Detector | Señales Clave |
|:---|:---|
| **Value** | Alto FCF Yield, bajo P/E, bajo P/B |
| **Quality** | Alto ROIC, márgenes estables, deuda baja |
| **Momentum** | Golden Cross, alineación RSI, surge de volumen |
| **Reversal** | Métricas oversold, capitulación de volumen |
| **Event** | Deltas de score significativos, sorpresas de earnings |

### Interpretar Ideas

- **Confidence:** Alta (60%+), Media (40-60%), Baja (<40%) de señales confirmadas
- **Signal Strength:** Proporción de señales disparadas dentro del detector
- **Confidence Bonus:** Señales validadas con alto Sharpe/Hit Rate reciben peso adicional

### Flujo Ideas → Analysis

Al hacer clic en "Analyze" en una idea, el sistema:
1. Navega automáticamente a la vista Analysis
2. Ejecuta el pipeline completo sobre ese ticker
3. Marca la idea como "analyzed"
4. Si luego añades el ticker a la watchlist, la idea se marca como "validated"

---

## 6. Analysis — Análisis Profundo

**Acceso:** `Alt+4` • Tab "Analysis"

Bóveda de evidencia completa para un solo activo, organizada en múltiples sub-tabs.

### Sub-Tabs Disponibles

#### Fundamental — Comité de Inversión
4 agentes IA especializados analizan simultáneamente, cada uno con una filosofía de inversión:

| Agente | Filosofía | Enfoque |
|:---|:---|:---|
| **Quality & Moat** | Munger/Fisher | ROIC, márgenes, ventajas competitivas |
| **Capital Allocation** | Icahn/Activistas | FCF, buybacks, deuda, eficiencia |
| **Value & Margin of Safety** | Graham/Buffett | P/E, P/B, FCF yield, EV/EBITDA |
| **Risk & Macro Stress** | Marks/Dalio | Ciclos macro, riesgo regulatorio, geopolítica |

Cada agente emite:
- **Señal** (BUY / HOLD / SELL)
- **Convicción** (0-10)
- **Memo narrativo** con tesis y evidencia

#### Technical — Motor Determinista

| Módulo | Indicadores | Señales |
|:---|:---|:---|
| **Trend** | SMA50, SMA200, MACD, Golden/Death Cross | BULLISH / BEARISH |
| **Momentum** | RSI(14), Stochastic %K/%D | OVERSOLD / NEUTRAL / OVERBOUGHT |
| **Volatility** | Bollinger Bands, ATR | LOW / NORMAL / HIGH |
| **Volume** | OBV, Vol/Avg20 | RISING / FLAT / FALLING |
| **Structure** | Soporte/Resistencia, Breakout Probability | UP / DOWN / SIDEWAYS |

Incluye además:
- **Regime Detection** — Detección de regímenes de tendencia y volatilidad
- **Multi-Timeframe** — Scoring en 4 timeframes (1H, 4H, 1D, 1W) con lógica de acuerdo/conflicto
- **Sector-Relative Strength** — Rendimiento vs. benchmark sectorial
- **Specialty Opinions** — 5 opiniones especializadas (Trend, Momentum, Volatility, Volume, Structure) con consenso

#### Alpha Signals — CASE Engine
Radar chart mostrando cobertura de señales en 8 dimensiones cuantitativas.

#### Investment Thesis
Historia de inversión CIO con catalizadores, riesgos y recomendación de timing.

#### Combined — Veredicto Unificado
- **Unified Verdict Hero** — Gauge semicircular con score agregado
- **Dual Score Bars** — Comparación Fundamental vs. Technical
- **Synthesis Narrative** — Perspectiva balanceada del supervisor

---

## 7. Portfolio — Gestión de Portafolio

**Acceso:** `Alt+5` • Tab "Portfolio"

Dashboard de inteligencia de portafolio y construcción de asignaciones.

### Core-Satellite Strategy

| Componente | Criterio | Asignación Target |
|:---|:---|:---|
| **CORE** | Quality Score ≥ 7, Financials ≥ 7 | ~70% |
| **SATELLITE** | Alto Opportunity Score, mayor riesgo | ~30% |

### Funcionalidades

- **Portfolio Builder** — Construcción automática basada en la watchlist analizada
- **Volatility Parity Sizing** — Pesos ajustados por ATR para ecualizar contribución al riesgo
- **What-If Simulator** — Simulación de escenarios
- **Performance Metrics** — Tracking de métricas de rendimiento

### Flujo Analysis → Portfolio

Desde la vista Analysis, puedes añadir un activo analizado directamente al portafolio pulsando el ícono ⭐ (Watchlist), que lo incorpora a la cobertura del portafolio.

---

## 8. System — Monitoreo del Sistema

**Acceso:** `Alt+6` • Tab "System"

Dashboard de salud operativa de la plataforma.

### Métricas Disponibles

- **Signal Pipeline Health** — Estado de cada etapa del pipeline
- **Drift Alerts** — Alertas de drift en modelos y señales
- **Provider Status** — Salud de proveedores de datos (yfinance, LLM, etc.)
- **Performance Logs** — Tiempos de ejecución y tasas de error
- **Recalibration Status** — Estado de calibración de los motores

---

## 9. Strategy Lab — Laboratorio de Estrategias

**Acceso:** `Alt+7` • Tab "Strategy Lab"

Workspace de investigación estilo Bloomberg con layout multi-panel.

### Características

- **Layout 4 Paneles** — Configuración estilo terminal financiero profesional
- **Backtesting Engine** — Validación empírica de señales con análisis de retornos forward
- **Comparación de Estrategias** — Análisis lado a lado de múltiples enfoques
- **Walk-Forward Optimization** — Optimización de parámetros de scoring

> [!NOTE]
> El Strategy Lab tiene su propio shell independiente (no usa el TerminalShell estándar) para maximizar el área de trabajo disponible.

---

## 10. Marketplace — Repositorio de Estrategias

**Acceso:** `Alt+8` • Tab "Marketplace"

Catálogo de estrategias institucionales pre-armadas, listas para importar.

### Estrategias Disponibles

El marketplace incluye 6 estrategias institucionales optimizadas (ej: MomQual v2 con Sharpe ~2.1). Cada estrategia incluye:

- Descripción y filosofía de inversión
- Métricas históricas (Sharpe, Sortino, Max Drawdown)
- Composición del universo
- Botón **Import to Lab** para personalización en Strategy Lab

---

## 11. AI Assistant — Asistente de Investigación

**Acceso:** `Alt+9` • Tab "AI Assistant"

Chat IA conectado al Knowledge Graph de investigación de la plataforma.

### Capacidades

- **Consultas de mercado** — Pregunta sobre cualquier activo o sector
- **Knowledge Graph** — Acceso a toda la investigación previa y memos generados
- **Integración Strategy Lab** — Puede sugerir y ejecutar estrategias
- **Contexto persistente** — Mantiene el hilo de la conversación de investigación

---

## 12. Pilot — Centro de Comando

**Acceso:** `Alt+0` • Tab "Pilot"

Centro de comando en tiempo real para la validación del despliegue de 12 semanas.

### Dashboard

- **Equity Curve** — Curva de equity en tiempo real (paper trading)
- **Alpha Tracking** — Performance vs. benchmark
- **Alpha Leaderboard** — Ranking de estrategias por alpha generado
- **Mark-to-Market** — Valoración en tiempo real de posiciones

### Live Broker Integration

La plataforma soporta un adaptador de broker pluggable:
- **Paper Trading** — Modo simulación para validación
- **Alpaca** — Integración con Alpaca Trading API
- **Interactive Brokers** — Adaptador para IB (en desarrollo)

---

## 13. Alpha Engine — Motor Cuantitativo

**Acceso:** Tab "Alpha Engine"

Vista dedicada al Alpha Intelligence Stack — sistema de scoring cuantitativo de 8 factores.

### Factores del CASE Engine

El Composite Alpha Score Engine (CASE) evalúa cada activo en 8 dimensiones:

1. **Value** — Métricas de valoración vs. fundamentales
2. **Quality** — Calidad del negocio (ROIC, márgenes, estabilidad)
3. **Momentum** — Tendencia de precio y volumen
4. **Growth** — Crecimiento de revenue y earnings
5. **Sentiment** — Sentimiento e insider activity
6. **Risk** — Métricas de riesgo y volatilidad
7. **Technical** — Señales técnicas consolidadas
8. **Catalyst** — Eventos próximos y catalizadores

### Ranking Universe

El Alpha Engine genera un ranking del universo completo, permitiendo comparar oportunidades cuantitativamente.

---

## 14. Herramientas Globales

### Command Palette (`Ctrl+K`)

Panel de comandos universal para:
- **Buscar tickers** — Búsqueda rápida con autocompletado
- **Navegar vistas** — Saltar a cualquier vista por nombre
- **Ejecutar acciones** — Analizar, exportar, refresh
- **Acceso rápido** — Tickers recientes y watchlist

### Watchlist (Panel Izquierdo ⭐)

- **Añadir:** Analiza un ticker → pulsa ⭐ en la barra superior
- **Eliminar:** Pulsa ⭐ nuevamente sobre un ticker en watchlist
- **Información:** Cada ticker muestra su última señal (BUY/HOLD/SELL) con indicador de color
- **Score Delta:** Tracking de cambios en puntuación entre análisis
- **Navegación rápida:** Clic en un ticker para recargarlo

### Historial de Análisis

El sistema mantiene automáticamente un historial de los últimos 50 análisis con carga rápida.

### Exportar Reportes

Pulsa el ícono 📥 (Export) en la barra superior para generar un reporte PDF imprimible del análisis actual.

### Cache Inteligente

- **Fundamental:** Cache de 24 horas
- **Técnico:** Cache de 15 minutos
- El badge dorado indica datos cacheados; usa 🔄 (Refresh) para forzar análisis fresco

### Onboarding Guiado

Al acceder por primera vez, se presenta un overlay de onboarding con un tour de 5 paradas por las funcionalidades principales del terminal.

---

## 15. Interpretación de Señales

### Tabla de Referencia Rápida

| Score | Señal | Significado | Acción Sugerida |
|:---|:---|:---|:---|
| **8.0 – 10.0** | 🟢 STRONG BUY | Alta convicción. Negocio excepcional a precio atractivo. | Considerar posición significativa. |
| **6.0 – 7.9** | 🟢 BUY | Convicción moderada. Catalizadores claros. | Evaluar sizing y timing. |
| **4.0 – 5.9** | 🟡 HOLD | Buena calidad, valoración completa. | Mantener posición existente. |
| **2.0 – 3.9** | 🔴 SELL | Riesgo/retorno desfavorable. | Reducir exposición gradualmente. |
| **0.0 – 1.9** | 🔴 AVOID | Riesgo significativo. | No entrar / salir de posición. |

### Notas Importantes

> [!WARNING]
> Las señales del sistema son herramientas de apoyo a la decisión, **no recomendaciones de inversión**. Siempre realiza tu propia diligencia debida (due diligence) antes de ejecutar cualquier operación.

- Los scores se calculan como promedio ponderado de las puntuaciones Fundamental y Técnica
- La señal del Comité puede diferir de la señal individual de cada agente
- El Opportunity Score incorpora dimensiones adicionales (Alpha Signals, régimen de mercado)

---

## 16. API de Referencia

Endpoints principales del backend (puerto 8000):

| Endpoint | Método | Descripción |
|:---|:---|:---|
| `/analysis/combined/stream` | GET | Stream SSE del análisis unificado completo |
| `/analysis/fundamental/stream` | GET | Stream SSE del comité de 4 agentes |
| `/analysis/technical` | GET | Indicadores técnicos deterministas |
| `/alpha/evaluate/{ticker}` | GET | Evaluación CASE de 8 factores |
| `/ideas/scan` | POST | Escanear universo por factores |
| `/ideas/auto-scan` | POST | Scan automático del universo |
| `/ranking/compute` | POST | Calcular ranking del universo |
| `/portfolio/build` | POST | Generar asignación Core-Satellite |
| `/lab/compare` | POST | Comparar estrategias/activos |

---

## 17. Solución de Problemas

| Problema | Causa Probable | Solución |
|:---|:---|:---|
| **Pantalla en blanco** | Backend o frontend no están corriendo | Verificar que ambos servicios estén activos (puertos 8000 y 3000) |
| **Error al analizar** | API key no configurada | Verificar `GOOGLE_API_KEY` o `GEMINI_API_KEY` en `.env` |
| **Análisis lento (>60s)** | Procesamiento paralelo de 4 agentes IA | Normal para primera ejecución; posteriores usan cache |
| **Rate limit** | Límites de la API de Gemini | Esperar 60 segundos y reintentar |
| **Datos desactualizados** | Cache activo | Pulsar 🔄 Refresh para forzar análisis fresco |
| **Ideas vacías** | Watchlist vacía | Añadir tickers a la watchlist antes de escanear |
| **Panel lateral no muestra tickers** | No hay tickers en watchlist | Analizar un ticker → pulsar ⭐ para añadirlo |

### Soporte

- **Centro de Ayuda:** `Shift+?` abre el panel de ayuda integrado
- **Command Palette:** `Ctrl+K` para acceso rápido a cualquier acción

---

*Version: 2.0.0 · 365 Advisers Investment Intelligence Terminal*
