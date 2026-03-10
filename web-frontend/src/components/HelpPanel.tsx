"use client";

import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
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
    Globe,
    Activity,
    FlaskConical,
    Store,
    Bot,
    Radio,
    Settings,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface HelpPanelProps {
    open: boolean;
    onClose: () => void;
    /** When true, renders as a full-page layout instead of an overlay sidebar */
    standalone?: boolean;
}

type HelpTab = "start" | "fundamental" | "technical" | "combined" | "signals" | "portfolio" | "ideas" | "market" | "system" | "pilot" | "strategylab" | "marketplace" | "assistant" | "tips";

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

            <AccordionItem title="Mapa de navegación — 10 vistas" defaultOpen>
                <p className="mb-2">La interfaz se organiza en <strong className="text-white">10 vistas principales</strong> (barra superior) y <strong className="text-white">sidebar</strong> (izquierda):</p>
                <div className="space-y-1.5">
                    {[
                        { tab: "Terminal", desc: "Vista de inicio. Resumen ejecutivo, veredicto institucional y watchlist inteligente.", icon: "🖥️", key: "Alt+1" },
                        { tab: "Market", desc: "Radar de mercado — clusters de señales, mapa de calor, régimen.", icon: "🗺️", key: "Alt+2" },
                        { tab: "Ideas", desc: "Oportunidades del Idea Engine — Value, Quality, Momentum, Reversal, Event.", icon: "💡", key: "Alt+3" },
                        { tab: "Analysis", desc: "Deep-dive: Fundamental (4 analistas IA), Technical (15+ indicadores), Combined (CIO).", icon: "🔬", key: "Alt+4" },
                        { tab: "Portfolio", desc: "Construcción Core-Satellite con Volatility Parity y What-If Simulator.", icon: "💼", key: "Alt+5" },
                        { tab: "System", desc: "Salud del pipeline, proveedores de datos, monitoreo de modelos.", icon: "🧠", key: "Alt+6" },
                        { tab: "Strategy Lab", desc: "Workspace Bloomberg de 4 paneles para investigar estrategias.", icon: "🧪", key: "Alt+7" },
                        { tab: "Marketplace", desc: "Catálogo de estrategias pre-construidas con backtest verificado.", icon: "🏬", key: "Alt+8" },
                        { tab: "AI Assistant", desc: "Chat con IA con acceso al Knowledge Graph del sistema.", icon: "✨", key: "Alt+9" },
                        { tab: "Pilot", desc: "Centro de comando — despliegue de 12 semanas con 3 portafolios paper.", icon: "�", key: "Alt+0" },
                    ].map(t => (
                        <div key={t.tab} className="flex items-start gap-2 bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                            <span>{t.icon}</span>
                            <div className="flex-1">
                                <span className="text-white font-black text-[10px]">{t.tab}</span>
                                <p className="text-gray-500 text-[9px]">{t.desc}</p>
                            </div>
                            <kbd className="bg-[#21262d] border border-[#30363d] px-1.5 py-0.5 rounded text-[8px] font-mono text-gray-500 flex-shrink-0">{t.key}</kbd>
                        </div>
                    ))}
                </div>
                <p className="mt-2 text-gray-600 text-[10px]">En el sidebar: <strong className="text-white">Watch</strong> = watchlist, <strong className="text-white">History</strong> = últimos 50 análisis, <strong className="text-white">Ideas</strong> = oportunidades detectadas automáticamente.</p>
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
                        <p className="text-white text-[10px] font-bold">¿Puedo analizar varias acciones?</p>
                        <p className="text-gray-500 text-[10px] mt-0.5">Sí. Analiza múltiples tickers y guárdalos en tu watchlist con ★. Luego ve al tab Portfolio para ver la cartera construida con todos tus análisis.</p>
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
                Motor de portafolio institucional: Core-Satellite allocation con Volatility Parity sizing. Persistencia en PostgreSQL.
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
                </ul>
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
                        ["Ctrl+K", "Abrir el Command Palette (navegación rápida)"],
                        ["Shift+?", "Abrir / cerrar este panel de ayuda"],
                        ["Esc", "Cerrar este panel / overlays"],
                        ["Alt+1-9,0", "Navegar entre las 10 vistas principales"],
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

            <AccordionItem title="Analizar múltiples tickers">
                <p>Para comparar activos, analiza cada uno individualmente y guárdalos en tu watchlist. El tab <strong className="text-white">Portfolio</strong> construye automáticamente una cartera óptima con todos tus análisis.</p>
            </AccordionItem>

            <AccordionItem title="Exportar análisis">
                <ul className="space-y-1.5">
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
                        <span className="text-[#d4af37] font-mono">PostgreSQL (server)</span>
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
                Autonomous Idea Generation Engine — discovers opportunities across 300+ tickers using 6 modular detectors, configurable strategy profiles, and pluggable universe providers.
            </p>

            <AccordionItem title="Getting Started — How to Use" defaultOpen>
                <ol className="space-y-2 list-decimal list-inside text-gray-400">
                    <li><strong className="text-white">Navigate to the Ideas tab</strong> (Alt+3) in the top navigation bar</li>
                    <li><strong className="text-white">Click ⚡ Universe Scan</strong> — the engine auto-discovers 300+ tickers from multiple sources and scans them in parallel</li>
                    <li><strong className="text-white">Browse the Opportunity Ranking</strong> — ideas are sorted by signal strength, with strategy badges showing how each was detected</li>
                    <li><strong className="text-white">Click any row</strong> to preview the idea details (signals, confidence, detector) in the side panel</li>
                    <li><strong className="text-white">Click Analyze</strong> to run a full Investment Committee analysis on that ticker</li>
                </ol>
                <div className="mt-3 bg-[#0d1117] rounded p-3 border border-[#21262d]">
                    <p className="text-[9px] font-black uppercase tracking-widest text-[#d4af37] mb-1">Two Scan Modes</p>
                    <ul className="space-y-1 text-[10px]">
                        <li><strong className="text-[#d4af37]">⚡ Universe Scan</strong> — auto-discovers tickers from 5+ sources (S&P 500, screener, sector rotation, portfolio, recent ideas). Best for broad discovery.</li>
                        <li><strong className="text-gray-300">↻ Scan Watchlist</strong> — scans only the tickers in your watchlist. Best for monitoring positions you already track.</li>
                    </ul>
                </div>
            </AccordionItem>

            <AccordionItem title="Universe Discovery — Where Tickers Come From" defaultOpen>
                <p className="mb-2">The engine autonomously discovers tickers from <strong className="text-white">6 pluggable sources</strong>. After discovery, duplicates are removed and results are capped to avoid overload.</p>
                <div className="space-y-1.5">
                    {[
                        { name: "Static Index", source: "S&P 500, NASDAQ 100, Dow 30", desc: "Constituents of major US equity indices (~160 tickers)", icon: "📊" },
                        { name: "Screener", source: "Market cap + volume filter", desc: "Large-cap ($1B+), high-volume equities — proxy for institutional liquidity", icon: "🔍" },
                        { name: "Sector Rotation", source: "11 GICS sectors × 10 leaders", desc: "Technology, Healthcare, Financials, Energy, and 7 more sector groups", icon: "🔄" },
                        { name: "Portfolio", source: "Your saved portfolios", desc: "Re-scans tickers from portfolio positions stored in the database", icon: "💼" },
                        { name: "Idea History", source: "Recent strong ideas", desc: "Re-evaluates tickers that generated high-quality ideas in the last 7 days", icon: "📈" },
                        { name: "Custom", source: "User watchlist", desc: "Pass-through for the tickers you manually track in your watchlist", icon: "⭐" },
                    ].map(s => (
                        <div key={s.name} className="bg-[#0d1117] rounded p-2.5 border border-[#21262d]">
                            <div className="flex items-center gap-2">
                                <span>{s.icon}</span>
                                <span className="text-white font-black text-[10px]">{s.name}</span>
                                <span className="text-gray-600 text-[9px] ml-auto font-mono">{s.source}</span>
                            </div>
                            <p className="text-gray-500 text-[9px] mt-0.5 ml-5">{s.desc}</p>
                        </div>
                    ))}
                </div>
                <div className="mt-2 bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                    <p className="text-[9px] font-black uppercase tracking-widest text-[#d4af37] mb-1">Source Breakdown Banner</p>
                    <p className="text-gray-500 text-[10px]">After a Universe Scan, a banner appears above the ranking table showing exactly how many tickers came from each source, the total discovered, unique count after dedup, and discovery time in milliseconds.</p>
                </div>
            </AccordionItem>

            <AccordionItem title="The 6 Detectors">
                <p className="mb-2">Each ticker is evaluated by <strong className="text-white">6 independent detectors</strong>. A ticker can generate multiple ideas if it triggers more than one detector — this signal confluence is a strong indicator.</p>
                {[
                    {
                        name: "Value", icon: "💎", color: "text-emerald-400",
                        desc: "Identifies undervalued assets: high FCF yield, low P/E, low EV/EBITDA, low P/B.",
                        interpretation: "Strong signal when ≥3 of 4 metrics are below thresholds. Indicates fundamental discount vs. intrinsic value.",
                    },
                    {
                        name: "Quality", icon: "🛡️", color: "text-blue-400",
                        desc: "Detects high-quality businesses: high ROIC, stable margins, profitable growth, low leverage.",
                        interpretation: "Strong when ROIC >15%, margins expanding, and D/E <0.5. Indicates franchise value.",
                    },
                    {
                        name: "Growth", icon: "🌱", color: "text-green-400",
                        desc: "Spots high-growth companies: revenue acceleration, earnings expansion, and improving fundamentals.",
                        interpretation: "Strong when both revenue and earnings growth exceed market averages with improving margins.",
                    },
                    {
                        name: "Momentum", icon: "🚀", color: "text-orange-400",
                        desc: "Identifies strong trends: Golden Cross, RSI 50-70, positive MACD, high volume, price above EMA20.",
                        interpretation: "Strong signal = confirmed uptrend across multiple technical indicators. Ideal for trend-following entries.",
                    },
                    {
                        name: "Reversal", icon: "↩️", color: "text-red-400",
                        desc: "Detects potential reversals: oversold RSI, low stochastic, price near lower Bollinger, volume capitulation.",
                        interpretation: "Requires minimum 2 confirming signals. Higher risk — potential bounce after excessive selloff.",
                    },
                    {
                        name: "Event", icon: "⚡", color: "text-purple-400",
                        desc: "Catalysts: significant score changes, earnings surprises, volatility squeezes, high beta opportunities.",
                        interpretation: "Captures events that precede significant price moves. Complements other detectors.",
                    },
                ].map(d => (
                    <div key={d.name} className="bg-[#0d1117] rounded p-3 space-y-1 border border-[#21262d]">
                        <div className="flex items-center gap-2">
                            <span>{d.icon}</span>
                            <span className={`font-black text-[11px] ${d.color}`}>{d.name}</span>
                        </div>
                        <p className="text-gray-400 text-[10px]">{d.desc}</p>
                        <p className="text-gray-600 text-[9px] italic">Interpretation: {d.interpretation}</p>
                    </div>
                ))}
            </AccordionItem>

            <AccordionItem title="Strategy Profiles">
                <p className="mb-2">Strategy Profiles configure <strong className="text-white">which detectors are active</strong> and <strong className="text-white">how ideas are ranked</strong>, adapting the engine to different investment styles:</p>
                <div className="space-y-1.5">
                    {[
                        { name: "Buy & Hold", desc: "Value + Quality focus. Long-term wealth building with undervalued, high-quality companies.", horizon: "1-5 years" },
                        { name: "Swing", desc: "Momentum + Event focus. Medium-term trend-following with catalyst opportunities.", horizon: "2-8 weeks" },
                        { name: "Deep Value", desc: "Heavy Value weighting. Contrarian approach — seeks maximum fundamental discount.", horizon: "6-18 months" },
                        { name: "Growth Quality", desc: "Growth + Quality focus. Premium companies with strong growth trajectories.", horizon: "1-3 years" },
                        { name: "Event Driven", desc: "Event + Momentum focus. Captures catalysts and high-volatility opportunities.", horizon: "Days to weeks" },
                    ].map(p => (
                        <div key={p.name} className="flex items-start gap-2 bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                            <div className="flex-1">
                                <span className="text-white font-black text-[10px]">{p.name}</span>
                                <p className="text-gray-500 text-[9px]">{p.desc}</p>
                            </div>
                            <span className="text-[#d4af37] text-[8px] font-mono flex-shrink-0">{p.horizon}</span>
                        </div>
                    ))}
                </div>
            </AccordionItem>

            <AccordionItem title="Understanding the Results">
                <div className="space-y-2">
                    <div className="bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                        <p className="text-white text-[10px] font-bold">Signal Strength (%)</p>
                        <p className="text-gray-500 text-[9px] mt-0.5">Proportion of detector signals that fired for this idea. 100% = all possible signals confirm the opportunity. Higher is stronger.</p>
                    </div>
                    <div className="bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                        <p className="text-white text-[10px] font-bold">Confidence Level</p>
                        <div className="mt-1 space-y-0.5 text-[9px]">
                            <div className="flex gap-2"><Signal label="HIGH" color="bg-green-500/15 border-green-500/30 text-green-400" /><span className="text-gray-500">≥60% of signals activated — high probability opportunity</span></div>
                            <div className="flex gap-2"><Signal label="MEDIUM" color="bg-yellow-500/15 border-yellow-500/30 text-yellow-400" /><span className="text-gray-500">40-60% — moderate signal, validate with full analysis</span></div>
                            <div className="flex gap-2"><Signal label="LOW" color="bg-gray-500/15 border-gray-500/30 text-gray-400" /><span className="text-gray-500">&lt;40% — weak signal, treat as exploratory</span></div>
                        </div>
                    </div>
                    <div className="bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                        <p className="text-white text-[10px] font-bold">Reliability Score (%)</p>
                        <p className="text-gray-500 text-[9px] mt-0.5">Measures how trustworthy the idea is, based on detector calibration and confirmation quality. Independent from signal strength — an idea can be strong but unreliable (or vice versa).</p>
                    </div>
                    <div className="bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                        <p className="text-white text-[10px] font-bold">Priority Ranking (#)</p>
                        <p className="text-gray-500 text-[9px] mt-0.5">Ideas are ranked #1 = best opportunity. The ranking considers signal strength, confidence, and a bonus for tickers with multiple detectors firing (signal confluence).</p>
                    </div>
                    <div className="bg-[#0d1117] rounded px-3 py-2 border border-[#21262d]">
                        <p className="text-white text-[10px] font-bold">Multiple Ideas per Ticker</p>
                        <p className="text-gray-500 text-[9px] mt-0.5">A single ticker can generate multiple ideas (e.g., AAPL may appear as both a Value and Quality idea). This <strong className="text-white">signal confluence</strong> indicates a more robust opportunity.</p>
                    </div>
                </div>
            </AccordionItem>

            <AccordionItem title="Actions on Ideas">
                <ul className="space-y-1.5">
                    <li><strong className="text-[#d4af37]">Analyze</strong> — run the full Investment Committee pipeline (Fundamental AI + Technical + CIO Decision) for that ticker.</li>
                    <li><strong className="text-red-400">✕ Dismiss</strong> — remove the idea from the active list. Does not delete data.</li>
                    <li><strong className="text-white">Click Row</strong> — opens the preview panel on the right showing the idea&apos;s signals, detector type, strength gauge, and a &quot;Run Full Analysis&quot; button.</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Filters & Sorting">
                <p>The left sidebar panel provides controls to narrow your focus:</p>
                <ul className="mt-1.5 space-y-1 text-[10px]">
                    <li><span className="text-emerald-400 font-bold">Value</span> — undervalued assets with fundamental discount</li>
                    <li><span className="text-blue-400 font-bold">Quality</span> — high-quality franchises with strong moats</li>
                    <li><span className="text-green-400 font-bold">Growth</span> — companies with accelerating growth</li>
                    <li><span className="text-orange-400 font-bold">Momentum</span> — confirmed uptrend with technical strength</li>
                    <li><span className="text-red-400 font-bold">Reversal</span> — potential bounce after excessive selloff</li>
                    <li><span className="text-purple-400 font-bold">Event</span> — catalyst-driven opportunities</li>
                </ul>
                <p className="mt-2 text-gray-600 text-[10px]">Sort by <strong className="text-white">Score</strong> (default, strongest signal first) or <strong className="text-white">Ticker</strong> (alphabetical). Use the search bar to filter by ticker symbol.</p>
            </AccordionItem>

            <AccordionItem title="FAQ">
                <div className="space-y-3">
                    <div>
                        <p className="text-white text-[10px] font-bold">How long does a Universe Scan take?</p>
                        <p className="text-gray-500 text-[10px] mt-0.5">Universe discovery takes ~5ms. The full scan depends on how many tickers are found (typically 50-200). With 50 tickers, expect ~10-30 seconds.</p>
                    </div>
                    <div>
                        <p className="text-white text-[10px] font-bold">Why does a ticker appear multiple times?</p>
                        <p className="text-gray-500 text-[10px] mt-0.5">Each detector evaluates independently. If AAPL triggers both the Value and Quality detectors, it generates 2 separate ideas. This <strong className="text-white">confluence</strong> is actually a stronger signal.</p>
                    </div>
                    <div>
                        <p className="text-white text-[10px] font-bold">What does "No ideas found" mean?</p>
                        <p className="text-gray-500 text-[10px] mt-0.5">None of the scanned tickers met the minimum thresholds for any detector. This can happen when markets are in a neutral regime. Try changing the strategy profile or waiting for market conditions to shift.</p>
                    </div>
                    <div>
                        <p className="text-white text-[10px] font-bold">Can I change which sources are used?</p>
                        <p className="text-gray-500 text-[10px] mt-0.5">The API supports configurable sources via <code className="text-[#d4af37] bg-[#161b22] px-1 rounded">POST /ideas/scan/auto</code> with a <code className="text-[#d4af37] bg-[#161b22] px-1 rounded">sources</code> array. The UI defaults to all 5 automated sources.</p>
                    </div>
                    <div>
                        <p className="text-white text-[10px] font-bold">What&apos;s the difference between Strength and Reliability?</p>
                        <p className="text-gray-500 text-[10px] mt-0.5"><strong className="text-white">Strength</strong> measures how many signals fired (attractiveness). <strong className="text-white">Reliability</strong> measures how trustworthy the detection is (calibration quality). An idea can be strong but unreliable (e.g., based on volatile data).</p>
                    </div>
                </div>
            </AccordionItem>
        </div>
    );
}

