"use client";

/**
 * RecalibrationLog.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Timeline of model recalibration events for System Intelligence.
 * Shows weight adjustments, signal additions/removals, and parameter updates.
 */

import { Clock, Wrench, Plus, Minus, RefreshCw } from "lucide-react";

interface RecalibrationEvent {
    date: string;
    description: string;
    type: "update" | "add" | "remove" | "recalibrate";
}

// Static placeholder events (will connect to backend when API exists)
const SAMPLE_EVENTS: RecalibrationEvent[] = [
    { date: "2026-03-06", description: "Decay params updated · Half-life: 14→12 days", type: "update" },
    { date: "2026-03-05", description: "Expanded Alpha Signal Library to 50 signals across 8 categories", type: "add" },
    { date: "2026-03-04", description: "Integrated CASE Engine into scoring pipeline", type: "recalibrate" },
    { date: "2026-03-03", description: "Added Alpha Decay & Signal Half-Life Model", type: "add" },
    { date: "2026-03-02", description: "Institutional Opportunity Score (12 factors) deployed", type: "recalibrate" },
];

export default function RecalibrationLog() {
    const events = SAMPLE_EVENTS;

    const typeConfig = {
        update: { icon: <Wrench size={10} />, color: "text-yellow-400", bg: "bg-yellow-500/15" },
        add: { icon: <Plus size={10} />, color: "text-green-400", bg: "bg-green-500/15" },
        remove: { icon: <Minus size={10} />, color: "text-red-400", bg: "bg-red-500/15" },
        recalibrate: { icon: <RefreshCw size={10} />, color: "text-blue-400", bg: "bg-blue-500/15" },
    };

    return (
        <div className="glass-card border-[#30363d] p-5">
            <div className="flex items-center gap-2 mb-4">
                <Clock size={13} className="text-purple-400" />
                <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">
                    Model Recalibration History
                </span>
            </div>

            <div className="relative">
                {/* Vertical timeline line */}
                <div className="absolute left-[13px] top-2 bottom-2 w-px bg-[#30363d]" />

                <div className="space-y-4">
                    {events.map((event, idx) => {
                        const cfg = typeConfig[event.type];
                        return (
                            <div key={idx} className="flex items-start gap-3 pl-1">
                                {/* Timeline dot */}
                                <div className={`w-[26px] h-[26px] rounded-full flex items-center justify-center flex-shrink-0 z-10 ${cfg.bg}`}>
                                    <span className={cfg.color}>{cfg.icon}</span>
                                </div>

                                {/* Content */}
                                <div className="flex-1 min-w-0 pt-0.5">
                                    <p className="text-[9px] font-mono text-gray-600 mb-0.5">{event.date}</p>
                                    <p className="text-[11px] text-gray-300 leading-relaxed">{event.description}</p>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
