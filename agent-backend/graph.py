import operator
from typing import Annotated, List, TypedDict, Union, Dict
import os
import json
import pandas as pd
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import StateGraph, END
from pydantic import BaseModel
import yfinance as yf

# Load environment variables
load_dotenv()

def sanitize_data(data):
    """Recursively replace NaN and Infinity with None for JSON compliance."""
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(x) for x in data]
    if isinstance(data, float):
        if pd.isna(data) or data == float('inf') or data == float('-inf'):
            return None
    return data

def extract_json(task_content: str):
    """Extracts JSON block from a string that might contain markdown or extra text."""
    try:
        # Look for the first '{' and last '}'
        start = task_content.find('{')
        end = task_content.rfind('}')
        if start != -1 and end != -1:
            json_str = task_content[start:end+1]
            return json.loads(json_str)
        return json.loads(task_content)
    except Exception as e:
        print(f"Error extracting JSON: {e}")
        return None

# Define the shared state
class AgentSignal(BaseModel):
    agent_name: str
    signal: str # e.g., "BUY", "SELL", "HOLD", "NEUTRAL"
    confidence: float
    analysis: str
    key_metrics: Dict[str, Union[float, str]]

class SharedState(TypedDict):
    ticker: str
    financial_data: dict
    chart_data: dict # New: Structured data for frontend charts
    agent_responses: Annotated[List[AgentSignal], operator.add]
    final_verdict: str

# LLM Configuration
# Using Gemini 2.5 models for maximum performance and compatibility with current API status
llm_supervisor = ChatGoogleGenerativeAI(model="gemini-2.5-pro")
llm_extraction = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
llm_standard = ChatGoogleGenerativeAI(model="gemini-2.5-pro")

# Tavily Search Tool
tavily_tool = TavilySearchResults(max_results=3)

# Data Fetching Utility
def fetch_financial_data(ticker_symbol: str):
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        # Historical price data for Candlestick chart
        history = stock.history(period="1y")
        price_data = []
        for index, row in history.iterrows():
            price_data.append({
                "time": index.strftime('%Y-%m-%d'),
                "open": row['Open'],
                "high": row['High'],
                "low": row['Low'],
                "close": row['Close']
            })
            
        # Financials for Cash Flow chart
        cashflow = stock.cashflow
        cf_data = []
        if not cashflow.empty:
            # We want 'Free Cash Flow' and 'Total Revenue' (if available in financials)
            # Fetching financials for Revenue
            financials = stock.financials
            for col in cashflow.columns:
                date_str = col.strftime('%Y')
                fcf = cashflow.loc['Free Cash Flow', col] if 'Free Cash Flow' in cashflow.index else 0
                rev = financials.loc['Total Revenue', col] if 'Total Revenue' in financials.index else 0
                cf_data.append({
                    "year": date_str,
                    "fcf": float(fcf),
                    "revenue": float(rev)
                })
        
        # --- Technical Indicators Calculation ---
        # Close prices for TA
        closes = history['Close']
        
        # SMA 20, 50, 200
        sma20 = closes.rolling(window=20).mean().iloc[-1]
        sma50 = closes.rolling(window=50).mean().iloc[-1]
        sma200 = closes.rolling(window=200).mean().iloc[-1]
        
        # RSI (14)
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # MACD (12, 26, 9)
        exp12 = closes.ewm(span=12, adjust=False).mean()
        exp26 = closes.ewm(span=26, adjust=False).mean()
        macd = exp12 - exp26
        signal_line = macd.ewm(span=9, adjust=False).mean()
        macd_val = macd.iloc[-1]
        macd_signal = signal_line.iloc[-1]
        
        # Bollinger Bands (20)
        std20 = closes.rolling(window=20).std().iloc[-1]
        upper_band = sma20 + (std20 * 2)
        lower_band = sma20 - (std20 * 2)
        
        tech_indicators = {
            "sma20": float(sma20),
            "sma50": float(sma50),
            "sma200": float(sma200),
            "rsi": float(rsi),
            "macd": float(macd_val),
            "macd_signal": float(macd_signal),
            "upper_band": float(upper_band),
            "lower_band": float(lower_band),
            "current_price": float(closes.iloc[-1])
        }
        
        return sanitize_data({
            "info": info,
            "chart_data": {
                "prices": price_data,
                "cashflow": cf_data[::-1]
            },
            "tech_indicators": tech_indicators
        })
    except Exception as e:
        print(f"Error fetching data for {ticker_symbol}: {e}")
        return {"info": {}, "chart_data": {"prices": [], "cashflow": []}}

