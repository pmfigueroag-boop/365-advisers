"use client";

import { useState, useEffect, useCallback } from "react";
import { ShieldCheck, LineChart, Star, ChevronRight, X, Zap } from "lucide-react";

const ONBOARDING_KEY = "365_onboarding_done";

interface Step {
    icon: React.ReactNode;
    title: string;
    subtitle: string;
    body: string;
    highlight?: string;
}

const STEPS: Step[] = [
    {
        icon: <Zap size={28} className="text-[#d4af37]" />,
        title: "Welcome to 365 Advisers",
        subtitle: "Step 1 of 3",
        body: "Type any stock ticker (e.g. NVDA, AAPL) in the search bar and click Analyze. The Investment Committee will run fundamental, technical, and combined analysis simultaneously.",
        highlight: "Institutional-grade analysis in under 60 seconds.",
    },
    {
        icon: <ShieldCheck size={28} className="text-[#d4af37]" />,
        title: "Reading the Committee Verdict",
        subtitle: "Step 2 of 3",
        body: "The Investment Committee Verdict synthesizes 4 institutional frameworks into a single score (0–10), a signal (BUY · HOLD · SELL), and an actionable narrative — the same process used by professional investment committees.",
        highlight: "Score ≥ 7 = Bullish · Score 5–6 = Neutral · Score ≤ 4 = Bearish",
    },
    {
        icon: <Star size={28} className="text-[#d4af37]" />,
        title: "Build Your Coverage List",
        subtitle: "Step 3 of 3",
        body: "Click the ★ button after any analysis to add the asset to your watchlist. Your Coverage List tracks signals, scores, and changes over time — so you can re-run analysis with one click.",
        highlight: "Pro tip: re-analyze regularly to track score deltas.",
    },
];

interface OnboardingOverlayProps {
    onDone: () => void;
}

export default function OnboardingOverlay({ onDone }: OnboardingOverlayProps) {
    const [step, setStep] = useState(0);
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        // Trigger entrance animation after mount
        const t = setTimeout(() => setVisible(true), 50);
        return () => clearTimeout(t);
    }, []);

    const dismiss = useCallback(() => {
        try { localStorage.setItem(ONBOARDING_KEY, "1"); } catch { /* ignore */ }
        setVisible(false);
        setTimeout(onDone, 350); // wait for exit animation
    }, [onDone]);

    useEffect(() => {
        const handler = (e: KeyboardEvent) => { if (e.key === "Escape") dismiss(); };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [dismiss]);

    const isLast = step === STEPS.length - 1;
    const current = STEPS[step];

    return (
        <div
            className="fixed inset-0 z-[100] flex items-center justify-center p-4"
            style={{
                backgroundColor: `rgba(0,0,0,${visible ? 0.7 : 0})`,
                backdropFilter: visible ? "blur(6px)" : "blur(0px)",
                transition: "background-color 0.35s ease, backdrop-filter 0.35s ease",
            }}
            onClick={(e) => e.target === e.currentTarget && dismiss()}
        >
            <div
                className="relative bg-[#0d1117] border border-[#30363d] rounded-2xl p-8 max-w-md w-full shadow-2xl"
                style={{
                    transform: visible ? "translateY(0) scale(1)" : "translateY(24px) scale(0.95)",
                    opacity: visible ? 1 : 0,
                    transition: "transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.35s ease",
                }}
            >
                {/* Close */}
                <button
                    onClick={dismiss}
                    className="absolute top-4 right-4 text-gray-600 hover:text-gray-400 transition-colors"
                    title="Skip onboarding"
                >
                    <X size={16} />
                </button>

                {/* Step indicator dots */}
                <div className="flex gap-1.5 mb-6">
                    {STEPS.map((_, i) => (
                        <div
                            key={i}
                            className={`h-1 rounded-full transition-all duration-300 ${i === step ? "w-6 bg-[#d4af37]" : "w-2 bg-[#30363d]"
                                }`}
                        />
                    ))}
                </div>

                {/* Icon */}
                <div className="w-14 h-14 bg-[#161b22] border border-[#d4af37]/20 rounded-2xl flex items-center justify-center mb-5">
                    {current.icon}
                </div>

                {/* Content */}
                <p className="text-[9px] font-mono text-gray-600 uppercase tracking-widest mb-1">
                    {current.subtitle}
                </p>
                <h2 className="text-lg font-black text-white mb-3">{current.title}</h2>
                <p className="text-sm text-gray-400 leading-relaxed mb-4">{current.body}</p>

                {current.highlight && (
                    <div className="bg-[#d4af37]/8 border border-[#d4af37]/20 rounded-lg px-4 py-2.5 mb-5">
                        <p className="text-[10px] font-mono text-[#d4af37]/80">{current.highlight}</p>
                    </div>
                )}

                {/* Actions */}
                <div className="flex items-center justify-between">
                    <button
                        onClick={dismiss}
                        className="text-[10px] text-gray-600 hover:text-gray-400 transition-colors uppercase tracking-widest font-bold"
                    >
                        Skip
                    </button>

                    <button
                        onClick={() => isLast ? dismiss() : setStep(s => s + 1)}
                        className="flex items-center gap-2 bg-[#d4af37] text-black text-sm font-black px-5 py-2 rounded-xl hover:bg-[#f9e29c] transition-all"
                    >
                        {isLast ? "Get Started" : "Next"}
                        {!isLast && <ChevronRight size={14} />}
                    </button>
                </div>
            </div>
        </div>
    );
}

/** Hook to manage onboarding visibility — server-safe */
export function useOnboarding() {
    const [showOnboarding, setShowOnboarding] = useState(false);

    useEffect(() => {
        if (typeof window === "undefined") return;
        const done = localStorage.getItem(ONBOARDING_KEY);
        if (!done) setShowOnboarding(true);
    }, []);

    const dismiss = useCallback(() => setShowOnboarding(false), []);
    return { showOnboarding, dismiss };
}
