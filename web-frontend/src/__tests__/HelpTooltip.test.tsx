/**
 * HelpTooltip.test.tsx — Unit tests for the IDEA contextual help system
 */
import { HELP, getHelp, type HelpEntry } from "../components/help/helpContent";

// ─── HelpContentRegistry Tests ────────────────────────────────────────────────

describe("HelpContentRegistry", () => {
    test("registry contains at least 30 topics", () => {
        const topics = Object.keys(HELP);
        expect(topics.length).toBeGreaterThanOrEqual(30);
    });

    test("every entry has title and description", () => {
        for (const [key, entry] of Object.entries(HELP)) {
            expect(entry.title).toBeTruthy();
            expect(entry.description).toBeTruthy();
            expect(typeof entry.title).toBe("string");
            expect(typeof entry.description).toBe("string");
        }
    });

    test("all detector entries have extended text", () => {
        const detectorKeys = Object.keys(HELP).filter((k) =>
            k.startsWith("detector_"),
        );
        expect(detectorKeys.length).toBeGreaterThanOrEqual(6);
        for (const key of detectorKeys) {
            expect(HELP[key].extended).toBeTruthy();
            expect(HELP[key].category).toBe("detector");
        }
    });

    test("metric entries have correct category", () => {
        const metricKeys = ["signal_strength", "confidence_score", "alpha_score"];
        for (const key of metricKeys) {
            expect(HELP[key]).toBeDefined();
            expect(HELP[key].category).toBe("metric");
        }
    });

    test("column entries exist for all table headers", () => {
        const colKeys = [
            "col_rank", "col_ticker", "col_strategy",
            "col_confidence", "col_strength", "col_reliability", "col_actions",
        ];
        for (const key of colKeys) {
            expect(HELP[key]).toBeDefined();
            expect(HELP[key].category).toBe("column");
        }
    });

    test("scan control entries exist", () => {
        expect(HELP["scan_universe"]).toBeDefined();
        expect(HELP["scan_watchlist"]).toBeDefined();
        expect(HELP["scan_universe"].category).toBe("control");
    });
});

// ─── getHelp Lookup Tests ─────────────────────────────────────────────────────

describe("getHelp", () => {
    test("returns correct entry for known topic", () => {
        const entry = getHelp("signal_strength");
        expect(entry.title).toBe("Signal Strength");
        expect(entry.description).toContain("intensity");
    });

    test("returns fallback for unknown topic", () => {
        const entry = getHelp("nonexistent_topic_12345");
        expect(entry.title).toBe("Help");
        expect(entry.description).toContain("No additional information");
    });

    test("never throws for any string input", () => {
        expect(() => getHelp("")).not.toThrow();
        expect(() => getHelp("random_key")).not.toThrow();
        expect(() => getHelp("signal_strength")).not.toThrow();
    });

    test("related topics reference valid keys", () => {
        for (const [key, entry] of Object.entries(HELP)) {
            if (entry.related) {
                for (const ref of entry.related) {
                    expect(HELP[ref]).toBeDefined();
                }
            }
        }
    });
});