// ─── Market Section ───────────────────────────────────────────────────────────

function MarketSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Vista panorámica del mercado. Muestra señales activas, clusters de oportunidades y el mapa de calor del universo.
            </p>
            <AccordionItem title="¿Qué es?" defaultOpen>
                <p>La vista <strong className="text-white">Market</strong> (Alt+2) muestra el estado general del mercado y las oportunidades detectadas por el sistema. Es tu radar de mercado institucional.</p>
            </AccordionItem>
            <AccordionItem title="Componentes principales">
                <ul className="space-y-1.5">
                    <li><strong className="text-white">Signal Clusters</strong> — agrupaciones de señales activas por tipo (momentum, value, quality, reversal, event). Permite ver qué estilos están dominando.</li>
                    <li><strong className="text-white">Opportunity Map</strong> — mapa de calor con los tickers más prometedores según el CASE score. Verde = oportunidad, rojo = riesgo.</li>
                    <li><strong className="text-white">Market Regime</strong> — indicador del régimen actual (Bull, Bear, Sideways) basado en indicadores técnicos agregados.</li>
                </ul>
            </AccordionItem>
            <AccordionItem title="Cómo interpretar">
                <ul className="space-y-1.5">
                    <li><strong className="text-white">Muchos clusters Value</strong> — el mercado puede estar sobrevendido, buenas oportunidades de compra</li>
                    <li><strong className="text-white">Muchos clusters Momentum</strong> — tendencias fuertes activas, seguir la dirección</li>
                    <li><strong className="text-white">Pocos clusters</strong> — mercado en pausa, esperar confirmación</li>
                </ul>
            </AccordionItem>
        </div>
    );
}

