"use client";

import { useState, useEffect, useRef } from "react";
import {
    X,
    HelpCircle,
    ShieldCheck,
    LineChart,
    Zap,
    Lightbulb,
    Rocket,
    Briefcase,
    ChevronDown,
    ChevronRight,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface HelpPanelProps {
    open: boolean;
    onClose: () => void;
}

type HelpTab = "start" | "fundamental" | "technical" | "combined" | "portfolio" | "ideas" | "tips";

interface AccordionItemProps {
    title: string;
    children: React.ReactNode;
    defaultOpen?: boolean;
}

// ─── Accordion ────────────────────────────────────────────────────────────────

function AccordionItem({ title, children, defaultOpen = false }: AccordionItemProps) {
    const [open, setOpen] = useState(defaultOpen);
    return (
        <div className="border border-[#30363d] rounded-lg overflow-hidden">
            <button
                onClick={() => setOpen(!open)}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[#161b22] transition-colors"
            >
                <span className="text-[11px] font-black uppercase tracking-widest text-gray-300">
                    {title}
                </span>
                {open ? (
                    <ChevronDown size={13} className="text-[#d4af37] flex-shrink-0" />
                ) : (
                    <ChevronRight size={13} className="text-gray-600 flex-shrink-0" />
                )}
            </button>
            {open && (
                <div className="px-4 pb-4 pt-1 text-[11px] text-gray-400 leading-relaxed space-y-2 border-t border-[#21262d]">
                    {children}
                </div>
            )}
        </div>
    );
}

// ─── Signal Badge ─────────────────────────────────────────────────────────────

function Signal({ label, color }: { label: string; color: string }) {
    return (
        <span className={`inline-block px-2 py-0.5 rounded text-[9px] font-black uppercase border ${color}`}>
            {label}
        </span>
    );
}

// ─── Tab Content Sections ─────────────────────────────────────────────────────

function StartSection() {
    return (
        <div className="space-y-3">
            <AccordionItem title="Primeros pasos — ¿Qué es 365 Advisers?" defaultOpen>
                <p>365 Advisers es un <strong className="text-white">motor de decisión de inversión institucional</strong>. Simula un comité de inversión con 4 analistas de IA especializados + un CIO Synthesizer que produce veredictos accionables.</p>
                <div className="mt-2 bg-[#0d1117] rounded p-3 border border-[#21262d]">
                    <p className="text-[9px] font-black uppercase tracking-widest text-[#d4af37] mb-2">Flujo básico en 4 pasos:</p>
                    <ol className="space-y-2 list-decimal list-inside text-gray-400">
                        <li><strong className="text-white">Ingresa un ticker</strong> en la barra superior (ej. <code className="text-[#d4af37] bg-[#161b22] px-1 rounded">NVDA</code>) y haz clic en <strong className="text-white">Analyze</strong> o presiona <kbd className="bg-[#21262d] border border-[#30363d] px-1 rounded text-[8px]">Enter</kbd></li>
                        <li><strong className="text-white">Espera ~40-60 segundos</strong> la primera vez — el sistema ejecuta 4 motores en paralelo (Fundamental IA, Técnico, Decision Engine, Portfolio)</li>
                        <li><strong className="text-white">Lee el veredicto</strong> en la pestaña Combined — incluye señal (BUY/HOLD/SELL), confianza, tesis y riesgos</li>
                        <li><strong className="text-white">Guarda con ★</strong> para tracking continuo — las re-consultas son instantáneas gracias al caché</li>
                    </ol>
                </div>
            </AccordionItem>

            <AccordionItem title="Mapa de navegación" defaultOpen>
                <p className="mb-2">La interfaz se organiza en <strong className="text-white">pestañas principales</strong> (arriba) y <strong className="text-white">sidebar</strong> (izquierda):</p>
                <div className="space-y-1.5">
                    {[
                        { tab: "Fundamental", desc: "Análisis IA con 4 analistas — memos individuales, ratios, Research Memo", icon: "🏛" },
                        { tab: "Technical", desc: "15+ indicadores técnicos — tendencia, momentum, volatilidad, volumen, estructura", icon: "📈" },
                        { tab: "Combined", desc: "Veredicto unificado del CIO — tesis, position sizing, score institucional", icon: "⚡" },
                        { tab: "Portfolio", desc: "Construcción de portafolio Core-Satellite con Volatility Parity", icon: "💼" },
                    ].map(t => (
                        <div key={t.tab} className="flex items-start gap-2 bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                            <span>{t.icon}</span>
                            <div>
                                <span className="text-white font-black text-[10px]">{t.tab}</span>
                                <p className="text-gray-500 text-[9px]">{t.desc}</p>
                            </div>
                        </div>
                    ))}
                </div>
                <p className="mt-2 text-gray-600 text-[10px]">En el sidebar: <strong className="text-white">Watch</strong> = watchlist, <strong className="text-white">History</strong> = últimos 50 análisis, <strong className="text-white">Ideas</strong> = oportunidades detectadas por el Idea Engine.</p>
            </AccordionItem>

            <AccordionItem title="Interpretación de señales">
                <p className="mb-2">Cada análisis produce un <strong className="text-white">score 0-10</strong> y una <strong className="text-white">señal de inversión</strong>. Así se interpretan:</p>
                <div className="space-y-2">
                    {[
                        { range: "8.0 – 10", label: "STRONG BUY", color: "bg-green-500/10 border-green-500/30 text-green-400", desc: "Convicción altísima — negocio excepcional a precio atractivo. Considerar posición significativa." },
                        { range: "6.0 – 7.9", label: "BUY", color: "bg-green-500/10 border-green-500/20 text-green-400", desc: "Oportunidad interesante con catalizadores claros. Evaluar tamaño de posición con Position Sizing." },
                        { range: "4.0 – 5.9", label: "HOLD", color: "bg-[#d4af37]/10 border-[#d4af37]/20 text-[#d4af37]", desc: "Calidad pero valuación plena — mantener posición existente, no agregar. Monitorear catalizadores." },
                        { range: "2.0 – 3.9", label: "SELL", color: "bg-red-500/10 border-red-500/20 text-red-400", desc: "Riesgo/recompensa desfavorable. Considerar reducción de exposición y niveles de stop-loss." },
                        { range: "0 – 1.9", label: "AVOID", color: "bg-red-500/20 border-red-500/30 text-red-400", desc: "Riesgos significativos — deterioro fundamental o técnico grave. No establecer posición larga." },
                    ].map(s => (
                        <div key={s.label} className="flex items-start gap-2">
                            <span className="text-gray-600 w-16 flex-shrink-0 font-mono text-[9px]">{s.range}</span>
                            <Signal label={s.label} color={s.color} />
                            <span className="text-gray-500 text-[10px]">{s.desc}</span>
                        </div>
                    ))}
                </div>
                <p className="mt-3 text-gray-700 text-[9px]">⚠️ No es una recomendación de inversión. Realiza siempre tu propio análisis y due diligence.</p>
            </AccordionItem>

            <AccordionItem title="Watchlist — Seguimiento continuo">
                <p className="mb-1.5">La watchlist es tu <strong className="text-white">universo de cobertura personal</strong>:</p>
                <ul className="space-y-1.5">
                    <li><strong className="text-white">Agregar:</strong> Clic en ★ en el header después de analizar un ticker</li>
                    <li><strong className="text-white">Re-analizar:</strong> Clic en cualquier ticker del sidebar → lo carga instantáneamente</li>
                    <li><strong className="text-white">Vista Heatmap:</strong> Cambia a la vista compacta con los iconos 📋/🟩 — colores verde/rojo indican mejora/deterioro del score vs. el análisis anterior</li>
                    <li><strong className="text-white">Delta de score:</strong> Si ves "+1.2" o "-0.8" junto al ticker, indica cuánto cambió el score entre el análisis previo y el actual</li>
                    <li><strong className="text-white">Escanear Ideas:</strong> Usa la pestaña <strong className="text-[#d4af37]">Ideas</strong> del sidebar para escanear tu watchlist completa buscando oportunidades automáticas</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Historial de análisis">
                <ul className="space-y-1.5">
                    <li><strong className="text-white">HISTORY</strong> en el sidebar — últimos 50 análisis, persistidos en localStorage</li>
                    <li>Cada entrada muestra: ticker, señal, fecha y resumen de agentes</li>
                    <li>Clic en una entrada → recarga ese análisis instantáneamente</li>
                    <li>El historial alimenta el tab <strong className="text-white">Portfolio</strong> — necesitas ≥2 análisis para construir portafolio</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Preguntas frecuentes">
                <div className="space-y-3">
                    <div>
                        <p className="text-white text-[10px] font-bold">¿Por qué el primer análisis tarda tanto?</p>
                        <p className="text-gray-500 text-[10px] mt-0.5">El sistema ejecuta 4 agentes IA en paralelo + obtiene datos de Yahoo Finance y TradingView. La primera vez toma ~40-60 s. Las siguientes veces es instantáneo gracias al caché (24h fundamental, 15min técnico).</p>
                    </div>
                    <div>
                        <p className="text-white text-[10px] font-bold">¿Qué significa el badge "CACHED"?</p>
                        <p className="text-gray-500 text-[10px] mt-0.5">Indica que los resultados provienen de la base de datos, no de una llamada nueva a la IA. Usa el botón ↻ para forzar datos frescos.</p>
                    </div>
                    <div>
                        <p className="text-white text-[10px] font-bold">¿Cómo sé si debo comprar o vender?</p>
                        <p className="text-gray-500 text-[10px] mt-0.5">Ve al tab <strong className="text-white">Combined</strong> y lee el veredicto del CIO. Incluye señal, confidence %, tesis de inversión, catalizadores y riesgos. Usa Position Sizing para el tamaño sugerido de la posición.</p>
                    </div>
                    <div>
                        <p className="text-white text-[10px] font-bold">¿Puedo comparar varias acciones?</p>
                        <p className="text-gray-500 text-[10px] mt-0.5">Sí. Clic en el icono ⇋ (Compare) en el header. Ingresa 2-3 tickers separados por coma y compara veredictos lado a lado.</p>
                    </div>
                    <div>
                        <p className="text-white text-[10px] font-bold">¿Los tooltips del glosario están en español?</p>
                        <p className="text-gray-500 text-[10px] mt-0.5">Sí. Pasa el cursor sobre cualquier término subrayado (RSI, P/E, ROIC, etc.) para ver su definición y cómo interpretarlo.</p>
                    </div>
                </div>
            </AccordionItem>
        </div>
    );
}

function FundamentalSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Motor LangGraph con 4 agentes especializados + Committee Supervisor (Gemini Pro). Tarda ~40-50 s. Caché 24 h.
            </p>

            <AccordionItem title="Los 4 analistas" defaultOpen>
                {[
                    {
                        name: "Quality & Moat",
                        avatars: "Munger · Phil Fisher",
                        icon: "🏛",
                        desc: "Evalúa la calidad del negocio: ROIC, márgenes, ventajas competitivas (moat), capacidad de fijación de precios y crecimiento sostenible.",
                    },
                    {
                        name: "Capital Allocation",
                        avatars: "Icahn · Activista",
                        icon: "💼",
                        desc: "Analiza FCF, buybacks, deuda, dividendos y la eficiencia del management para generar valor para el accionista.",
                    },
                    {
                        name: "Value & Margin of Safety",
                        avatars: "Graham · Buffett",
                        description: "Verifica si hay margen de seguridad: P/E, P/B, EV/EBITDA, FCF yield. Señal AVOID si la valuación descuenta perfectamente el crecimiento futuro.",
                        icon: "⚖️",
                        desc: "Verifica margen de seguridad: P/E, P/B, FCF yield, EV/EBITDA. Señal AVOID si la valuación descuenta perfectamente el crecimiento futuro.",
                    },
                    {
                        name: "Risk & Macro Stress",
                        avatars: "Marks · Dalio",
                        icon: "🌐",
                        desc: "Identifica riesgos macro, ciclo económico, riesgo regulatorio, geopolítico y concentración. Señal HOLD si los riesgos sistémicos son materiales.",
                    },
                ].map((a) => (
                    <div key={a.name} className="bg-[#0d1117] rounded p-3 space-y-1 border border-[#21262d]">
                        <div className="flex items-center gap-2">
                            <span>{a.icon}</span>
                            <span className="text-white font-black text-[11px]">{a.name}</span>
                        </div>
                        <p className="text-gray-600 text-[9px] italic">{a.avatars}</p>
                        <p className="text-gray-400 text-[10px]">{a.desc}</p>
                    </div>
                ))}
            </AccordionItem>

            <AccordionItem title="Leer un memo de analista">
                <p className="mb-1.5">Cada agente produce un <strong className="text-white">memo individual</strong> con 3 elementos clave:</p>
                <ul className="space-y-1.5">
                    <li><strong className="text-white">Señal</strong> — BUY / AVOID / HOLD del agente individual. Si 3 de 4 agentes dicen BUY, el comité generalmente emite BUY.</li>
                    <li><strong className="text-white">Convicción %</strong> — certeza del agente en su tesis. &gt;85% = alta convicción, 60-85% = moderada, &lt;60% = baja.</li>
                    <li><strong className="text-white">Texto del memo</strong> — razonamiento en lenguaje natural con datos reales de mercado. Busca la tesis central, catalizadores mencionados y riesgos identificados.</li>
                </ul>
                <p className="mt-2 text-gray-600 text-[10px]">El Committee Supervisor pondera los 4 memos y emite el veredicto final. Su peso es proporcional a la convicción de cada agente.</p>
            </AccordionItem>

            <AccordionItem title="Research Memo (1-pager)">
                <p>Scroll hacia abajo en el tab Fundamental para ver el <strong className="text-white">Research Memo</strong>. Es un resumen ejecutivo que incluye:</p>
                <ul className="mt-1.5 space-y-1">
                    <li><strong className="text-white">Tesis de inversión</strong> — razón principal para comprar/mantener/vender</li>
                    <li><strong className="text-white">Métricas clave</strong> — ROIC, P/E, FCF yield y otras métricas resaltadas</li>
                    <li><strong className="text-white">Catalizadores</strong> — eventos futuros que podrían mover el precio</li>
                    <li><strong className="text-white">Riesgos</strong> — factores que podrían invalidar la tesis</li>
                </ul>
                <p className="mt-2 text-gray-600 text-[10px]">Usa el botón PDF (↓) en el header para exportar el memo como documento institucional.</p>
            </AccordionItem>
        </div>
    );
}

function TechnicalSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Motor determinístico sin LLM. Calcula 15+ indicadores en ~2-3 segundos. Caché 15 min.
            </p>

            <AccordionItem title="Los 5 módulos" defaultOpen>
                {[
                    {
                        name: "Trend", icon: "📈",
                        indicators: "SMA50, SMA200, MACD, Golden Cross / Death Cross",
                        desc: "Determina la dirección de precio a mediano-largo plazo. Golden Cross (SMA50 cruza arriba SMA200) es señal alcista fuerte.",
                    },
                    {
                        name: "Momentum", icon: "⚡",
                        indicators: "RSI(14), Stochastic %K/%D",
                        desc: "Velocidad del movimiento de precio. RSI < 30 = sobrevendido (rebote probable), RSI > 70 = sobrecomprado (corrección probable).",
                    },
                    {
                        name: "Volatility", icon: "〰️",
                        indicators: "Bollinger Bands, ATR, BB Width",
                        desc: "Amplitud del rango de precio. BB estrechos = consolidación (breakout inminente). BB anchos = alta volatilidad.",
                    },
                    {
                        name: "Volume", icon: "📊",
                        indicators: "OBV, Vol/Avg20",
                        desc: "Confirma si el movimiento de precio tiene respaldo de volumen. OBV rising + precio subiendo = señal de acumulación institucional.",
                    },
                    {
                        name: "Structure", icon: "🏗",
                        indicators: "Soporte, Resistencia, Breakout probability",
                        desc: "Niveles clave de precio. El sistema identifica soporte/resistencia automáticamente y calcula la probabilidad de breakout.",
                    },
                ].map((m) => (
                    <div key={m.name} className="bg-[#0d1117] rounded p-3 space-y-1 border border-[#21262d]">
                        <div className="flex items-center gap-2">
                            <span>{m.icon}</span>
                            <span className="text-white font-black text-[11px]">{m.name}</span>
                        </div>
                        <p className="text-[#d4af37] text-[9px] font-mono">{m.indicators}</p>
                        <p className="text-gray-400 text-[10px]">{m.desc}</p>
                    </div>
                ))}
            </AccordionItem>

            <AccordionItem title="Score técnico global">
                <p>El score técnico (0-10) es una media ponderada de los 5 módulos. Las barras de <strong className="text-white">Module Scores</strong> muestran cada subscore individualmente para identificar fortalezas y debilidades.</p>
                <div className="mt-2 grid grid-cols-2 gap-1 text-[9px]">
                    {[["STRONG_BUY", "≥ 8.0"], ["BUY", "6.0–7.9"], ["NEUTRAL", "4.0–5.9"], ["SELL", "2.0–3.9"]].map(([s, r]) => (
                        <div key={s} className="flex justify-between bg-[#21262d] rounded px-2 py-1">
                            <span className="font-mono text-gray-400">{s}</span>
                            <span className="text-gray-600">{r}</span>
                        </div>
                    ))}
                </div>
            </AccordionItem>
        </div>
    );
}

function CombinedSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Decision Engine: orquesta Fundamental + Technical vía SSE, luego el CIO Synthesizer genera el veredicto institucional con Position Sizing.
            </p>

            <AccordionItem title="Status Timeline" defaultOpen>
                <div className="flex items-center gap-2 py-2 px-3 bg-[#0d1117] rounded border border-[#21262d] font-mono text-[9px]">
                    <span className="text-green-400">● Data</span>
                    <span className="text-gray-700">──</span>
                    <span className="text-[#d4af37]">● Analysts</span>
                    <span className="text-gray-700">──</span>
                    <span className="text-blue-400">● Technical</span>
                    <span className="text-gray-700">──</span>
                    <span className="text-purple-400">● CIO</span>
                    <span className="text-gray-700">──</span>
                    <span className="text-gray-400">● Done</span>
                </div>
                <ul className="mt-2 space-y-1">
                    <li><strong className="text-green-400">Data</strong> — ratios financieros cargados (Yahoo Finance)</li>
                    <li><strong className="text-[#d4af37]">Analysts</strong> — 4 agentes de IA procesando en paralelo</li>
                    <li><strong className="text-blue-400">Technical</strong> — indicadores calculados</li>
                    <li><strong className="text-purple-400">CIO</strong> — el CIO Synthesizer genera el veredicto unificado, tesis, catalizadores y riesgos</li>
                    <li><strong className="text-white">Done</strong> — stream completo; badge CACHED si viene de DB</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Decision Engine (CIO Synthesizer)">
                <p>El veredicto ya no es una media simple. El <strong className="text-white">CIO Synthesizer</strong> (Gemini Pro) evalúa ambos motores y produce:</p>
                <ul className="mt-1.5 space-y-1">
                    <li><strong className="text-white">Investment Position</strong> — BUY / HOLD / SELL / AVOID / Strong Opportunity. Es el veredicto final del sistema.</li>
                    <li><strong className="text-white">Confidence %</strong> — nivel de certeza institucional (0–100%). &gt;80% = alta convicción, 50-80% = moderada.</li>
                    <li><strong className="text-white">CIO Memo</strong> — tesis de inversión completa con visión de valuación, contexto técnico, catalizadores y riesgos clave.</li>
                </ul>
                <div className="mt-2 px-3 py-2 bg-[#0d1117] rounded border border-[#21262d]">
                    <p className="text-[9px] font-black uppercase tracking-widest text-[#d4af37] mb-1">Cómo leer el veredicto:</p>
                    <ol className="space-y-1 list-decimal list-inside text-gray-400 text-[10px]">
                        <li>Mira la <strong className="text-white">señal</strong> (BUY/HOLD/SELL) — es tu acción sugerida</li>
                        <li>Revisa el <strong className="text-white">confidence %</strong> — si es bajo (&lt;60%), lee los riesgos con atención</li>
                        <li>Lee los <strong className="text-white">catalizadores</strong> — son los eventos que validan la tesis</li>
                        <li>Evalúa los <strong className="text-white">riesgos</strong> — decide si son aceptables para tu perfil</li>
                    </ol>
                </div>
            </AccordionItem>

            <AccordionItem title="Position Sizing — ¿Cuánto invertir?">
                <p>Debajo del veredicto, el bloque <strong className="text-white">Portfolio Allocation Suggestion</strong> te dice qué porcentaje de tu portafolio asignar:</p>
                <ul className="mt-1.5 space-y-1">
                    <li><strong className="text-white">Opportunity Score</strong> — score 0–10 del potencial. &gt;7 = oportunidad fuerte.</li>
                    <li><strong className="text-white">Conviction Level</strong> — Low / Medium / High / Very High — resume la fortaleza de la señal.</li>
                    <li><strong className="text-white">Base Size %</strong> — tamaño base antes de ajuste por riesgo (2-8%).</li>
                    <li><strong className="text-white">Risk Adjustment</strong> — multiplicador por volatilidad (ATR). Alta volatilidad reduce el tamaño sugerido.</li>
                    <li><strong className="text-white">Suggested Allocation %</strong> — posición final sugerida (max 10%). Este es el número clave a usar.</li>
                </ul>
                <p className="mt-2 text-gray-600 text-[10px]">💡 Ejemplo: Si Allocation = 5%, significa que de un portafolio de $100K, la posición sugerida es $5K en este activo.</p>
            </AccordionItem>

            <AccordionItem title="Sub-tabs del Combined">
                <ul className="space-y-2">
                    <li><strong className="text-white">CIO Memo</strong> — tesis de inversión, valuación, contexto técnico, catalizadores y riesgos clave</li>
                    <li><strong className="text-white">Analysts (4/4)</strong> — los 4 memos completos del motor fundamental</li>
                    <li><strong className="text-white">Tech [score]</strong> — IndicatorGrid completo del motor técnico</li>
                    <li><strong className="text-white">History</strong> — gráfico de evolución de scores a lo largo del tiempo</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Exportar CSV">
                <p>En la barra superior del Combined tab, el botón <strong className="text-white">CSV</strong> descarga un archivo con todos los ratios fundamentales e indicadores técnicos del análisis activo.</p>
            </AccordionItem>

            <AccordionItem title="Botón REFRESH">
                <p>El botón <strong className="text-white">REFRESH</strong> en la esquina superior derecha del Combined tab invalida ambos cachés y fuerza un recálculo completo — útil cuando el precio ha movido significativamente o quieres datos frescos del mercado.</p>
            </AccordionItem>
        </div>
    );
}

function PortfolioSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Motor de portafolio institucional: Core-Satellite allocation con Volatility Parity sizing. Persistencia en SQLite.
            </p>

            <AccordionItem title="Portfolio Builder" defaultOpen>
                <p>El tab <strong className="text-white">Portfolio</strong> construye una cartera óptima basada en los tickers de tu historial de análisis:</p>
                <ul className="mt-1.5 space-y-1">
                    <li><strong className="text-white">Core-Satellite</strong> — los activos con mayor conviction son "Core" (mayor peso), el resto son "Satellite"</li>
                    <li><strong className="text-white">Volatility Parity</strong> — el sizing se ajusta inversamente a la volatilidad (ATR) de cada posición</li>
                    <li><strong className="text-white">Estrategia y Riesgo</strong> — selecciona la estrategia (Growth, Value, Balanced) y nivel de riesgo (Conservative, Moderate, Aggressive)</li>
                </ul>
                <p className="mt-2 text-gray-600 text-[10px]">Necesitas al menos 2 análisis completados en el historial para generar un portafolio.</p>
            </AccordionItem>

            <AccordionItem title="What-If Simulator">
                <p>El sandbox <strong className="text-white">What-If</strong> permite probar escenarios antes de comitear capital:</p>
                <ul className="mt-1.5 space-y-1">
                    <li><strong className="text-white">Inyectar ticker</strong> — agrega un activo del historial al portafolio simulado y ve cómo cambian los pesos</li>
                    <li><strong className="text-white">Remover ticker</strong> — elimina un activo y recalcula la distribución</li>
                    <li><strong className="text-white">Comparar</strong> — ve side-by-side el portafolio base vs. el escenario simulado</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Guardar portafolios">
                <p>Clic en <strong className="text-white">Save Portfolio</strong> para persistir la configuración actual en la base de datos del servidor (SQLite). Los portafolios guardados aparecen en la lista inferior con nombre, estrategia y fecha.</p>
            </AccordionItem>
        </div>
    );
}

