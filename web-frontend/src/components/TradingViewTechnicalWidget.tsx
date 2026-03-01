"use client";

import React, { useEffect, useRef } from 'react';

interface TradingViewTechnicalWidgetProps {
    symbol: string;
}

export default function TradingViewTechnicalWidget({ symbol }: TradingViewTechnicalWidgetProps) {
    const container = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!container.current) return;
        container.current.innerHTML = '';

        const script = document.createElement("script");
        script.src = "https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js";
        script.type = "text/javascript";
        script.async = true;

        const config = {
            "interval": "1D",
            "width": "100%",
            "isTransparent": false,
            "height": 400,
            "symbol": symbol.includes(":") ? symbol : `NASDAQ:${symbol}`,
            "showIntervalTabs": true,
            "displayMode": "single",
            "locale": "en",
            "colorTheme": "dark"
        };

        script.innerHTML = JSON.stringify(config);
        container.current.appendChild(script);
    }, [symbol]);

    return (
        <div className="tradingview-widget-container" ref={container} style={{ minHeight: "400px", width: "100%" }}>
            <div className="tradingview-widget-container__widget"></div>
        </div>
    );
}
