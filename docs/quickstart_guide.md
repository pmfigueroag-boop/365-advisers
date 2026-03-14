# 365 Advisers — Quick-Start Guide

> De cero a tu primer análisis en 5 minutos.

---

## 1. Requisitos

| Componente | Versión | Puerto |
|:---|:---|:---|
| Python (backend) | 3.11+ | 8000 |
| Node.js (frontend) | 18+ | 3000 |

> [!IMPORTANT]
> Necesitas un `GOOGLE_API_KEY` o `GEMINI_API_KEY` configurado en el archivo `.env` dentro de `agent-backend/`.

---

## 2. Arrancar el Sistema

**Backend:**
```bash
cd 365-advisers/agent-backend
.\venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**
```bash
cd 365-advisers/web-frontend
npm run dev
```

Abre **http://localhost:3000** en tu navegador.

---

## 3. Tu Primer Análisis (2 minutos)

1. **Escribe un ticker** — En la barra superior, ingresa un símbolo (ej: `NVDA`, `AAPL`, `MSFT`).
2. **Pulsa "Analyze"** (o `Enter`) — El sistema lanza el pipeline completo:
   - 📊 **Datos de mercado** → recopilación automática vía yfinance
   - 🧠 **Análisis Fundamental** → 4 agentes IA especializados (Calidad, Capital, Valor, Riesgo)
   - 📈 **Análisis Técnico** → Motor determinista con 15+ indicadores
   - ⚡ **Alpha Signals** → Scoring cuantitativo de 8 factores
   - 🎯 **Comité de Inversión** → Veredicto final unificado
3. **Revisa el resultado** — En ~40-50 segundos recibirás:
   - Un **veredicto** (BUY / HOLD / SELL)
   - Un **Opportunity Score** (0-10)
   - Una **tesis de inversión** narrativa

---

## 4. Navegación Rápida

Usa **`Alt + número`** para saltar entre vistas:

| Atajo | Vista | ¿Para qué? |
|:---|:---|:---|
| `Alt+1` | 🖥️ **Terminal** | Tu punto de partida. Veredicto ejecutivo y watchlist. |
| `Alt+2` | 🗺️ **Market** | Mapa del mercado: sectores, clusters y señales de riesgo. |
| `Alt+3` | 💡 **Ideas** | Escáner de oportunidades por factores (Value, Quality, Mom...). |
| `Alt+4` | 🔬 **Analysis** | Análisis profundo con 8+ sub-tabs de evidencia. |
| `Alt+5` | 💼 **Portfolio** | Construcción de portafolio Core-Satellite. |
| `Alt+6` | 🧠 **System** | Salud del sistema, drift alerts, proveedores. |
| `Alt+7` | 🧪 **Strategy Lab** | Workspace de investigación estilo Bloomberg. |
| `Alt+8` | 🏬 **Marketplace** | Estrategias institucionales pre-armadas. |
| `Alt+9` | ✨ **AI Assistant** | Chat IA conectado al Knowledge Graph. |
| `Alt+0` | 🚀 **Pilot** | Centro de comando del piloto (paper trading). |

**Otros atajos esenciales:**
- `Ctrl+K` — Abre el **Command Palette** (buscar tickers, ejecutar acciones, navegar)
- `Shift+?` — Abre el **Centro de Ayuda**

---

## 5. Construir tu Watchlist

1. Analiza un ticker (`AAPL`).
2. Pulsa el icono ⭐ en la barra superior para añadirlo a tu **Watchlist**.
3. Los tickers en tu watchlist aparecen en el **panel lateral izquierdo** con su señal más reciente.
4. Haz clic en cualquier ticker del panel para volver a cargarlo instantáneamente.

---

## 6. Descubrir Ideas de Inversión

1. Ve a **Ideas** (`Alt+3`).
2. Pulsa **Scan Universe** para escanear todos los tickers de tu watchlist.
   - O usa **Auto Scan** para que el sistema busque oportunidades automáticamente.
3. El escáner detecta 5 patrones: **Value**, **Quality**, **Momentum**, **Reversal**, **Event**.
4. Haz clic en **Analyze** junto a cualquier idea para lanzar un análisis completo.

---

## 7. Interpretar Señales

| Score | Señal | Significado |
|:---|:---|:---|
| **8.0 – 10.0** | 🟢 **STRONG BUY** | Alta convicción. Negocio excepcional a precio atractivo. |
| **6.0 – 7.9** | 🟢 **BUY** | Convicción moderada. Evaluar dimensionamiento. |
| **4.0 – 5.9** | 🟡 **HOLD** | Buena calidad, valoración completa. Mantener posición. |
| **2.0 – 3.9** | 🔴 **SELL** | Riesgo/retorno desfavorable. Considerar reducción. |
| **0.0 – 1.9** | 🔴 **AVOID** | Riesgo significativo. Problemas fundamentales o técnicos. |

---

## 8. Próximos Pasos

- 📖 Consulta el **[Manual de Usuario Completo](./user_manual.md)** para detalles de cada vista.
- 🧪 Explora el **Strategy Lab** (`Alt+7`) para backtesting y optimización.
- 🚀 Configura el **Pilot** (`Alt+0`) para validar estrategias con paper trading.

---

*Version: 2.0.0 · 365 Advisers Investment Intelligence Terminal*
