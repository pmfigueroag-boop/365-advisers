"use client";

/**
 * MotionWrappers.tsx
 * ──────────────────────────────────────────────────────────────────────────
 * Reusable Framer Motion wrappers for the terminal UI.
 *
 * Provides declarative animation components:
 *  - FadeIn: simple opacity fade
 *  - SlideUp: fade + translate-y reveal
 *  - StaggerGroup: stagger children on mount
 *  - ScaleIn: pop-in for score cards
 *  - PulseOnUpdate: pulse animation when value changes
 */

import { motion, AnimatePresence, type Variants } from "framer-motion";
import { type ReactNode } from "react";

// ── Shared Timing ────────────────────────────────────────────────────────────

const SPRING = { type: "spring", stiffness: 300, damping: 30 } as const;
const EASE_OUT = [0.16, 1, 0.3, 1] as const;

// ── FadeIn ───────────────────────────────────────────────────────────────────

interface FadeInProps {
    children: ReactNode;
    delay?: number;
    duration?: number;
    className?: string;
}

export function FadeIn({ children, delay = 0, duration = 0.4, className }: FadeInProps) {
    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration, delay, ease: EASE_OUT }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

// ── SlideUp ──────────────────────────────────────────────────────────────────

interface SlideUpProps {
    children: ReactNode;
    delay?: number;
    duration?: number;
    distance?: number;
    className?: string;
}

export function SlideUp({
    children,
    delay = 0,
    duration = 0.5,
    distance = 24,
    className,
}: SlideUpProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: distance }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration, delay, ease: EASE_OUT }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

// ── ScaleIn ──────────────────────────────────────────────────────────────────

interface ScaleInProps {
    children: ReactNode;
    delay?: number;
    className?: string;
}

export function ScaleIn({ children, delay = 0, className }: ScaleInProps) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ ...SPRING, delay }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

// ── StaggerGroup ─────────────────────────────────────────────────────────────

const staggerContainer: Variants = {
    hidden: {},
    visible: {
        transition: {
            staggerChildren: 0.08,
            delayChildren: 0.1,
        },
    },
};

const staggerItem: Variants = {
    hidden: { opacity: 0, y: 16 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.4, ease: EASE_OUT },
    },
};

interface StaggerGroupProps {
    children: ReactNode;
    className?: string;
}

export function StaggerGroup({ children, className }: StaggerGroupProps) {
    return (
        <motion.div
            variants={staggerContainer}
            initial="hidden"
            animate="visible"
            className={className}
        >
            {children}
        </motion.div>
    );
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
    return (
        <motion.div variants={staggerItem} className={className}>
            {children}
        </motion.div>
    );
}

// ── PulseOnUpdate ────────────────────────────────────────────────────────────

interface PulseOnUpdateProps {
    children: ReactNode;
    triggerKey: string | number;
    className?: string;
}

export function PulseOnUpdate({ children, triggerKey, className }: PulseOnUpdateProps) {
    return (
        <motion.div
            key={triggerKey}
            initial={{ scale: 1.04, opacity: 0.7 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.3, ease: EASE_OUT }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

// ── Re-export AnimatePresence for convenience ────────────────────────────────

export { AnimatePresence, motion };
