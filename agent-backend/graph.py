import operator
from typing import Annotated, List, TypedDict, Union, Dict, Any
import os
import json
import pandas as pd
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import StateGraph, END
import yfinance as yf
from tradingview_ta import TA_Handler, Interval, Exchange

# Load environment variables
load_dotenv()

def sanitize_data(data):
    """Recursively replace NaN and Infinity with None for JSON compliance."""
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple, set)):
        return [sanitize_data(x) for x in data]
    elif isinstance(data, (float, int)):
        import math
        try:
            if math.isnan(data) or math.isinf(data):
                return None
        except Exception:
            return None
    return data

def extract_json(task_content: str):
    """Extracts JSON block from a string that might contain markdown or extra text."""
    if not task_content:
        return None
    try:
        # 1. Try direct parsing
        return json.loads(task_content)
    except Exception:
        pass
        
    try:
        # 2. Try cleaning markdown blocks
        if "```json" in task_content:
            task_content = task_content.split("```json")[1].split("```")[0].strip()
        elif "```" in task_content:
            task_content = task_content.split("```")[1].split("```")[0].strip()
            
        # 3. Last resort: match first '{' and last '}'
        start = task_content.find('{')
        end = task_content.rfind('}')
        if start != -1 and end != -1:
            json_str = task_content[start:end+1]
            # Remove any trailing commas that break strict JSON
            import re
            json_str = re.sub(r",\s*}", "}", json_str)
            json_str = re.sub(r",\s*]", "]", json_str)
            return json.loads(json_str)
            
        return None
    except Exception as e:
        print(f"Error extracting JSON: {e}")
        return None

# Define the shared state
class SharedState(TypedDict):
    ticker: str
    financial_data: dict
    macro_data: dict
    chart_data: dict
    agent_responses: Annotated[List[Dict[str, Any]], operator.add]
    final_verdict: str
    dalio_response: dict

# LLM Configuration
# Migrating to the "2.5" generation as confirmed by list_models and API feedback
llm_supervisor = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=os.getenv("GOOGLE_API_KEY"))
llm_extraction = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))
llm_standard = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=os.getenv("GOOGLE_API_KEY"))

# Tavily Search Tool
tavily_tool = TavilySearchResults(max_results=3)

