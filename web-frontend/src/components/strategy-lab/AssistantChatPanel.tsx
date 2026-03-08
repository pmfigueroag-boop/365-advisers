"use client";

/**
 * AssistantChatPanel.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Interactive AI chat component for the Strategy Lab Intelligence Panel.
 * Connects to POST /strategy-lab/assistant/chat with session management.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import {
    Send,
    Loader2,
    Bot,
    User,
    Lightbulb,
    Trash2,
    AlertCircle,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChatMessage {
    role: "user" | "assistant";
    content: string;
    recommendations?: Array<{ action: string; rationale: string }>;
    intent?: string;
    tool_calls?: string[];
    timestamp: string;
}

interface AssistantChatPanelProps {
    sessionId?: string;
    context?: Record<string, unknown>;
}

export default function AssistantChatPanel({
    sessionId = "lab-default",
    context,
}: AssistantChatPanelProps) {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const sendMessage = useCallback(async () => {
        const trimmed = input.trim();
        if (!trimmed || loading) return;

        const userMsg: ChatMessage = {
            role: "user",
            content: trimmed,
            timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);
        setError(null);

        try {
            const res = await fetch(`${API}/strategy-lab/assistant/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: trimmed,
                    session_id: sessionId,
                    context: context ?? null,
                }),
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const data = await res.json();

            // Build assistant response from structured data
            const contextText = data.context || "";
            const recommendations = data.recommendations || [];
            const intent = data.intent || "general";
            const toolCalls = data.tool_calls || [];

            // Use assembled context as the message body
            const assistantContent = contextText || "I processed your request but found no relevant data.";

            const assistantMsg: ChatMessage = {
                role: "assistant",
                content: assistantContent,
                recommendations,
                intent,
                tool_calls: toolCalls,
                timestamp: new Date().toISOString(),
            };

            setMessages((prev) => [...prev, assistantMsg]);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to send message";
            setError(message);
        } finally {
            setLoading(false);
            inputRef.current?.focus();
        }
    }, [input, loading, sessionId, context]);

    const clearChat = useCallback(async () => {
        setMessages([]);
        setError(null);
        try {
            await fetch(`${API}/strategy-lab/assistant/sessions/${sessionId}`, {
                method: "DELETE",
            });
        } catch {
            // Silent — clearing local is enough
        }
    }, [sessionId]);

    return (
        <div className="lab-chat">
            {/* Messages area */}
            <div className="lab-chat-messages">
                {messages.length === 0 && (
                    <div className="lab-chat-empty">
                        <Bot size={20} className="text-[#d4af37]/40" />
                        <p>Ask me about strategies, signals, backtests, or portfolio construction.</p>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} className={`lab-chat-msg ${msg.role === "user" ? "lab-chat-msg-user" : "lab-chat-msg-assistant"}`}>
                        <div className="lab-chat-msg-icon">
                            {msg.role === "user" ? <User size={10} /> : <Bot size={10} />}
                        </div>
                        <div className="lab-chat-msg-body">
                            {msg.role === "assistant" && msg.intent && (
                                <div className="lab-chat-meta">
                                    <span className="lab-chat-intent">{msg.intent}</span>
                                    {msg.tool_calls && msg.tool_calls.length > 0 && (
                                        <span className="lab-chat-tools">{msg.tool_calls.length} tools</span>
                                    )}
                                </div>
                            )}
                            <div className="lab-chat-msg-text">
                                {msg.content.split("\n").map((line, j) => (
                                    <p key={j}>{line || "\u00A0"}</p>
                                ))}
                            </div>
                            {/* Recommendations */}
                            {msg.recommendations && msg.recommendations.length > 0 && (
                                <div className="lab-chat-recs">
                                    {msg.recommendations.map((rec, j) => (
                                        <div key={j} className="lab-chat-rec">
                                            <Lightbulb size={10} className="text-[#d4af37] flex-shrink-0 mt-0.5" />
                                            <div>
                                                <span className="lab-chat-rec-action">{rec.action}</span>
                                                <span className="lab-chat-rec-rationale">{rec.rationale}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                ))}

                {loading && (
                    <div className="lab-chat-msg lab-chat-msg-assistant">
                        <div className="lab-chat-msg-icon">
                            <Bot size={10} />
                        </div>
                        <div className="lab-chat-msg-body">
                            <div className="lab-chat-loading">
                                <Loader2 size={12} className="animate-spin text-[#d4af37]" />
                                <span>Analyzing...</span>
                            </div>
                        </div>
                    </div>
                )}

                {error && (
                    <div className="lab-chat-error">
                        <AlertCircle size={10} />
                        <span>{error}</span>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div className="lab-chat-input-area">
                <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                    placeholder="Ask about strategies, signals..."
                    className="lab-chat-input"
                    disabled={loading}
                />
                <button
                    onClick={sendMessage}
                    disabled={!input.trim() || loading}
                    className="lab-chat-send"
                    title="Send"
                >
                    <Send size={12} />
                </button>
                {messages.length > 0 && (
                    <button
                        onClick={clearChat}
                        className="lab-chat-clear"
                        title="Clear chat"
                    >
                        <Trash2 size={11} />
                    </button>
                )}
            </div>
        </div>
    );
}