function TipsSection() {
    return (
        <div className="space-y-3">
            <AccordionItem title="Atajos de teclado" defaultOpen>
                <div className="space-y-1.5">
                    {[
                        ["Enter", "Ejecutar análisis (desde el campo de búsqueda)"],
                        ["Shift + ?", "Abrir / cerrar este panel de ayuda"],
                        ["Esc", "Cerrar este panel / overlays"],
                    ].map(([key, desc]) => (
                        <div key={key} className="flex items-center gap-3">
                            <kbd className="bg-[#21262d] border border-[#30363d] px-2 py-0.5 rounded text-[9px] font-mono text-gray-300 flex-shrink-0">
                                {key}
                            </kbd>
                            <span className="text-gray-400 text-[10px]">{desc}</span>
                        </div>
                    ))}
                </div>
            </AccordionItem>

            <AccordionItem title="Force Refresh (datos frescos)">
                <p>Si quieres saltarte el caché para un ticker específico:</p>
                <ul className="mt-2 space-y-1">
                    <li>Combined tab → botón <strong className="text-white">REFRESH</strong> — invalida fundamental + técnico</li>
                    <li>Header → botón <strong className="text-white">↻</strong> (junto a CACHED badge) — fuerza refresh del análisis completo</li>
                    <li>API directa: agrega <code className="text-[#d4af37] bg-[#161b22] px-1 rounded">?force=true</code> al endpoint</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Comparar tickers">
                <p>Clic en el icono <strong className="text-white">⟳</strong> (Compare) en el header para activar el modo comparación. Introduce hasta 3 tickers separados por coma (ej. <code className="text-[#d4af37] bg-[#161b22] px-1 rounded">AAPL, MSFT, NVDA</code>) y compara el veredicto de los agentes en paralelo.</p>
            </AccordionItem>

            <AccordionItem title="Exportar análisis">
                <ul className="space-y-1.5">
                    <li><strong className="text-white">PDF</strong> — botón <strong className="text-white">↓</strong> en el header — exporta el Research Memo institucional completo</li>
                    <li><strong className="text-white">CSV</strong> — botón <strong className="text-white">CSV</strong> en el Combined tab — descarga ratios fundamentales + indicadores técnicos en formato tabular</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Onboarding">
                <p>La primera vez que entras, un overlay de 3 pasos te guía por el flujo básico. Si lo saltas, puedes repetirlo borrando <code className="text-[#d4af37] bg-[#161b22] px-1 rounded">365_onboarding_done</code> de localStorage.</p>
            </AccordionItem>

            <AccordionItem title="Rendimiento y caché">
                <div className="space-y-1">
                    <div className="flex justify-between text-[10px] bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                        <span className="text-gray-400">Fundamental</span>
                        <span className="text-[#d4af37] font-mono">Caché 24 h</span>
                    </div>
                    <div className="flex justify-between text-[10px] bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                        <span className="text-gray-400">Technical</span>
                        <span className="text-[#d4af37] font-mono">Caché 15 min</span>
                    </div>
                    <div className="flex justify-between text-[10px] bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                        <span className="text-gray-400">Persistencia</span>
                        <span className="text-[#d4af37] font-mono">SQLite (server)</span>
                    </div>
                </div>
                <p className="mt-2 text-gray-600 text-[9px]">El badge <strong className="text-white">CACHED</strong> en el Combined timeline indica que la respuesta vino de la base de datos, no de una nueva llamada a la IA.</p>
            </AccordionItem>
        </div>
    );
}

function IdeasHelpSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Motor de generación de ideas: escanea tu watchlist para detectar oportunidades automáticamente usando 5 detectores modulares.
            </p>

            <AccordionItem title="¿Cómo usar el Ideas Engine?" defaultOpen>
                <ol className="space-y-2 list-decimal list-inside text-gray-400">
                    <li><strong className="text-white">Agrega tickers a tu Watchlist</strong> — analiza varios tickers y guárdalos con ★</li>
                    <li><strong className="text-white">Ve a la pestaña Ideas</strong> en el sidebar (icono 💡)</li>
                    <li><strong className="text-white">Clic en ↻</strong> (refresh) — el sistema escanea todos tus tickers en paralelo</li>
                    <li><strong className="text-white">Revisa los resultados</strong> — cada idea muestra tipo, confianza y señales detectadas</li>
                    <li><strong className="text-white">Clic en ⚡</strong> para ejecutar un análisis completo del ticker seleccionado</li>
                </ol>
                <p className="mt-2 text-gray-600 text-[10px]">El escaneo tarda ~5-15 s dependiendo del número de tickers y la conexión.</p>
            </AccordionItem>

            <AccordionItem title="Los 5 detectores" defaultOpen>
                {[
                    {
                        name: "Value", icon: "💎", color: "text-emerald-400",
                        desc: "Identifica activos subvaluados: FCF yield alto, P/E bajo, EV/EBITDA bajo, P/B bajo.",
                        interpretation: "Señal fuerte cuando ≥3 de 4 métricas están por debajo de los umbrales. Indica descuento fundamental vs. valor intrínseco.",
                    },
                    {
                        name: "Quality", icon: "⚡", color: "text-blue-400",
                        desc: "Detecta negocios de alta calidad: ROIC alto, márgenes estables, crecimiento rentable, baja deuda.",
                        interpretation: "Señal fuerte cuando el ROIC >15%, márgenes expandiéndose y D/E <0.5. Indica franchise value.",
                    },
                    {
                        name: "Momentum", icon: "📈", color: "text-orange-400",
                        desc: "Identifica tendencias fuertes: Golden Cross, RSI 50-70, MACD positivo, volumen alto, precio sobre EMA20.",
                        interpretation: "Señal fuerte = tendencia alcista confirmada por múltiples indicadores. Ideal para entradas con momentum.",
                    },
                    {
                        name: "Reversal", icon: "📉", color: "text-red-400",
                        desc: "Detecta posibles reversiones: RSI sobrevendido, Stochastic bajo, precio cerca de Bollinger inferior, capitulación de volumen.",
                        interpretation: "Requiere mínimo 2 señales confirmando. Mayor riesgo — potencial de rebote tras caída excesiva.",
                    },
                    {
                        name: "Event", icon: "📊", color: "text-purple-400",
                        desc: "Oportunidades por catalizadores: cambio significativo en score, sorpresa de earnings, squeeze de volatilidad, beta alto.",
                        interpretation: "Captura eventos que preceden movimientos significativos de precio. Complementa otros detectores.",
                    },
                ].map(d => (
                    <div key={d.name} className="bg-[#0d1117] rounded p-3 space-y-1 border border-[#21262d]">
                        <div className="flex items-center gap-2">
                            <span>{d.icon}</span>
                            <span className={`font-black text-[11px] ${d.color}`}>{d.name}</span>
                        </div>
                        <p className="text-gray-400 text-[10px]">{d.desc}</p>
                        <p className="text-gray-600 text-[9px] italic">Interpretación: {d.interpretation}</p>
                    </div>
                ))}
            </AccordionItem>

            <AccordionItem title="Interpretar resultados">
                <div className="space-y-2">
                    <div className="bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                        <p className="text-white text-[10px] font-bold">Confidence (Confianza)</p>
                        <div className="mt-1 space-y-0.5 text-[9px]">
                            <div className="flex gap-2"><Signal label="HIGH" color="bg-green-500/15 border-green-500/30 text-green-400" /><span className="text-gray-500">≥60% de señales activadas — alta probabilidad</span></div>
                            <div className="flex gap-2"><Signal label="MEDIUM" color="bg-yellow-500/15 border-yellow-500/30 text-yellow-400" /><span className="text-gray-500">40-60% — señal moderada, validar con análisis completo</span></div>
                            <div className="flex gap-2"><Signal label="LOW" color="bg-gray-500/15 border-gray-500/30 text-gray-400" /><span className="text-gray-500">&lt;40% — señal débil, tratar como exploratoria</span></div>
                        </div>
                    </div>
                    <div className="bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                        <p className="text-white text-[10px] font-bold">Signal Strength (Barra de fuerza)</p>
                        <p className="text-gray-500 text-[9px] mt-0.5">La barra visual muestra qué proporción de señales del detector se activaron. 100% = todas las señales posibles confirman la oportunidad.</p>
                    </div>
                    <div className="bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                        <p className="text-white text-[10px] font-bold">Priority (Ranking)</p>
                        <p className="text-gray-500 text-[9px] mt-0.5">Las ideas se ordenan por prioridad #1 = mejor oportunidad. El ranking considera: fuerza de señal, confianza, y bonus por múltiples detectores activados en el mismo ticker.</p>
                    </div>
                </div>
            </AccordionItem>

            <AccordionItem title="Acciones sobre una idea">
                <ul className="space-y-1.5">
                    <li><strong className="text-[#d4af37]">⚡ Analizar</strong> — ejecuta el pipeline completo (Fundamental + Technical + CIO) para ese ticker. Los resultados aparecerán en las pestañas principales.</li>
                    <li><strong className="text-red-400">✕ Descartar</strong> — elimina la idea de la lista activa (aparece al hover). No afecta datos.</li>
                    <li><strong className="text-white">▼ Expandir</strong> — muestra las señales individuales detectadas con su fuerza (strong/moderate/weak) y descripción.</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Filtros por tipo">
                <p>Los chips de filtro en la parte superior permiten ver solo ideas de un tipo específico. Esto es útil cuando buscas oportunidades de un estilo particular:</p>
                <ul className="mt-1.5 space-y-1 text-[10px]">
                    <li><span className="text-emerald-400 font-bold">Value</span> — para inversores value buscando descuentos fundamentales</li>
                    <li><span className="text-blue-400 font-bold">Quality</span> — para cazadores de calidad (franchises, moats)</li>
                    <li><span className="text-orange-400 font-bold">Momentum</span> — para seguir tendencias alcistas confirmadas</li>
                    <li><span className="text-red-400 font-bold">Reversal</span> — para especular en rebotes tras caídas (mayor riesgo)</li>
                    <li><span className="text-purple-400 font-bold">Event</span> — para capturar catalizadores y cambios repentinos</li>
                </ul>
            </AccordionItem>
        </div>
    );
}

