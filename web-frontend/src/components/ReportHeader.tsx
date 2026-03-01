"use client";

/**
 * ReportHeader — only visible when printing (display:none on screen).
 * Shows a professional cover header: logo, ticker, company, generated timestamp.
 */
export default function ReportHeader({
    ticker,
    name,
    price,
}: {
    ticker: string;
    name?: string;
    price?: number;
}) {
    const now = new Date();
    const dateStr = now.toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
    });
    const timeStr = now.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZoneName: "short",
    });
    const reportId = `${ticker}-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}-${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}`;

    return (
        <div
            className="print-only"
            style={{
                display: "none",
                borderBottom: "2px solid #d4af37",
                paddingBottom: "12pt",
                marginBottom: "16pt",
            }}
        >
            {/* Banner */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8pt", marginBottom: "4pt" }}>
                        <div
                            style={{
                                background: "#d4af37",
                                color: "#000",
                                fontWeight: 900,
                                fontSize: "11pt",
                                padding: "3pt 7pt",
                                borderRadius: "4pt",
                                letterSpacing: "0.04em",
                            }}
                        >
                            365
                        </div>
                        <span
                            style={{
                                fontWeight: 900,
                                fontSize: "16pt",
                                letterSpacing: "-0.03em",
                                color: "#d4af37",
                            }}
                        >
                            ADVISERS
                        </span>
                    </div>
                    <p style={{ fontSize: "8pt", color: "#6e7681", margin: 0 }}>
                        Investment Committee Report — Confidential
                    </p>
                </div>

                <div style={{ textAlign: "right", fontSize: "7.5pt", color: "#6e7681", lineHeight: 1.6 }}>
                    <div>
                        <strong style={{ color: "#e6edf3", fontSize: "9pt" }}>{ticker}</strong>
                        {name && name !== ticker && (
                            <span style={{ marginLeft: "4pt", color: "#8b949e" }}>— {name}</span>
                        )}
                    </div>
                    {price && (
                        <div>
                            Price: <strong style={{ color: "#d4af37" }}>${price.toFixed(2)}</strong>
                        </div>
                    )}
                    <div>
                        Generated: {dateStr} · {timeStr}
                    </div>
                    <div style={{ fontFamily: "monospace", fontSize: "7pt", color: "#484f58", marginTop: "2pt" }}>
                        Report ID: {reportId}
                    </div>
                </div>
            </div>
        </div>
    );
}