# Nodes (Specialized Agents)

def agente_lynch(state: SharedState):
    print("--- Agente Lynch: Iniciando análisis ---")
    ticker = state["ticker"]
    data = state.get("financial_data", {}).get("info", {})
    
    peg = data.get("trailingPegRatio", 0)
    debt_to_equity = data.get("debtToEquity", 0)
    profit_margins = data.get("profitMargins", 0)
    
    analysis_prompt = f"""
    Actúa como Peter Lynch. Realiza un análisis FUNDAMENTAL exhaustivo de {ticker}.
    DATOS CLAVE:
    - PEG Ratio: {peg}
    - Debt/Equity: {debt_to_equity}
    - Profit Margins: {profit_margins}
    - Info General: {data.get('longBusinessSummary', 'No disponible')[:500]}...

    TU MISIÓN:
    1. Clasifica la acción rigurosamente (Fast Grower, Stalwart, Slow Grower, Cyclical, Asset Play, Turnaround).
    2. Evalúa si la historia de crecimiento es compatible con la valoración actual.
    3. Analiza la carga de deuda y si los márgenes permiten absorber choques.
    4. Concluye si es una 'Inversión Simple' (que un niño de 10 años entendería) y si el precio es una ganga.

    RESPUESTA: Debes ser detallado y usar un tono directo y sabio.
    Responde en formato JSON: {{"signal": "BUY/SELL/HOLD", "confidence": 0.0-1.0, "analysis": "ANÁLISIS DETALLADO AQUÍ", "category": "..."}}
    """
    
    response = llm_extraction.invoke(analysis_prompt)
    res_json = extract_json(response.content)
    if not res_json:
        res_json = {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error parsing Lynch analysis", "category": "Unknown"}
        
    signal = AgentSignal(
        agent_name="Lynch", 
        signal=res_json["signal"], 
        confidence=res_json["confidence"], 
        analysis=res_json["analysis"],
        key_metrics={"peg": peg, "category": res_json.get("category", "N/A")}
    )
    return {"agent_responses": [signal]}

def agente_buffett(state: SharedState):
    print("--- Agente Buffett: Iniciando análisis ---")
    ticker = state["ticker"]
    data = state.get("financial_data", {}).get("info", {})
    roe = data.get("returnOnEquity", 0)
    current_ratio = data.get("currentRatio", 0)
    
    analysis_prompt = f"""
    Actúa como Warren Buffett. Realiza un análisis de VALOR e INTANGIBLES de {ticker}.
    DATOS CLAVE:
    - Return on Equity (ROE): {roe}
    - Current Ratio: {current_ratio}
    - Margen Bruto: {data.get('grossMargins', 0)}
    - Free Cash Flow: {data.get('freeCashflow', 0)}

    TU MISIÓN:
    1. Determina la calidad del 'Moat' (Foso Defensivo). ¿Es una marca, una ventaja de escala o un monopolio local?
    2. Evalúa la gestión del capital. ¿El management genera retornos consistentes sobre el patrimonio?
    3. Calcula un margen de seguridad cualitativo basado en la estabilidad de sus flujos de caja.
    4. Decide si este es un negocio que te gustaría tener durante los próximos 10, 20 o 30 años.

    RESPUESTA: Usa un tono tranquilo, paciente y centrado en la calidad del negocio.
    Responde en formato JSON: {{"signal": "BUY/SELL/HOLD", "confidence": 0.0-1.0, "analysis": "ANÁLISIS DETALLADO AQUÍ"}}
    """
    
    response = llm_standard.invoke(analysis_prompt)
    res_json = extract_json(response.content)
    if not res_json:
        res_json = {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error parsing Buffett analysis"}

    signal = AgentSignal(
        agent_name="Buffett", 
        signal=res_json["signal"], 
        confidence=res_json["confidence"], 
        analysis=res_json["analysis"],
        key_metrics={"roe": roe, "moat_rating": "Evaluated"}
    )
    return {"agent_responses": [signal]}

def agente_marks(state: SharedState):
    """
    Riesgo y Ciclo: Sentimiento, Crédito, Inflación.
    INTEGRACIÓN TAVILY: Búsqueda macro en tiempo real.
    """
    print("--- Agente Marks: Iniciando análisis macro ---")
    ticker = state["ticker"]
    
    # Performing web search for macro context
    search_query = f"current market sentiment interest rates inflation and macro news for {ticker} stock 2024"
    search_results = tavily_tool.invoke(search_query)
    
    analysis_prompt = f"""
    Actúa como Howard Marks. Analiza el entorno macro actual para {ticker}.
    CONTEXTO DE BÚSQUEDA WEB:
    {search_results}
    
    Considera los ciclos de mercado, la psicología del inversor y el riesgo sistémico basado en las noticias recientes.
    ¿Estamos en una etapa de exuberancia o de miedo? ¿Cómo afectan las tasas de interés y la inflación a este ticker?
    Responde en formato JSON: {{"signal": "AGRESSIVE/DEFENSIVE/NEUTRAL", "confidence": 0-1.0, "analysis": "...", "posture": "..."}}
    """
    
    response = llm_standard.invoke(analysis_prompt)
    res_json = extract_json(response.content)
    if not res_json:
        res_json = {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error parsing Marks analysis", "posture": "Neutral"}

    signal = AgentSignal(
        agent_name="Marks", 
        signal=res_json["signal"], 
        confidence=res_json["confidence"], 
        analysis=res_json["analysis"],
        key_metrics={"market_posture": res_json.get("posture", "N/A")}
    )
    return {"agent_responses": [signal]}

def agente_icahn(state: SharedState):
    print("--- Agente Icahn: Iniciando análisis activista ---")
    ticker = state["ticker"]
    data = state.get("financial_data", {}).get("info", {})
    pe = data.get("trailingPE", 0)
    cash = data.get("totalCash", 0)
    
    analysis_prompt = f"""
    Actúa como Carl Icahn. Realiza un análisis ACTIVISTA y de INEFICIENCIAS en {ticker}.
    DATOS CLAVE:
    - P/E Ratio: {pe}
    - Total Cash: {cash}
    - Valor de Empresa/EBITDA: {data.get('enterpriseToEbitda', 0)}
    - % Acciones en manos de Instituciones: {data.get('heldPercentInstitutions', 0)}

    TU MISIÓN:
    1. Identifica ineficiencias. ¿Está el management sentado en demasiado efectivo? ¿Hay segmentos de negocio mal gestionados?
    2. Determina si el precio actual ofrece una oportunidad para entrar y forzar cambios (reestructuración, recompras, dividendos).
    3. Evalúa si la directiva está alineada con el valor para el accionista o si son burócratas desperdiciando el capital.
    4. Sé agresivo. Si el negocio está mal gestionado, dilo claramente.

    RESPUESTA: Usa un tono combativo, directo y enfocado en 'liberar valor'.
    Responde en formato JSON: {{"signal": "BUY/SELL/HOLD", "confidence": 0.0-1.0, "analysis": "ANÁLISIS DETALLADO AQUÍ"}}
    """
    
    response = llm_extraction.invoke(analysis_prompt)
    res_json = extract_json(response.content)
    if not res_json:
        res_json = {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error parsing Icahn analysis"}

    signal = AgentSignal(
        agent_name="Icahn", 
        signal=res_json["signal"], 
        confidence=res_json["confidence"], 
        analysis=res_json["analysis"],
        key_metrics={"pe_ratio": pe, "opportunistic_value": "High" if pe < 15 else "Low"}
    )
    return {"agent_responses": [signal]}

def agente_bollinger(state: SharedState):
    print("--- Agente Bollinger: Iniciando análisis de volatilidad ---")
    ticker = state["ticker"]
    tech = state.get("financial_data", {}).get("tech_indicators", {})
    
    analysis_prompt = f"""
    Actúa como un experto en Bandas de Bollinger. Analiza la volatilidad de {ticker}.
    DATOS TÉCNICOS:
    - Precio Actual: {tech.get('current_price')}
    - Banda Superior: {tech.get('upper_band')}
    - Banda Inferior: {tech.get('lower_band')}
    - SMA 20: {tech.get('sma20')}

    TU MISIÓN:
    1. Determina si el precio está en zonas de sobreextensión (tocando bandas).
    2. Analiza si hay una contracción de volatilidad (Squeeze) que preceda un movimiento fuerte.
    3. Define si la tendencia actual tiene fuerza o si está perdiendo impulso según la posición respecto a la media móvil de 20.
    Responde en formato JSON: {{"signal": "BUY/SELL/NEUTRAL", "confidence": 0.0-1.0, "analysis": "..."}}
    """
    response = llm_extraction.invoke(analysis_prompt)
    res_json = extract_json(response.content)
    if not res_json: res_json = {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error parsing Bollinger analysis"}
    return {"agent_responses": [AgentSignal(agent_name="Bollinger", **res_json, key_metrics=tech)]}

def agente_rsi(state: SharedState):
    print("--- Agente RSI: Iniciando análisis de momentum ---")
    ticker = state["ticker"]
    tech = state.get("financial_data", {}).get("tech_indicators", {})
    
    analysis_prompt = f"""
    Actúa como un especialista en Momentum (RSI). Analiza la fuerza de {ticker}.
    RSI Actual: {tech.get('rsi')}
    
    TU MISIÓN:
    1. ¿Está el activo en zona de sobrecompra (>70) o sobreventa (<30)?
    2. ¿Hay divergencias o señales de agotamiento de tendencia?
    3. Proporciona una lectura clara de la 'velocidad' del movimiento actual.
    Responde en formato JSON: {{"signal": "BUY/SELL/NEUTRAL", "confidence": 0.0-1.0, "analysis": "..."}}
    """
    response = llm_extraction.invoke(analysis_prompt)
    res_json = extract_json(response.content)
    if not res_json: res_json = {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error parsing RSI analysis"}
    return {"agent_responses": [AgentSignal(agent_name="RSI", **res_json, key_metrics=tech)]}

def agente_macd(state: SharedState):
    print("--- Agente MACD: Iniciando análisis de tendencia ---")
    ticker = state["ticker"]
    tech = state.get("financial_data", {}).get("tech_indicators", {})
    
    analysis_prompt = f"""
    Actúa como un experto en convergencia/divergencia de medias móviles (MACD).
    MACD: {tech.get('macd')}
    Señal: {tech.get('macd_signal')}
    
    TU MISIÓN:
    1. Identifica cruces de líneas y su relevancia.
    2. Determina si estamos en una fase de aceleración o deceleración de tendencia.
    3. Evalúa la posición respecto a la línea de cero.
    Responde en formato JSON: {{"signal": "BUY/SELL/NEUTRAL", "confidence": 0.0-1.0, "analysis": "..."}}
    """
    response = llm_extraction.invoke(analysis_prompt)
    res_json = extract_json(response.content)
    if not res_json: res_json = {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error parsing MACD analysis"}
    return {"agent_responses": [AgentSignal(agent_name="MACD", **res_json, key_metrics=tech)]}

def agente_gann(state: SharedState):
    print("--- Agente Gann: Iniciando análisis de niveles ---")
    ticker = state["ticker"]
    tech = state.get("financial_data", {}).get("tech_indicators", {})
    
    analysis_prompt = f"""
    Actúa como un analista de niveles de soporte, resistencia y geometría de mercado (estilo Gann/Soportes).
    DATOS:
    - Precio Actual: {tech.get('current_price')}
    - SMA 50: {tech.get('sma50')}
    - SMA 200: {tech.get('sma200')}

    TU MISIÓN:
    1. Identifica los soportes y resistencias clave según las medias móviles de largo plazo.
    2. Determina si el precio está operando por encima o debajo del 'Muro' de 200 periodos.
    3. Evalúa la estructura del mercado: ¿Máximos crecientes o erosión de soporte?
    Responde en formato JSON: {{"signal": "BUY/SELL/NEUTRAL", "confidence": 0.0-1.0, "analysis": "..."}}
    """
    response = llm_extraction.invoke(analysis_prompt)
    res_json = extract_json(response.content)
    if not res_json: res_json = {"signal": "NEUTRAL", "confidence": 0.5, "analysis": "Error parsing Gann analysis"}
    return {"agent_responses": [AgentSignal(agent_name="Gann", **res_json, key_metrics=tech)]}

def agente_dalio(state: SharedState):
    """
    Supervisor / Portfolio Manager: Toma de decisiones ponderada por credibilidad.
    USANDO GEMINI 1.5 PRO.
    """
    print("--- Agente Dalio: Iniciando síntesis final ---")
    ticker = state["ticker"]
    responses = state["agent_responses"]
    
    summary = "\n".join([f"{r.agent_name} ({r.signal}, conf: {r.confidence}): {r.analysis[:150]}..." for r in responses])
    
    analysis_prompt = f"""
    Actúa como Ray Dalio (Supervisor Maestro). Tienes un comité de 8 mentes maestras analizando {ticker}:
    - FUNDAMENTALISTAS: Lynch, Buffett, Icahn.
    - MACRO/PSICOLOGÍA: Marks.
    - TÉCNICOS: Bollinger, RSI, MACD, Gann.

    TU MISIÓN:
    1. Sintetiza las 8 señales aplicando ponderación por credibilidad.
    2. Resuelve conflictos. Por ejemplo: ¿Es una oportunidad técnica de rebote (RSI/MACD) aunque Icahn vea mala gestión?
    3. Considera el entorno macro de Marks como el 'viento' que empuja a todos los demás.
    4. Emite un Veredicto Final que sea una obra maestra de equilibrio entre fundamentales y técnica.

    Resumen de agentes:
    {summary}
    
    Responde EN ESPAÑOL en formato JSON: {{"verdict": "VEREDICTO MAGISTRAL AQUÍ", "risk_score": 0-10, "allocation_rec": "..."}}
    """
    
    response = llm_supervisor.invoke(analysis_prompt)
    res_json = extract_json(response.content)
    if not res_json:
        res_json = {"verdict": "Error synthesizing final verdict", "risk_score": 5, "allocation_rec": "Neutral"}

    return {"final_verdict": res_json["verdict"]}

# Building the Graph
workflow = StateGraph(SharedState)

# Add Nodes
def data_fetcher_node(state: SharedState):
    print(f"--- Data Fetcher: Obteniendo datos para {state['ticker']} ---")
    data = fetch_financial_data(state["ticker"])
    print("--- Data Fetcher: Datos obtenidos correctamente ---")
    return {
        "financial_data": {"info": data["info"]},
        "chart_data": data["chart_data"]
    }

workflow.add_node("DataFetcher", data_fetcher_node)
workflow.add_node("Lynch", agente_lynch)
workflow.add_node("Buffett", agente_buffett)
workflow.add_node("Marks", agente_marks)
workflow.add_node("Icahn", agente_icahn)
workflow.add_node("Bollinger", agente_bollinger)
workflow.add_node("RSI", agente_rsi)
workflow.add_node("MACD", agente_macd)
workflow.add_node("Gann", agente_gann)
workflow.add_node("Dalio", agente_dalio)

# Define Edges
workflow.set_entry_point("DataFetcher")
workflow.add_edge("DataFetcher", "Lynch")
workflow.add_edge("Lynch", "Buffett")
workflow.add_edge("Buffett", "Marks")
workflow.add_edge("Marks", "Icahn")
workflow.add_edge("Icahn", "Bollinger")
workflow.add_edge("Bollinger", "RSI")
workflow.add_edge("RSI", "MACD")
workflow.add_edge("MACD", "Gann")
workflow.add_edge("Gann", "Dalio")
workflow.add_edge("Dalio", END)

# Compile for execution
app_graph = workflow.compile()
