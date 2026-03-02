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
    ChevronDown,
    ChevronRight,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface HelpPanelProps {
    open: boolean;
    onClose: () => void;
}

type HelpTab = "start" | "fundamental" | "technical" | "combined" | "tips";

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
                    <li>El sistema ejecuta los 3 motores en paralelo (~40-50 s primera vez)</li>
                    <li>Navega entre las pestañas <strong className="text-white">Fundamental</strong>, <strong className="text-white">Technical</strong> y <strong className="text-white">Combined</strong></li>
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
                Orquesta ambos motores en una sola petición SSE y sintetiza un veredicto unificado.
            </p>

            <AccordionItem title="Status Timeline" defaultOpen>
                <div className="flex items-center gap-2 py-2 px-3 bg-[#0d1117] rounded border border-[#21262d] font-mono text-[9px]">
                    <span className="text-green-400">● Data</span>
                    <span className="text-gray-700">───</span>
                    <span className="text-[#d4af37]">● Analysts</span>
                    <span className="text-gray-700">───</span>
                    <span className="text-blue-400">● Technical</span>
                    <span className="text-gray-700">───</span>
                    <span className="text-gray-400">● Done</span>
                </div>
                <ul className="mt-2 space-y-1">
                    <li><strong className="text-green-400">Data</strong> — ratios financieros cargados (Yahoo Finance)</li>
                    <li><strong className="text-[#d4af37]">Analysts</strong> — 4 agentes de IA procesando en paralelo</li>
                    <li><strong className="text-blue-400">Technical</strong> — indicadores calculados</li>
                    <li><strong className="text-white">Done</strong> — stream completo; badge CACHED si viene de DB</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Score combinado">
                <p>El score unificado es la <strong className="text-white">media simple</strong> del score fundamental y el técnico:</p>
                <div className="my-2 px-3 py-2 bg-[#0d1117] rounded border border-[#21262d] font-mono text-[10px] text-center text-[#d4af37]">
                    Combined = (Fundamental + Technical) / 2
                </div>
                <p>El gauge semicircular lo visualiza en formato 0–10. El veredicto (BUY/HOLD/SELL) se deriva de ese score combinado.</p>
            </AccordionItem>

            <AccordionItem title="Sub-tabs del Combined">
                <ul className="space-y-2">
                    <li><strong className="text-white">Overview</strong> — catalizadores y riesgos sintetizados del Committee</li>
                    <li><strong className="text-white">Analysts (4/4)</strong> — los 4 memos completos del motor fundamental</li>
                    <li><strong className="text-white">Tech [score]</strong> — IndicatorGrid completo del motor técnico</li>
                    <li><strong className="text-white">History</strong> — gráfico de evolución de scores a lo largo del tiempo</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Botón REFRESH">
                <p>El botón <strong className="text-white">REFRESH</strong> en la esquina superior derecha del Combined tab invalida ambos cachés y fuerza un recálculo completo — útil cuando el precio ha movido significativamente o quieres datos frescos del mercado.</p>
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
                        ["Esc", "Cerrar este panel de ayuda"],
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
                    <li>API directa: agrega <code className="text-[#d4af37] bg-[#161b22] px-1 rounded">?force=true</code> al endpoint</li>
                    <li>Menú de caché: <code className="text-[#d4af37] bg-[#161b22] px-1 rounded">GET /cache/status</code> para ver el estado actual</li>
                </ul>
            </AccordionItem>

            <AccordionItem title="Comparar tickers">
                <p>Clic en el icono <strong className="text-white">⟳</strong> (Compare) en el header para activar el modo comparación. Introduce hasta 3 tickers separados por coma (ej. <code className="text-[#d4af37] bg-[#161b22] px-1 rounded">AAPL, MSFT, NVDA</code>) y compara el veredicto de los agentes en paralelo.</p>
            </AccordionItem>

            <AccordionItem title="Exportar análisis">
                <p>Clic en el botón de descarga (<strong className="text-white">↓</strong>) en el header mientras tienes un análisis activo para guardar el reporte en PDF — incluye el Research Memo institucional.</p>
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
                    {activeTab === "tips" && <TipsSection />}
                </div>

                {/* Footer */}
                <div className="px-5 py-3 border-t border-[#21262d] flex-shrink-0 flex items-center justify-between">
                    <span className="text-[9px] text-gray-700 font-mono">365 Advisers v1.0</span>
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