# Data Fetching Utility
def fetch_financial_data(ticker_symbol: str):
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info or {}
        ticker_name = info.get('shortName', ticker_symbol)
        
        # 1. Historical Prices (Candlestick)
        price_data = []
        history = pd.DataFrame()
        try:
            history = stock.history(period="1y")
            if not history.empty:
                for index, row in history.iterrows():
                    price_data.append({
                        "time": index.strftime('%Y-%m-%d'),
                        "open": row['Open'], "high": row['High'], "low": row['Low'], "close": row['Close']
                    })
        except Exception as he: print(f"History Error: {he}")

        # 2. Tech Indicators (TradingView + Fallbacks)
        tech_indicators = {}
        tv_data = {"summary": {"RECOMMENDATION": "UNKNOWN"}}
        
        try:
            exchange = "NASDAQ"
            if info.get('exchange') == 'NYQ': exchange = "NYSE"
            elif info.get('exchange') == 'ASQ': exchange = "AMEX"
            
            handler = TA_Handler(
                symbol=ticker_symbol, screener="america",
                exchange=exchange, interval=Interval.INTERVAL_1_DAY
            )
            analysis_tv = handler.get_analysis()
            inds = analysis_tv.indicators
            
            def get_tv_ind(inds, keys, default=0):
                if isinstance(keys, str): keys = [keys]
                for k in keys:
                    if k in inds and inds[k] is not None:
                        try: return float(inds[k])
                        except: continue
                return default

            tech_indicators = {
                "current_price": get_tv_ind(inds, ["close", "Close"], float(history['Close'].iloc[-1]) if not history.empty else 0),
                "rsi": get_tv_ind(inds, ["RSI", "RSI[1]"], 0),
                "macd": get_tv_ind(inds, "MACD.macd", 0),
                "macd_signal": get_tv_ind(inds, "MACD.signal", 0),
                "sma20": get_tv_ind(inds, ["SMA20", "EMA20"], 0),
                "sma50": get_tv_ind(inds, ["SMA50", "EMA50"], 0),
                "sma200": get_tv_ind(inds, ["SMA200", "EMA200"], 0),
                "upper_band": get_tv_ind(inds, "BB.upper", 0),
                "lower_band": get_tv_ind(inds, "BB.lower", 0),
                "tv_recommendation": analysis_tv.summary.get("RECOMMENDATION", "UNKNOWN")
            }
            tv_data = {
                "summary": analysis_tv.summary,
                "oscillators": analysis_tv.oscillators,
                "moving_averages": analysis_tv.moving_averages
            }
        except Exception as tve:
            print(f"TV Error, using fallbacks: {tve}")
            last_price = float(history['Close'].iloc[-1]) if not history.empty else 0
            tech_indicators = {
                "current_price": last_price, "rsi": 50, "sma20": 0, "sma50": 0, "sma200": 0,
                "upper_band": 0, "lower_band": 0, "macd": 0, "macd_signal": 0,
                "tv_recommendation": "UNKNOWN", "msg": "TV Connection Failed"
            }

        # 3. Fundamental Engine (Institutional)
        fundamental_engine = {}
        try:
            is_ = stock.financials
            bs = stock.balance_sheet
            
            def safe_get(df, index_keys, default=None):
                if df is None or df.empty: return default
                for k in index_keys:
                    if k in df.index:
                        val = df.loc[k]
                        if isinstance(val, pd.Series): val = val.iloc[0]
                        return float(val) if pd.notnull(val) else default
                return default

            ebit = safe_get(is_, ['EBIT', 'Operating Income'])
            total_rev = safe_get(is_, ['Total Revenue'])
            net_inc = safe_get(is_, ['Net Income'])
            total_assets = safe_get(bs, ['Total Assets'])
            total_equity = safe_get(bs, ['Stockholders Equity', 'Total Stockholder Equity'])
            total_debt = safe_get(bs, ['Total Debt', 'Long Term Debt'], 0)
            
            fundamental_engine = {
                "profitability": {
                    "gross_margin": (safe_get(is_, ['Gross Profit']) / total_rev) if total_rev else "DATA_INCOMPLETE",
                    "ebit_margin": (ebit / total_rev) if ebit and total_rev else "DATA_INCOMPLETE",
                    "roe": (net_inc / total_equity) if net_inc and total_equity else "DATA_INCOMPLETE",
                    "roic": (ebit * 0.75 / (total_debt + total_equity)) if ebit and (total_debt + total_equity) else "DATA_INCOMPLETE"
                },
                "valuation": {
                    "pe": info.get('trailingPE') or info.get('forwardPE') or "DATA_INCOMPLETE",
                    "market_cap": info.get('marketCap')
                }
            }
        except Exception as fe: print(f"Fundamental Error: {fe}")

        return sanitize_data({
            "ticker": ticker_symbol,
            "name": ticker_name,
            "info": info,
            "chart_data": {"prices": price_data},
            "tech_indicators": tech_indicators,
            "fundamental_engine": fundamental_engine,
            "tradingview": tv_data
        })
    except Exception as e:
        print(f"CRITICAL ERROR in fetch_financial_data for {ticker_symbol}: {e}")
        return sanitize_data({
            "info": {}, "chart_data": {"prices": []}, 
            "tech_indicators": {"current_price": 0, "rsi": 50}, 
            "fundamental_engine": {}, "tradingview": {"error": str(e)}
        })

# --- Specialized Agents (Nodes) ---

