"use client";

import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    BarChart,
    Bar,
    Legend,
} from "recharts";

interface PriceData {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
}

interface CashFlowData {
    year: string;
    fcf: number;
    revenue: number;
}

const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-[#161b22] border border-[#30363d] p-3 rounded-lg shadow-xl">
                <p className="text-gray-400 text-xs mb-1">{label}</p>
                {payload.map((entry: any, index: number) => (
                    <p key={index} style={{ color: entry.color }} className="text-sm font-bold">
                        {entry.name}: {new Intl.NumberFormat('en-US', {
                            style: 'currency',
                            currency: 'USD',
                            notation: 'compact',
                        }).format(entry.value)}
                    </p>
                ))}
            </div>
        );
    }
    return null;
};

export function PriceChart({ data }: { data: PriceData[] }) {
    return (
        <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data}>
                    <defs>
                        <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#d4af37" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#d4af37" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
                    <XAxis
                        dataKey="time"
                        stroke="#8b949e"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        minTickGap={30}
                    />
                    <YAxis
                        stroke="#8b949e"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(value) => `$${value}`}
                        domain={['auto', 'auto']}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Area
                        type="monotone"
                        dataKey="close"
                        name="Precio"
                        stroke="#d4af37"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#colorPrice)"
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
}

export function CashFlowChart({ data }: { data: CashFlowData[] }) {
    return (
        <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
                    <XAxis
                        dataKey="year"
                        stroke="#8b949e"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                    />
                    <YAxis
                        stroke="#8b949e"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(value) => `$${(value / 1e9).toFixed(0)}B`}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ paddingTop: '20px' }} />
                    <Bar dataKey="revenue" name="Ingresos" fill="#30363d" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="fcf" name="Free Cash Flow" fill="#d4af37" radius={[4, 4, 0, 0]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
