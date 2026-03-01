"use client";

import React, { useEffect, useRef } from 'react';

interface TradingViewChartProps {
    symbol: string;
}

export default function TradingViewChart({ symbol }: TradingViewChartProps) {
    const container = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!container.current) return;

        // Clean up previous instances
        container.current.innerHTML = '<div id="tradingview_advanced_chart" style="height: 500px; width: 100%;"></div>';

        const script = document.createElement("script");
        script.src = "https://s3.tradingview.com/tv.js";
        script.type = "text/javascript";
        script.async = true;
        script.onload = () => {
            if ((window as any).TradingView) {
                new (window as any).TradingView.widget({
                    "width": "100%",
                    "height": 500,
                    "symbol": symbol.includes(":") ? symbol : `NASDAQ:${symbol}`,
                    "interval": "D",
                    "timezone": "Etc/UTC",
                    "theme": "dark",
                    "style": "1",
                    "locale": "en",
                    "toolbar_bg": "#131722",
                    "enable_publishing": false,
                    "allow_symbol_change": true,
                    "container_id": "tradingview_advanced_chart"
                });
            }
        };

        container.current.appendChild(script);
    }, [symbol]);

    return (
        <div className="tradingview-widget-container" ref={container} style={{ height: "500px", width: "100%" }}>
            <div id="tradingview_advanced_chart" style={{ height: "500px", width: "100%" }}></div>
        </div>
    );
}