// ─── Tab Config ───────────────────────────────────────────────────────────────

const TABS: { id: HelpTab; label: string; Icon: React.ElementType }[] = [
    { id: "start", label: "Inicio", Icon: Rocket },
    { id: "fundamental", label: "Fundamental", Icon: ShieldCheck },
    { id: "technical", label: "Técnico", Icon: LineChart },
    { id: "combined", label: "Combined", Icon: Zap },
    { id: "portfolio", label: "Portfolio", Icon: Briefcase },
    { id: "ideas", label: "Ideas", Icon: Lightbulb },
    { id: "tips", label: "Tips Pro", Icon: HelpCircle },
];

// ─── Main HelpPanel ───────────────────────────────────────────────────────────

export default function HelpPanel({ open, onClose }: HelpPanelProps) {
    const [activeTab, setActiveTab] = useState<HelpTab>("start");
    const panelRef = useRef<HTMLDivElement>(null);

    // Close on Escape
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [onClose]);

    // Trap focus when open
    useEffect(() => {
        if (open) panelRef.current?.focus();
    }, [open]);

    if (!open) return null;

    return (
        <>
            {/* Overlay */}
            <div
                className="fixed inset-0 bg-black/50 z-40 backdrop-blur-sm"
                onClick={onClose}
                aria-hidden="true"
            />

            {/* Panel */}
            <div
                ref={panelRef}
                tabIndex={-1}
                role="dialog"
                aria-label="Centro de ayuda"
                className="fixed top-0 right-0 h-full w-full sm:w-96 z-50 flex flex-col bg-[#0d1117] border-l border-[#30363d] shadow-2xl outline-none"
                style={{ animation: "slideInRight 0.25s cubic-bezier(0.4,0,0.2,1) both" }}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-[#21262d] flex-shrink-0">
                    <div className="flex items-center gap-2">
                        <HelpCircle size={15} className="text-[#d4af37]" />
                        <span className="text-[11px] font-black uppercase tracking-widest text-white">
                            Centro de Ayuda
                        </span>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1 rounded hover:bg-[#21262d] transition-colors text-gray-500 hover:text-white"
                        aria-label="Cerrar"
                    >
                        <X size={15} />
                    </button>
                </div>

                {/* Tab bar */}
                <div className="flex border-b border-[#21262d] flex-shrink-0 overflow-x-auto">
                    {TABS.map(({ id, label, Icon }) => (
                        <button
                            key={id}
                            onClick={() => setActiveTab(id)}
                            className={`flex items-center gap-1.5 px-3 py-2.5 text-[9px] font-black uppercase tracking-widest whitespace-nowrap transition-colors flex-shrink-0 border-b-2 ${activeTab === id
                                ? "border-[#d4af37] text-[#d4af37]"
                                : "border-transparent text-gray-600 hover:text-gray-300"
                                }`}
                        >
                            <Icon size={10} />
                            {label}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                    {activeTab === "start" && <StartSection />}
                    {activeTab === "fundamental" && <FundamentalSection />}
                    {activeTab === "technical" && <TechnicalSection />}
                    {activeTab === "combined" && <CombinedSection />}
                    {activeTab === "portfolio" && <PortfolioSection />}
                    {activeTab === "ideas" && <IdeasHelpSection />}
                    {activeTab === "tips" && <TipsSection />}
                </div>

                {/* Footer */}
                <div className="px-5 py-3 border-t border-[#21262d] flex-shrink-0 flex items-center justify-between">
                    <span className="text-[9px] text-gray-700 font-mono">365 Advisers v3.0</span>
                    <span className="text-[9px] text-gray-700">
                        Presiona <kbd className="bg-[#21262d] border border-[#30363d] px-1 rounded text-[8px]">Esc</kbd> para cerrar
                    </span>
                </div>
            </div>

            <style jsx global>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
      `}</style>
        </>
    );
}
