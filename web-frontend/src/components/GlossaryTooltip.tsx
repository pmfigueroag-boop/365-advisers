import { HelpCircle } from "lucide-react";

export const GLOSSARY: Record<string, string> = {
    // Technical
    "RSI": "Relative Strength Index. Mide la magnitud de cambios de precios recientes para evaluar condiciones de sobrecompra (>70) o sobreventa (<30).",
    "MACD": "Moving Average Convergence Divergence. Muestra la relación entre dos medias móviles de precios. Usado para identificar tendencias.",
    "Bollinger Bands": "Bandas de Bollinger. Miden volatilidad. El precio suele rebotar dentro de ellas.",
    "ATR": "Average True Range. Muestra el promedio de volatilidad o movimiento del precio en un periodo.",
    "OBV": "On-Balance Volume. Relaciona el volumen de operaciones con los cambios de precio para identificar tendencias fuertes.",
    "Support": "Soporte. Nivel de precio donde históricamente la acción frena su caída por alto volumen de compras.",
    "Resistance": "Resistencia. Nivel de precio donde la acción frena su subida por alto nivel de ventas.",
    // Fundamental & Ratios
    "P/E": "Price to Earnings Ratio. Relación Precio-Beneficio. Indica cuánto paga el mercado por cada $1 de ganancia de la empresa.",
    "PEG": "Price/Earnings to Growth. Valora la acción basada en sus ganancias y el crecimiento esperado de estas.",
    "EV/EBITDA": "Enterprise Value / EBITDA. Valora el negocio entero tomando en cuenta deuda y caja, ignorando impuestos e intereses.",
    "ROE": "Return on Equity. Porcentaje de beneficio generado sobre el capital de los accionistas.",
    "ROA": "Return on Assets. Indica qué tan eficiente es la gerencia en usar sus activos para generar ganancias.",
    "ROIC": "Return on Invested Capital. Retorno sobre todo el capital invertido (deuda y equity).",
    "Gross Margin": "Margen Bruto. Porcentaje de dinero que la empresa retiene tras deducir los costos directos de hacer el producto.",
    "Operating Margin": "Margen Operativo. Beneficio de operaciones core, excluyendo deuda e impuestos.",
    "Net Margin": "Margen Neto. Porcentaje de beneficio definitivo tras descontar absolutamente todos los gastos.",
    "Current Ratio": "Ratio de Liquidez. Mide la capacidad de pagar obligaciones a corto plazo (Activos / Pasivos corrientes).",
    "Quick Ratio": "Prueba Ácida. Similar al Current Ratio, pero excluye inventario (activos más líquidos).",
    "Debt/Equity": "Ratio Deuda/Capital. Nivel de apalancamiento de la empresa comparado con su capital propio.",
    "Free Cash Flow": "Flujo de Caja Libre. Efectivo disponible tras pagar mantenimiento de operaciones y activos.",
    "Beta": "Mide el riesgo sistemático de la acción comparado al mercado. Beta > 1 es más volátil que el mercado.",
    "Altman Z-Score": "Modelo predictivo de probabilidad de quiebra corporativa en los próximos 2 años.",
    "Piotroski F-Score": "Calificación 0-9 para evaluar la fortaleza financiera y operativa de la firma.",
};

export default function GlossaryTooltip({ term, label }: { term: string, label?: string }) {
    // Normalize the term to try to find a match
    const k = Object.keys(GLOSSARY).find((key) => term.toUpperCase().includes(key.toUpperCase()));
    const definition = k ? GLOSSARY[k] : null;

    if (!definition) {
        return <span>{label || term}</span>;
    }

    return (
        <div className="group relative inline-flex items-center gap-1 cursor-help">
            <span className="border-b border-dashed border-gray-600 pb-[1px]">{label || term}</span>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-[#1c2128] border border-[#30363d] rounded shadow-xl text-[10px] text-gray-300 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-50 normal-case tracking-normal">
                <div className="font-bold text-[#d4af37] mb-0.5">{k}</div>
                {definition}
            </div>
        </div>
    );
}