// ─── Signals / CASE Section ──────────────────────────────────────────────────

function SignalsSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Biblioteca de 50+ señales Alpha organizadas en 8 categorías, evaluadas por el pipeline CASE (Composite Alpha Score Engine).
            </p>
            <AccordionItem title="¿Qué es el CASE Score?" defaultOpen>
                <p>El <strong className="text-white">Composite Alpha Score Engine (CASE)</strong> es el sistema de puntuación que combina múltiples señales en un score unificado de 0-100 para cada ticker:</p>
                <div className="mt-2 space-y-1">
                    <div className="flex justify-between bg-[#0d1117] rounded px-3 py-1.5 border border-[#21262d] text-[10px]">
                        <span className="text-green-400 font-bold">80-100</span>
                        <span className="text-gray-400">Oportunidad excepcional — múltiples señales confirman</span>
                    </div>
                    <div className="flex justify-between bg-[#0d1117] rounded px-3 py-1.5 border border-[#21262d] text-[10px]">
                        <span className="text-[#d4af37] font-bold">60-79</span>
                        <span className="text-gray-400">Señal moderada — vale la pena investigar</span>
                    </div>
                    <div className="flex justify-between bg-[#0d1117] rounded px-3 py-1.5 border border-[#21262d] text-[10px]">
                        <span className="text-gray-400 font-bold">40-59</span>
                        <span className="text-gray-400">Neutral — señales mixtas</span>
                    </div>
                    <div className="flex justify-between bg-[#0d1117] rounded px-3 py-1.5 border border-[#21262d] text-[10px]">
                        <span className="text-red-400 font-bold">0-39</span>
                        <span className="text-gray-400">Débil — pocas señales activas</span>
                    </div>
                </div>
            </AccordionItem>
            <AccordionItem title="Fórmula CASE: P×C×R">
                <p>El CASE combina 3 dimensiones con pesos configurables:</p>
                <ul className="mt-1.5 space-y-1">
                    <li><strong className="text-white">P (Potencia)</strong> — fuerza bruta de la señal (cuántas sub-señales se activaron)</li>
                    <li><strong className="text-white">C (Confianza)</strong> — confiabilidad histórica de la señal (hit rate, Sharpe)</li>
                    <li><strong className="text-white">R (Relevancia)</strong> — frescura de la señal; las señales decaen exponencialmente con el tiempo</li>
                </ul>
            </AccordionItem>
            <AccordionItem title="Las 8 categorías de señales">
                <div className="space-y-1">
                    {[
                        { cat: "Momentum", desc: "Tendencia de precio (SMA, MACD, RSI)" },
                        { cat: "Value", desc: "Valuación relativa (P/E, P/B, FCF Yield)" },
                        { cat: "Quality", desc: "Calidad del negocio (ROIC, márgenes, deuda)" },
                        { cat: "Growth", desc: "Crecimiento de ingresos, beneficios y expansión" },
                        { cat: "Flow", desc: "Flujos institucionales y de opciones" },
                        { cat: "Macro", desc: "Indicadores macroeconómicos" },
                        { cat: "Volatility", desc: "Régimen de volatilidad y Bollinger" },
                        { cat: "Event", desc: "Earnings, splits, catalizadores especiales" },
                    ].map(s => (
                        <div key={s.cat} className="flex items-center gap-2 bg-[#0d1117] rounded px-3 py-1.5 border border-[#21262d] text-[10px]">
                            <span className="text-[#d4af37] font-bold w-20">{s.cat}</span>
                            <span className="text-gray-400">{s.desc}</span>
                        </div>
                    ))}
                </div>
            </AccordionItem>
            <AccordionItem title="Alpha Decay (vida media)">
                <p>Cada señal tiene una <strong className="text-white">vida media</strong> — el tiempo en que mantiene su poder predictivo. El sistema aplica decaimiento exponencial automáticamente:</p>
                <ul className="mt-1.5 space-y-1">
                    <li><strong className="text-green-400">Fresca</strong> — señal recién generada, máxima potencia</li>
                    <li><strong className="text-[#d4af37]">Madura</strong> — 50-80% de potencia restante</li>
                    <li><strong className="text-red-400">Decaída</strong> — &lt;50% de potencia, considerar si aún es válida</li>
                </ul>
            </AccordionItem>
            <AccordionItem title="Radar y Gauge">
                <ul className="space-y-1.5">
                    <li><strong className="text-white">Alpha Gauge</strong> — medidor semicircular que muestra el CASE score total. La aguja indica la fuerza global de señales activas.</li>
                    <li><strong className="text-white">Radar Chart</strong> — diagrama radar que muestra la distribución de señales en las 8 categorías. Categorías con picos altos = señales fuertes en ese estilo.</li>
                </ul>
            </AccordionItem>
        </div>
    );
}

