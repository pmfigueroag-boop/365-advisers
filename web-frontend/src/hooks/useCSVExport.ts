export function useCSVExport() {
    const downloadCSV = (dataReady: any, techSummary: any, ticker: string) => {
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
                Object.entries(dataReady.fundamental_metrics).forEach(([category, metrics]: [string, any]) => {
                    rows.push([`-- ${category.toUpperCase()} --`]);
                    Object.entries(metrics).forEach(([key, val]: [string, any]) => {
                        rows.push([key, String(val)]);
                    });
                    rows.push([]);
                });
            }

            // TECHNICAL INDICATORS
            rows.push(["TECHNICAL INDICATORS"]);
            if (techSummary && techSummary.indicators) {
                Object.entries(techSummary.indicators).forEach(([category, data]: [string, any]) => {
                    rows.push([`-- ${category.toUpperCase()} --`]);
                    if (data.values) {
                        Object.entries(data.values).forEach(([key, val]: [string, any]) => {
                            let formattedVal = val;
                            if (typeof val === 'number') {
                                formattedVal = val.toFixed(2);
                            }
                            rows.push([key, String(formattedVal)]);
                        });
                    }
                    if (data.signals) {
                        Object.entries(data.signals).forEach(([key, val]: [string, any]) => {
                            rows.push([`${key} Signal`, String(val)]);
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

        } catch (e) {
            console.error("Failed to generate CSV", e);
        }
    };

    return { downloadCSV };
}
