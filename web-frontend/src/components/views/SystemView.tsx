"use client";

/**
 * SystemView.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * System Intelligence — comprehensive view combining QVF ValidationDashboard
 * with Concept Drift Alerts and Recalibration History.
 */

import { Brain } from "lucide-react";
import ValidationDashboard from "@/components/validation/ValidationDashboard";
import DriftAlerts from "@/components/system/DriftAlerts";
import RecalibrationLog from "@/components/system/RecalibrationLog";
import ErrorBoundary from "@/components/ErrorBoundary";

export default function SystemView() {
    return (
        <div className="space-y-6" style={{ animation: "fadeSlideIn 0.3s ease both" }}>
            {/* Header */}
            <div>
                <div className="flex items-center gap-2 mb-1">
                    <Brain size={16} className="text-purple-400" />
                    <h2 className="text-base font-black uppercase tracking-widest text-gray-300">
                        System Intelligence
                    </h2>
                </div>
                <p className="text-xs text-gray-600">
                    Monitor signal health, concept drift, detector accuracy, and model calibration.
                </p>
            </div>

            <div className="separator-gold" />

            {/* Drift Alerts + Recalibration side by side on large screens */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <ErrorBoundary>
                    <DriftAlerts />
                </ErrorBoundary>
                <ErrorBoundary>
                    <RecalibrationLog />
                </ErrorBoundary>
            </div>

            {/* Full QVF Dashboard */}
            <ErrorBoundary>
                <ValidationDashboard />
            </ErrorBoundary>
        </div>
    );
}