// ─── System Section ──────────────────────────────────────────────────────────

function SystemSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Panel de salud del sistema: estado del pipeline, proveedores de datos, monitoreo de modelos, y alertas de drift.
            </p>
            <AccordionItem title="¿Qué es?" defaultOpen>
                <p>La vista <strong className="text-white">System</strong> (Alt+6) es el centro de operaciones. Muestra si todos los motores y proveedores de datos están funcionando correctamente.</p>
            </AccordionItem>
            <AccordionItem title="Dashboard de Salud">
                <ul className="space-y-1.5">
                    <li><strong className="text-white">Provider Health</strong> — estado de cada fuente de datos (Market Data, ETF Flows, Options, Institutional Flow, News, Macro). Verde = activo, rojo = caído.</li>
                    <li><strong className="text-white">Pipeline Status</strong> — estado del ciclo diario (idle/running/complete/failed)</li>
                    <li><strong className="text-white">Model Monitoring</strong> — performance de los modelos de IA, alertas de drift si la calidad cae</li>
                    <li><strong className="text-white">Circuit Breakers</strong> — si un componente falla repetidamente, se desactiva automáticamente para proteger el sistema</li>
                </ul>
            </AccordionItem>
            <AccordionItem title="Cómo interpretar">
                <ul className="space-y-1.5">
                    <li><strong className="text-green-400">Todo verde</strong> — sistema operando normalmente</li>
                    <li><strong className="text-yellow-400">Amarillo</strong> — algún proveedor degradado; los análisis pueden tener datos incompletos</li>
                    <li><strong className="text-red-400">Rojo</strong> — componente caído; el sistema usa fallbacks pero la calidad puede ser menor</li>
                </ul>
            </AccordionItem>
        </div>
    );
}

