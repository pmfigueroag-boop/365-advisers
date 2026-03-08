"use client";

/**
 * AIAssistantView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Strategy AI Assistant — Research chat with Knowledge Graph integration.
 * Allows generating, analyzing, interpreting backtests, and suggesting portfolios.
 */

import { useState, useRef, useEffect } from "react";
import {
    Send,
    Sparkles,
    FlaskConical,
    Brain,
    BarChart3,
    Briefcase,
    RefreshCw,
    Lightbulb,
    Microscope,
    TrendingUp,
    Zap,
    Clock,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────

interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
}

interface QuickAction {
    icon: React.ReactNode;
    label: string;
    prompt: string;
}

const QUICK_ACTIONS: QuickAction[] = [
    {
        icon: <Sparkles size={14} />,
        label: "Generate Strategy",
        prompt: "Generate a momentum + quality multi-factor strategy with regime-aware position sizing",
    },
    {
        icon: <Microscope size={14} />,
        label: "Analyze Signals",
        prompt: "Analyze which alpha signals have the highest IC and suggest a signal composition",
    },
    {
        icon: <BarChart3 size={14} />,
        label: "Interpret Backtest",
        prompt: "Help me interpret my latest backtest results and identify areas for improvement",
    },
    {
        icon: <Briefcase size={14} />,
        label: "Suggest Portfolio",
        prompt: "Suggest an optimal portfolio allocation across my existing strategies",
    },
];

// ─── Sample conversation ──────────────────────────────────────────────────

const INITIAL_MESSAGES: ChatMessage[] = [
    {
        id: "welcome",
        role: "assistant",
        content: "Welcome to the 365 Advisers Research Assistant. I can help you generate strategies, analyze signals, interpret backtests, and suggest portfolio allocations.\n\nI have access to your Knowledge Graph, Strategy Lab, and Experiment Tracking data. How can I help you today?",
        timestamp: new Date(),
    },
];

