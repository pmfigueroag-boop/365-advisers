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

type HelpTab = "start" | "fundamental" | "technical" | "combined" | "portfolio" | "tips";

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
            <AccordionItem title="¿Cómo analizar un ticker?" defaultOpen>
                <ol className="space-y-1.5 list-decimal list-inside text-gray-400">
                    <li>Escribe el símbolo en la barra superior (ej. <code className="text-[#d4af37] bg-[#161b22] px-1 rounded">AAPL</code>)</li>
                    <li>Haz clic en <strong className="text-white">Analyze</strong> o presiona <kbd className="bg-[#21262d] border border-[#30363d] px-1 rounded text-[9px]">Enter</kbd></li>
                    <li>El sistema ejecuta 4 motores en paralelo: Fundamental (LangGraph IA), Technical (determinístico), Decision Engine (CIO Synthesizer) y Portfolio Engine (~40-60 s primera vez)</li>
                    <li>Navega entre las pestañas <strong className="text-white">Fundamental</strong>, <strong className="text-white">Technical</strong>, <strong className="text-white">Combined</strong> y <strong className="text-white">Portfolio</strong></li>
                </ol>
                <p className="mt-2 text-gray-600 text-[10px]">Las siguientes consultas del mismo ticker son instantáneas gracias al caché.</p>
            </AccordionItem>

            <AccordionItem title="Interpretación de señales" defaultOpen>
                <div className="space-y-2">
                    {[
                        { range: "8.0 – 10", label: "STRONG BUY", color: "bg-green-500/10 border-green-500/30 text-green-400", desc: "Convicción altísima — negocio excepcional a precio atractivo" },
                        { range: "6.0 – 7.9", label: "BUY", color: "bg-green-500/10 border-green-500/20 text-green-400", desc: "Oportunidad interesante con catalizadores claros" },
                        { range: "4.0 – 5.9", label: "HOLD", color: "bg-[#d4af37]/10 border-[#d4af37]/20 text-[#d4af37]", desc: "Calidad pero valuación plena — mantener, sin agregar" },
                        { range: "2.0 – 3.9", label: "SELL", color: "bg-red-500/10 border-red-500/20 text-red-400", desc: "Riesgo/recompensa desfavorable" },
                        { range: "0 – 1.9", label: "AVOID", color: "bg-red-500/20 border-red-500/30 text-red-400", desc: "Riesgos significativos — evitar posición larga" },
                    ].map(s => (
                        <div key={s.label} className="flex items-start gap-2">
                            <span className="text-gray-600 w-20 flex-shrink-0 font-mono text-[9px]">{s.range}</span>
                            <Signal label={s.label} color={s.color} />
                            <span className="text-gray-500 text-[10px]">{s.desc}</span>
                        </div>
                    ))}
                </div>
                <p className="mt-3 text-gray-700 text-[9px]">⚠️ No es una recomendación de inversión. Realiza siempre tu propio análisis.</p>
            </AccordionItem>

            <AccordionItem title="Watchlist e historial">
                <ul className="space-y-1.5">
                    <li><strong className="text-white">★</strong> en el header — guarda el ticker en tu watchlist con señal automática</li>
                    <li>Clic en un ticker del sidebar — lo carga sin tener que escribirlo de nuevo</li>
                    <li><strong className="text-white">HISTORY</strong> en el sidebar — últimos 50 análisis, persistidos en localStorage</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Vista Heatmap de Watchlist">
                <p>La watchlist tiene dos modos de visualización:</p>
                <ul className="mt-1.5 space-y-1">
                    <li><strong className="text-white">Lista</strong> — vista clásica con ticker, nombre, señal y fecha</li>
                    <li><strong className="text-white">Heatmap</strong> — cuadrícula compacta con color basado en el delta de score (verde = mejora, rojo = deterioro)</li>
                </ul>
                <p className="mt-1.5 text-gray-600 text-[10px]">Cambia entre vistas con los iconos 📋/🟩 en la cabecera del sidebar.</p>
            </AccordionItem>

            <AccordionItem title="Glosario interactivo">
                <p>Los indicadores técnicos y ratios fundamentales en la plataforma tienen <strong className="text-white">tooltips interactivos</strong>. Pasa el cursor sobre cualquier término subrayado (ej. RSI, P/E, ROIC) para ver su definición en español.</p>
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
                <ul className="space-y-1.5">
                    <li><strong className="text-white">Señal</strong> — BUY / AVOID / HOLD del agente individual</li>
                    <li><strong className="text-white">Convicción %</strong> — certeza del agente en su tesis. &gt;85% = alta.</li>
                    <li><strong className="text-white">Texto</strong> — razonamiento en lenguaje natural con datos reales de mercado</li>
                </ul>
                <p className="mt-2 text-gray-600 text-[10px]">El Committee Supervisor pondera los 4 memos y emite el veredicto final.</p>
            </AccordionItem>

            <AccordionItem title="Research Memo (1-pager)">
                <p>Scroll hacia abajo en el tab Fundamental para ver el <strong className="text-white">Research Memo</strong> — resumen institucional estructurado que incluye tesis de inversión, catalizadores, riesgos y conclusión.</p>
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
                    <li><strong className="text-white">Investment Position</strong> — BUY / HOLD / SELL / AVOID / Strong Opportunity</li>
                    <li><strong className="text-white">Confidence %</strong> — nivel de certeza institucional (0–100%)</li>
                    <li><strong className="text-white">CIO Memo</strong> — tesis de inversión, visión de valuación, contexto técnico, catalizadores y riesgos</li>
                </ul>
                <div className="mt-2 px-3 py-2 bg-[#0d1117] rounded border border-[#21262d] font-mono text-[10px] text-center text-[#d4af37]">
                    Scores: Fund {"→"} X.X / 10 · Tech {"→"} X.X / 10 · Confidence {"→"} XX%
                </div>
            </AccordionItem>

            <AccordionItem title="Position Sizing">
                <p>Debajo del veredicto, el bloque <strong className="text-white">Portfolio Allocation Suggestion</strong> calcula el tamaño de posición recomendado:</p>
                <ul className="mt-1.5 space-y-1">
                    <li><strong className="text-white">Opportunity Score</strong> — score 0–10 del potencial de la oportunidad</li>
                    <li><strong className="text-white">Conviction Level</strong> — Low / Medium / High / Very High</li>
                    <li><strong className="text-white">Base Size %</strong> — tamaño base antes de ajuste por riesgo</li>
                    <li><strong className="text-white">Risk Adjustment</strong> — multiplicador por volatilidad (ATR) y nivel de riesgo</li>
                    <li><strong className="text-white">Suggested Allocation %</strong> — posición final sugerida (max 10%)</li>
                </ul>
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

// ─── Tab Config ───────────────────────────────────────────────────────────────

const TABS: { id: HelpTab; label: string; Icon: React.ElementType }[] = [
    { id: "start", label: "Inicio", Icon: Rocket },
    { id: "fundamental", label: "Fundamental", Icon: ShieldCheck },
    { id: "technical", label: "Técnico", Icon: LineChart },
    { id: "combined", label: "Combined", Icon: Zap },
    { id: "portfolio", label: "Portfolio", Icon: Briefcase },
    { id: "tips", label: "Tips Pro", Icon: Lightbulb },
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