// ─── Pilot Section ───────────────────────────────────────────────────────────

function PilotSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Centro de comando del piloto: validación de 12 semanas con 3 portafolios paper ($1M cada uno).
            </p>
            <AccordionItem title="¿Qué es el Pilot?" defaultOpen>
                <p>El <strong className="text-white">Pilot Command Center</strong> (Alt+0) ejecuta un despliegue de prueba de 12 semanas con 3 portafolios paper trading. Valida que el sistema genera alpha real antes de comprometer capital.</p>
            </AccordionItem>
            <AccordionItem title="Los 3 portafolios">
                <ul className="space-y-1.5">
                    <li><strong className="text-[#d4af37]">Research</strong> — Top 8 tickers por CASE score. Portafolio basado en señales del sistema. Es el que debe generar alpha.</li>
                    <li><strong className="text-green-400">Strategy</strong> — Equal-weight de los 10 tickers del universo piloto. Referencia del peso igualitario.</li>
                    <li><strong className="text-blue-400">Benchmark</strong> — 70% SPY + 30% QQQ. Comparación vs. el mercado.</li>
                </ul>
            </AccordionItem>
            <AccordionItem title="Las 4 fases">
                <ul className="space-y-1.5">
                    <li><strong className="text-blue-400">Setup</strong> (Sem 0) — Inicialización de portafolios y configuración</li>
                    <li><strong className="text-yellow-400">Observation</strong> (Sem 1-4) — Sistema recolecta datos, no opera</li>
                    <li><strong className="text-green-400">Paper Trading</strong> (Sem 5-8) — Ejecución paper con posiciones reales</li>
                    <li><strong className="text-purple-400">Evaluation</strong> (Sem 9-12) — Evaluación de criterios Go/No-Go</li>
                </ul>
            </AccordionItem>
            <AccordionItem title="Cómo usar el dashboard">
                <ol className="space-y-1.5 list-decimal list-inside">
                    <li><strong className="text-white">▶ Run Daily Cycle</strong> — ejecuta el pipeline completo (data → signals → allocation → snapshot). Tarda ~27s.</li>
                    <li><strong className="text-white">⏭ Advance Phase</strong> — avanza a la siguiente fase del piloto</li>
                    <li><strong className="text-white">↻ Refresh</strong> — actualiza los datos del dashboard</li>
                </ol>
            </AccordionItem>
            <AccordionItem title="Interpretar las Equity Curves">
                <ul className="space-y-1.5">
                    <li><strong className="text-white">NAV</strong> — Net Asset Value. El valor total del portafolio. Empieza en $1M.</li>
                    <li><strong className="text-white">Retorno acumulado</strong> — ganancia/pérdida total desde el inicio. Research debe superar a Benchmark para validar alpha.</li>
                    <li><strong className="text-white">Gráfico de líneas</strong> — aparece con 2+ ciclos en días diferentes. Las líneas se separan cuando los portafolios tienen diferente performance.</li>
                </ul>
            </AccordionItem>
            <AccordionItem title="Tabla de posiciones">
                <p>Muestra las posiciones actuales de cada portafolio:</p>
                <ul className="mt-1.5 space-y-1">
                    <li><strong className="text-white">Weight %</strong> — porcentaje del portafolio asignado. Research varía por CASE; Strategy es 10% cada uno; Benchmark es 70/30.</li>
                    <li><strong className="text-white">Shares</strong> — cantidad de acciones (calculadas con precios reales de mercado)</li>
                    <li><strong className="text-white">P&L %</strong> — ganancia/pérdida porcentual desde la entrada. Verde = ganando, rojo = perdiendo.</li>
                </ul>
            </AccordionItem>
            <AccordionItem title="Criterios de éxito">
                <p>Al final de las 12 semanas, el sistema evalúa automáticamente:</p>
                <ul className="mt-1.5 space-y-1">
                    <li>Research Alpha &gt; 0 vs Benchmark</li>
                    <li>Information Ratio &gt; 0.5</li>
                    <li>Max Drawdown &lt; 15%</li>
                    <li>Hit Rate de señales &gt; 55%</li>
                    <li>Uptime del sistema &gt; 99%</li>
                </ul>
            </AccordionItem>
        </div>
    );
}