def agente_lynch(state: SharedState):
    print("--- Agente Lynch: Iniciando análisis ---")
    fundamentals = state.get("financial_data", {}).get("fundamental_engine", {})
    prompt = f"Actúa como Peter Lynch. Analiza {state['ticker']}.\nDATOS: {fundamentals}\nResponde JSON: {{\"signal\": \"BUY/SELL/HOLD\", \"confidence\": 0.8, \"analysis\": \"...\", \"selected_metrics\": [], \"discarded_metrics\": []}}"
    res_json = extract_json(llm_extraction.invoke(prompt).content) or {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error"}
    return {"agent_responses": [{"agent_name": "Lynch", **res_json}]}

def agente_buffett(state: SharedState):
    print("--- Agente Buffett: Iniciando análisis ---")
    fundamentals = state.get("financial_data", {}).get("fundamental_engine", {})
    prompt = f"Actúa como Warren Buffett. Analiza {state['ticker']}.\nDATOS: {fundamentals}\nResponde JSON: {{\"signal\": \"BUY/SELL/HOLD\", \"confidence\": 0.9, \"analysis\": \"...\", \"selected_metrics\": [], \"discarded_metrics\": []}}"
    res_json = extract_json(llm_standard.invoke(prompt).content) or {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error"}
    return {"agent_responses": [{"agent_name": "Buffett", **res_json}]}

def agente_marks(state: SharedState):
    print("--- Agente Marks: Iniciando análisis macro ---")
    search = tavily_tool.invoke(f"sentiment for {state['ticker']}")
    prompt = f"Actúa como Howard Marks. Analiza {state['ticker']}.\nCONTEXTO: {search}\nResponde JSON: {{\"signal\": \"BUY/SELL/HOLD\", \"confidence\": 0.85, \"analysis\": \"...\", \"selected_metrics\": [], \"discarded_metrics\": []}}"
    res_json = extract_json(llm_standard.invoke(prompt).content) or {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error"}
    return {"agent_responses": [{"agent_name": "Marks", **res_json}]}

def agente_icahn(state: SharedState):
    print("--- Agente Icahn: Iniciando análisis activista ---")
    fundamentals = state.get("financial_data", {}).get("fundamental_engine", {})
    prompt = f"Actúa como Carl Icahn. Analiza {state['ticker']}.\nDATOS: {fundamentals}\nResponde JSON: {{\"signal\": \"BUY/SELL/HOLD\", \"confidence\": 0.8, \"analysis\": \"...\", \"selected_metrics\": [], \"discarded_metrics\": []}}"
    res_json = extract_json(llm_extraction.invoke(prompt).content) or {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error"}
    return {"agent_responses": [{"agent_name": "Icahn", **res_json}]}

def agente_bollinger(state: SharedState):
    print("--- Agente Bollinger: Iniciando análisis ---")
    tech = state.get("financial_data", {}).get("tech_indicators", {})
    prompt = f"Actúa como experto en Bollinger. Analiza {state['ticker']}.\nDATOS: {tech}\nResponde JSON: {{\"signal\": \"BUY/SELL/NEUTRAL\", \"confidence\": 0.7, \"analysis\": \"...\", \"selected_metrics\": [], \"discarded_metrics\": []}}"
    res_json = extract_json(llm_extraction.invoke(prompt).content) or {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error"}
    return {"agent_responses": [{"agent_name": "Bollinger", **res_json}]}

def agente_rsi(state: SharedState):
    print("--- Agente RSI: Iniciando análisis de momentum ---")
    tech = state.get("financial_data", {}).get("tech_indicators", {})
    prompt = f"Actúa como experto en RSI. Analiza {state['ticker']}.\nDATOS RSI: {tech.get('rsi')}\nResponde JSON: {{\"signal\": \"BUY/SELL/NEUTRAL\", \"confidence\": 0.7, \"analysis\": \"...\", \"selected_metrics\": [], \"discarded_metrics\": []}}"
    res_json = extract_json(llm_extraction.invoke(prompt).content) or {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error"}
    return {"agent_responses": [{"agent_name": "RSI", **res_json}]}

def agente_macd(state: SharedState):
    print("--- Agente MACD: Iniciando análisis ---")
    tech = state.get("financial_data", {}).get("tech_indicators", {})
    prompt = f"Actúa como experto en MACD. Analiza {state['ticker']}.\nDATOS: {tech}\nResponde JSON: {{\"signal\": \"BUY/SELL/NEUTRAL\", \"confidence\": 0.7, \"analysis\": \"...\", \"selected_metrics\": [], \"discarded_metrics\": []}}"
    res_json = extract_json(llm_extraction.invoke(prompt).content) or {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error"}
    return {"agent_responses": [{"agent_name": "MACD", **res_json}]}

def agente_gann(state: SharedState):
    print("--- Agente Gann: Iniciando análisis ---")
    tech = state.get("financial_data", {}).get("tech_indicators", {})
    prompt = f"Actúa como experto en niveles. Analiza {state['ticker']}.\nDATOS: {tech}\nResponde JSON: {{\"signal\": \"BUY/SELL/NEUTRAL\", \"confidence\": 0.6, \"analysis\": \"...\", \"selected_metrics\": [], \"discarded_metrics\": []}}"
    res_json = extract_json(llm_extraction.invoke(prompt).content) or {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error"}
    return {"agent_responses": [{"agent_name": "Gann", **res_json}]}

def agente_dalio(state: SharedState):
    print("--- Agente Dalio: Iniciando síntesis final ---")
    responses = state["agent_responses"]
    summary = "\n".join([f"{r['agent_name']}: {r['signal']} (conf {r['confidence']})" for r in responses])
    prompt = f"Actúa como Ray Dalio. Sintetiza estos informes:\n{summary}\nResponde JSON: {{\"verdict\": \"...\", \"risk_score\": 5, \"allocation_rec\": \"...\", \"summary_table\": \"...\"}}"
    res_json = extract_json(llm_supervisor.invoke(prompt).content) or {"verdict": "Error"}
    return {"final_verdict": res_json["verdict"], "dalio_response": res_json}

# BUILDING THE GRAPH
workflow = StateGraph(SharedState)

def data_fetcher_node(state: SharedState):
    return {"financial_data": fetch_financial_data(state["ticker"])}

workflow.add_node("DataFetcher", data_fetcher_node)
for name, func in [("Lynch", agente_lynch), ("Buffett", agente_buffett), ("Marks", agente_marks), ("Icahn", agente_icahn),
                  ("Bollinger", agente_bollinger), ("RSI", agente_rsi), ("MACD", agente_macd), ("Gann", agente_gann)]:
    workflow.add_node(name, func)
    workflow.add_edge("DataFetcher", name)
    workflow.add_edge(name, "Dalio")

workflow.add_node("Dalio", agente_dalio)
workflow.set_entry_point("DataFetcher")
workflow.add_edge("Dalio", END)

app_graph = workflow.compile()
