"use client";

import React, { Component, ReactNode } from "react";

interface ErrorBoundaryProps {
    children: ReactNode;
    fallbackMessage?: string;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

/**
 * React Error Boundary — catches rendering errors in child components
 * and displays a recovery UI instead of crashing the entire page.
 * Fixes audit finding #17.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
        console.error("[ErrorBoundary] Caught rendering error:", error, errorInfo);
    }

    render(): ReactNode {
        if (this.state.hasError) {
            return (
                <div className="glass-card p-6 text-center border border-red-500/30 bg-red-500/5 my-4">
                    <p className="text-sm font-bold text-red-400 mb-2">
                        {this.props.fallbackMessage || "Something went wrong rendering this component."}
                    </p>
                    <p className="text-[10px] text-gray-500 mb-4 font-mono">
                        {this.state.error?.message}
                    </p>
                    <button
                        onClick={() => this.setState({ hasError: false, error: null })}
                        className="text-xs bg-red-500/20 hover:bg-red-500/30 text-red-300 px-4 py-1.5 rounded transition-colors"
                    >
                        Try Again
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