// ─── Strategy Lab Section ────────────────────────────────────────────────────

function StrategyLabSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Laboratorio de investigación de estrategias estilo Bloomberg. Workspace multi-panel para diseñar, comparar y validar estrategias.
            </p>
            <AccordionItem title="¿Qué es?" defaultOpen>
                <p>El <strong className="text-white">Strategy Lab</strong> (Alt+7) es un workspace de 4 paneles inspirado en terminales Bloomberg/Aladdin. Permite investigar estrategias de inversión de forma profesional.</p>
            </AccordionItem>
            <AccordionItem title="Los 4 paneles">
                <ul className="space-y-1.5">
                    <li><strong className="text-white">📋 Strategy List</strong> (izquierda) — catálogo de estrategias disponibles. Clic en una para cargarla.</li>
                    <li><strong className="text-white">📈 Detail / Performance</strong> (centro) — equity curve, drawdown, métricas de la estrategia seleccionada</li>
                    <li><strong className="text-white">🧠 Intelligence Panel</strong> (derecha) — chat con IA sobre la estrategia, análisis contextual</li>
                    <li><strong className="text-white">📊 Bottom Analytics</strong> (inferior) — parámetros, composición, y datos históricos</li>
                </ul>
            </AccordionItem>
            <AccordionItem title="Métricas clave">
                <ul className="space-y-1.5">
                    <li><strong className="text-white">Sharpe Ratio</strong> — retorno ajustado por riesgo. &gt;1.5 = bueno, &gt;2.0 = excelente</li>
                    <li><strong className="text-white">Max Drawdown</strong> — caída máxima desde un pico. &lt;10% = conservador, &lt;20% = moderado</li>
                    <li><strong className="text-white">Win Rate</strong> — porcentaje de trades ganadores. &gt;55% = bueno en combinación con buen risk/reward</li>
                    <li><strong className="text-white">Quality Score</strong> — puntuación 0-100 del Scorecard. Integra todos los factores anteriores.</li>
                </ul>
            </AccordionItem>
            <AccordionItem title="Comparar estrategias">
                <p>Selecciona 2+ estrategias y usa <strong className="text-white">Compare</strong> para ver side-by-side: equity curves superpuestas, tabla de métricas comparativa, y ranking general.</p>
            </AccordionItem>
        </div>
    );
}

