"use client";

/**
 * /help — Standalone Help Center page.
 * Opens in a new browser window via window.open() from the main terminal.
 * Reuses the HelpPanel component in "standalone" (full-page) mode.
 */

import HelpPanel from "@/components/HelpPanel";

export default function HelpPage() {
    return (
        <HelpPanel
            open={true}
            onClose={() => window.close()}
            standalone
        />
    );
}