export default function AIAssistantView() {
    const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
    const [input, setInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const handleSend = () => {
        if (!input.trim() || isProcessing) return;
        const userMsg: ChatMessage = {
            id: `user-${Date.now()}`,
            role: "user",
            content: input,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setIsProcessing(true);

        // Simulated AI response
        setTimeout(() => {
            const assistantMsg: ChatMessage = {
                id: `ai-${Date.now()}`,
                role: "assistant",
                content: generateMockResponse(userMsg.content),
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, assistantMsg]);
            setIsProcessing(false);
        }, 1500);
    };

    const handleQuickAction = (action: QuickAction) => {
        setInput(action.prompt);
    };

    return (
        <div className="flex flex-col h-full" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-[#30363d]/50">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#d4af37]/20 to-purple-500/20 flex items-center justify-center">
                        <Sparkles size={16} className="text-[#d4af37]" />
                    </div>
                    <div>
                        <h2 className="text-sm font-black uppercase tracking-widest text-gray-300">
                            Research Assistant
                        </h2>
                        <p className="text-[9px] text-gray-600 font-mono">
                            Knowledge Graph · Strategy Lab · Experiment Tracking
                        </p>
                    </div>
                </div>
                <button
                    onClick={() => setMessages(INITIAL_MESSAGES)}
                    className="p-2 rounded-lg text-gray-600 hover:text-[#d4af37] hover:bg-[#d4af37]/10 transition-all"
                    title="New conversation"
                >
                    <RefreshCw size={14} />
                </button>
            </div>

            {/* Quick Actions */}
            <div className="flex gap-2 py-3 overflow-x-auto">
                {QUICK_ACTIONS.map((action, i) => (
                    <button
                        key={i}
                        onClick={() => handleQuickAction(action)}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#161b22] border border-[#30363d] text-[10px] font-bold text-gray-400 hover:border-[#d4af37]/30 hover:text-[#d4af37] transition-all whitespace-nowrap"
                    >
                        {action.icon}
                        {action.label}
                    </button>
                ))}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto space-y-4 py-3">
                {messages.map((msg) => (
                    <div
                        key={msg.id}
                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                        <div
                            className={`max-w-[85%] rounded-xl px-4 py-3 ${msg.role === "user"
                                    ? "bg-[#d4af37]/10 border border-[#d4af37]/20 text-gray-200"
                                    : "bg-[#161b22] border border-[#30363d] text-gray-300"
                                }`}
                        >
                            {msg.role === "assistant" && (
                                <div className="flex items-center gap-2 mb-2">
                                    <Sparkles size={10} className="text-[#d4af37]" />
                                    <span className="text-[9px] font-black uppercase tracking-widest text-[#d4af37]">
                                        AI Research Assistant
                                    </span>
                                </div>
                            )}
                            <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{
                                fontFamily: msg.role === "assistant" ? "var(--font-insight)" : undefined,
                            }}>
                                {msg.content}
                            </p>
                            <p className="text-[8px] text-gray-700 mt-2 font-mono">
                                {msg.timestamp.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
                            </p>
                        </div>
                    </div>
                ))}

                {isProcessing && (
                    <div className="flex justify-start">
                        <div className="bg-[#161b22] border border-[#30363d] rounded-xl px-4 py-3">
                            <div className="flex items-center gap-2">
                                <Sparkles size={10} className="text-[#d4af37] animate-pulse" />
                                <span className="text-[9px] font-bold text-gray-500">Analyzing...</span>
                            </div>
                            <div className="flex gap-1 mt-2">
                                <div className="w-1.5 h-1.5 rounded-full bg-[#d4af37]/40 animate-bounce" style={{ animationDelay: "0ms" }} />
                                <div className="w-1.5 h-1.5 rounded-full bg-[#d4af37]/40 animate-bounce" style={{ animationDelay: "200ms" }} />
                                <div className="w-1.5 h-1.5 rounded-full bg-[#d4af37]/40 animate-bounce" style={{ animationDelay: "400ms" }} />
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="pt-3 border-t border-[#30363d]/50">
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSend()}
                        placeholder="Ask about strategies, signals, backtests, portfolios..."
                        className="flex-1 bg-[#161b22] border border-[#30363d] px-4 py-2.5 rounded-xl text-xs focus:outline-none focus:border-[#d4af37]/40 focus:ring-2 focus:ring-[#d4af37]/10 transition-all"
                        disabled={isProcessing}
                    />
                    <button
                        onClick={handleSend}
                        disabled={!input.trim() || isProcessing}
                        className="bg-gradient-to-r from-[#d4af37] to-[#e8c84a] text-black px-4 py-2.5 rounded-xl font-bold text-xs hover:brightness-110 transition-all disabled:opacity-40 flex items-center gap-2"
                    >
                        <Send size={12} />
                    </button>
                </div>
                <p className="text-[8px] text-gray-700 mt-1.5 font-mono text-center">
                    Connected to Knowledge Graph · Strategy Lab · Experiment Tracking
                </p>
            </div>
        </div>
    );
}

// ─── Mock Response Generator ──────────────────────────────────────────────

function generateMockResponse(userInput: string): string {
    const lower = userInput.toLowerCase();

    if (lower.includes("generate") || lower.includes("create") || lower.includes("strategy")) {
        return `Based on your Knowledge Graph analysis, I recommend a **Multi-Factor Momentum Quality** strategy:

**Signal Composition:**
• Required: Momentum (IC: 0.08, p<0.01) + Quality (IC: 0.06, p<0.02)
• Optional boost: Event signals for catalyst timing

**Key Parameters:**
• CASE Score threshold: ≥ 75
• Universe: S&P 500 (min market cap $10B)
• Sizing: Volatility Parity
• Max positions: 15

**Regime-Aware Rules:**
• Bull: Full exposure (momentum amplified)
• Bear: No new entries, trailing stop 12%
• Volatile: Reduce to 50%, tighten stops

This configuration shows a historical Sharpe of ~2.1 with 82% win rate. Shall I create this strategy in the Lab?`;
    }

    if (lower.includes("signal") || lower.includes("analyze") || lower.includes("alpha")) {
        return `**Alpha Signal Analysis Summary:**

Top signals by Information Coefficient (IC):
1. **Price Momentum (12m)**: IC = 0.08 (p < 0.01) — Strong, consistent
2. **Quality Score**: IC = 0.06 (p < 0.02) — Stable across regimes
3. **Revenue Growth**: IC = 0.05 (p < 0.03) — Recent improvement
4. **FCF Yield**: IC = 0.04 (p < 0.05) — Better in bear regimes
5. **Institutional Flow**: IC = 0.03 (p < 0.08) — Noisy but additive

**Redundancy Analysis:**
• Momentum + Quality: Low correlation (ρ = 0.15) — excellent pair
• Value + Quality: Moderate correlation (ρ = 0.42) — some overlap
• Recommendation: Prioritize Momentum + Quality + Event for maximum diversification`;
    }

    if (lower.includes("backtest") || lower.includes("interpret") || lower.includes("result")) {
        return `**Backtest Interpretation:**

Your latest backtest shows promising results with some areas for attention:

✅ **Strengths:**
• Sharpe Ratio: 1.85 (above institutional threshold of 1.5)
• Win Rate: 74% with positive profit factor (2.3x)
• Regime handling: Strategy correctly reduced exposure during 2022 drawdown

⚠️ **Areas for Review:**
• Max Drawdown: -16.2% (slightly above the -15% target)
• Average holding period: 45 days (shorter than configured 60-day target)
• Concentration risk: Top 3 positions = 28% of portfolio

**Recommendations:**
1. Tighten trailing stop from 15% to 12% to reduce max drawdown
2. Add a sector concentration cap of 25%
3. Consider adding a volatility filter for position entry timing`;
    }

    if (lower.includes("portfolio") || lower.includes("allocat") || lower.includes("suggest")) {
        return `**Portfolio Allocation Recommendation:**

Based on your 4 backtested strategies, here's an optimal allocation:

| Strategy | Allocation | Role | Sharpe |
|:---|:---|:---|:---|
| Momentum Quality v2 | 35% | Core Alpha | 2.1 |
| Value Contrarian v3 | 25% | Diversifier | 1.8 |
| Low Vol Yield | 25% | Defensive | 1.5 |
| Event Catalyst | 15% | Satellite | 1.4 |

**Expected Portfolio Metrics:**
• Portfolio Sharpe: 2.4 (diversification benefit: +0.3)
• Expected Return: 19.5% ann.
• Expected Max DD: -10.2%
• Inter-strategy correlation: 0.18 avg

The low correlation between Momentum and Value strategies provides natural hedging.`;
    }

    return `I understand your question about "${userInput.substring(0, 80)}..."

Let me analyze this using the available data from your Knowledge Graph and Strategy Lab. 

Based on the current system state:
• **47 active signals** across 8 categories
• **6 strategies** in the registry
• **Market regime**: Bull (low volatility)

Could you provide more context about what specific aspect you'd like me to focus on? I can help with:
1. 📊 Signal analysis and IC evaluation
2. 🧪 Strategy generation and optimization  
3. 📈 Backtest interpretation
4. 💼 Portfolio construction`;
}