// ─── Marketplace Section ─────────────────────────────────────────────────────

function MarketplaceSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Repositorio de estrategias pre-construidas. Explora, evalúa y despliega estrategias institucionales.
            </p>
            <AccordionItem title="¿Qué es?" defaultOpen>
                <p>El <strong className="text-white">Marketplace</strong> (Alt+8) es un catálogo de estrategias verificadas listas para usar. Cada estrategia incluye backtest histórico, métricas de rendimiento y composición.</p>
            </AccordionItem>
            <AccordionItem title="Cómo evaluar una estrategia">
                <ol className="space-y-1.5 list-decimal list-inside">
                    <li>Revisa el <strong className="text-white">Quality Score</strong> (0-100) — resume la robustez general</li>
                    <li>Verifica el <strong className="text-white">Sharpe Ratio</strong> — &gt;1.5 es aceptable para producción</li>
                    <li>Confirma que el <strong className="text-white">Max Drawdown</strong> es tolerable para tu perfil de riesgo</li>
                    <li>Mira el <strong className="text-white">Regime Stability</strong> — estrategias "estables" funcionan en más condiciones de mercado</li>
                </ol>
            </AccordionItem>
        </div>
    );
}

// ─── AI Assistant Section ────────────────────────────────────────────────────

function AssistantSection() {
    return (
        <div className="space-y-3">
            <p className="text-[10px] text-gray-500 px-1">
                Asistente de investigación con IA. Haz preguntas sobre el mercado, estrategias, y los datos del sistema.
            </p>
            <AccordionItem title="¿Qué es?" defaultOpen>
                <p>El <strong className="text-white">AI Assistant</strong> (Alt+9) es un chat con IA que tiene acceso al Knowledge Graph del sistema. Puede responder preguntas sobre tickers analizados, estrategias, y métricas.</p>
            </AccordionItem>
            <AccordionItem title="Ejemplos de uso">
                <ul className="space-y-1.5">
                    <li><strong className="text-white">"¿Cuál es la tesis de inversión para NVDA?"</strong> — resume el análisis fundamental más reciente</li>
                    <li><strong className="text-white">"Compara AAPL vs MSFT en calidad"</strong> — compara métricas de calidad entre tickers</li>
                    <li><strong className="text-white">"¿Qué señales están activas hoy?"</strong> — lista las señales Alpha activas del día</li>
                    <li><strong className="text-white">"Explica el CASE score de AMZN"</strong> — desglosa el score compuesto</li>
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
    { id: "signals", label: "Señales", Icon: Radio },
    { id: "portfolio", label: "Portfolio", Icon: Briefcase },
    { id: "ideas", label: "Ideas", Icon: Lightbulb },
    { id: "market", label: "Market", Icon: Globe },
    { id: "system", label: "System", Icon: Settings },
    { id: "pilot", label: "Pilot", Icon: Activity },
    { id: "strategylab", label: "Strategy Lab", Icon: FlaskConical },
    { id: "marketplace", label: "Marketplace", Icon: Store },
    { id: "assistant", label: "AI Assistant", Icon: Bot },
    { id: "tips", label: "Tips Pro", Icon: HelpCircle },
];

// ─── Main HelpPanel ───────────────────────────────────────────────────────────

export default function HelpPanel({ open, onClose, standalone = false }: HelpPanelProps) {
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

    // ── Panel content (shared between standalone and overlay modes) ──────────
    const panelContent = (
        <div
            ref={panelRef}
            tabIndex={-1}
            role="dialog"
            aria-label="Centro de ayuda"
            className={standalone
                ? "flex flex-col h-screen bg-[#0d1117] text-gray-300 outline-none"
                : "fixed top-0 right-0 h-full w-[420px] max-w-[100vw] z-50 flex flex-col bg-[#0d1117] border-l border-[#30363d] shadow-2xl outline-none"
            }
            style={standalone ? undefined : { animation: "slideInHelpPanel 0.25s cubic-bezier(0.4,0,0.2,1) both" }}
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
            <div className="relative flex-shrink-0">
                {/* Scroll gradient hints */}
                <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-6 z-10 bg-gradient-to-r from-[#0d1117] to-transparent" />
                <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-6 z-10 bg-gradient-to-l from-[#0d1117] to-transparent" />
                <div className={`flex flex-nowrap border-b border-[#21262d] overflow-x-auto custom-scrollbar ${standalone ? "flex-wrap" : ""}`}>
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
            </div>

            {/* Content */}
            <div key={activeTab} className={`flex-1 overflow-y-auto space-y-3 ${standalone ? "p-6 max-w-4xl mx-auto w-full" : "p-4"}`} style={{ animation: 'fadeSlideIn 0.2s ease both' }}>
                {activeTab === "start" && <StartSection />}
                {activeTab === "fundamental" && <FundamentalSection />}
                {activeTab === "technical" && <TechnicalSection />}
                {activeTab === "combined" && <CombinedSection />}
                {activeTab === "signals" && <SignalsSection />}
                {activeTab === "portfolio" && <PortfolioSection />}
                {activeTab === "ideas" && <IdeasHelpSection />}
                {activeTab === "market" && <MarketSection />}
                {activeTab === "system" && <SystemSection />}
                {activeTab === "pilot" && <PilotSection />}
                {activeTab === "strategylab" && <StrategyLabSection />}
                {activeTab === "marketplace" && <MarketplaceSection />}
                {activeTab === "assistant" && <AssistantSection />}
                {activeTab === "tips" && <TipsSection />}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-[#21262d] flex-shrink-0 flex items-center justify-between">
                <span className="text-[9px] text-gray-700 font-mono">365 Advisers v4.0</span>
                <span className="text-[9px] text-gray-700">
                    Presiona <kbd className="bg-[#21262d] border border-[#30363d] px-1 rounded text-[8px]">Esc</kbd> para cerrar
                </span>
            </div>
        </div>
    );

    // ── Standalone mode: render directly (full page) ────────────────────────
    if (standalone) {
        return panelContent;
    }

    // ── Overlay mode: render via portal ─────────────────────────────────────
    return createPortal(
        <>
            {/* Overlay backdrop */}
            <div
                className="fixed inset-0 bg-black/50 z-40 backdrop-blur-sm"
                onClick={onClose}
                aria-hidden="true"
            />

            {panelContent}

            <style jsx global>{`
        @keyframes slideInHelpPanel {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
      `}</style>
        </>
        , document.body);
}
