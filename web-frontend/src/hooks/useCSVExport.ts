import type { TechnicalAnalysisResult } from "./useTechnicalAnalysis";

export function useCSVExport() {
    const downloadCSV = (dataReady: { name?: string; fundamental_metrics?: Record<string, Record<string, unknown>> } | null, techAnalysis: TechnicalAnalysisResult | null, ticker: string) => {
        if (!dataReady) return;

        try {
            const rows: string[][] = [];
            const timestamp = new Date().toISOString();

            // HEADER
            rows.push(["TICKER", "NAME", "TIMESTAMP"]);
            rows.push([ticker, dataReady.name || ticker, timestamp]);
            rows.push([]);

            // FUNDAMENTAL RATIOS
            rows.push(["FUNDAMENTAL METRICS"]);
            if (dataReady.fundamental_metrics) {
                Object.entries(dataReady.fundamental_metrics).forEach(([category, metrics]) => {
                    rows.push([`-- ${category.toUpperCase()} --`]);
                    Object.entries(metrics).forEach(([key, val]) => {
                        rows.push([key, String(val)]);
                    });
                    rows.push([]);
                });
            }

            // TECHNICAL INDICATORS
            rows.push(["TECHNICAL INDICATORS"]);
            if (techAnalysis && techAnalysis.indicators) {
                Object.entries(techAnalysis.indicators).forEach(([category, data]) => {
                    rows.push([`-- ${category.toUpperCase()} --`]);
                    if (data && typeof data === 'object') {
                        Object.entries(data).forEach(([key, val]) => {
                            let formattedVal = val;
                            if (typeof val === 'number') {
                                formattedVal = val.toFixed(2);
                            } else if (typeof val === 'object') {
                                formattedVal = JSON.stringify(val);
                            }
                            rows.push([key, String(formattedVal)]);
                        });
                    }
                    rows.push([]);
                });
            }

            const csvContent = rows.map((e) => e.join(",")).join("\n");
            const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");

            link.setAttribute("href", url);
            link.setAttribute("download", `${ticker}_analysis_${new Date().getTime()}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

        } catch (e: unknown) {
            console.error("Failed to generate CSV", e);
        }
    };

    return { downloadCSV };
}
