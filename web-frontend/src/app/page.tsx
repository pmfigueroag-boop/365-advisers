"use client";

import { useState } from "react";
import { PriceChart, CashFlowChart } from "@/components/Charts";
import TradingViewChart from "@/components/TradingViewChart";
import TradingViewTechnicalWidget from "@/components/TradingViewTechnicalWidget";
import {
  TrendingUp,
  TrendingDown,
  AlertCircle,
  BarChart3,
  Search,
  Activity,
  ShieldCheck,
  Zap
} from "lucide-react";

interface AgentSignal {
  agent_name: string;
  signal: string;
  confidence: number;
  analysis: string;
  key_metrics: any;
  selected_metrics?: string[];
  discarded_metrics?: string[];
}

const FundamentalTable = ({ engine }: { engine: any }) => {
  if (!engine) return null;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      {Object.entries(engine).map(([category, metrics]: [string, any]) => (
        <div key={category} className="glass-card p-4 border-[#30363d] bg-[#0d1117]/30">
          <h4 className="text-[10px] font-black uppercase text-[#d4af37] mb-3 tracking-widest">{category.replace('_', ' ')}</h4>
          <div className="space-y-2">
            {Object.entries(metrics).map(([key, val]: [string, any]) => (
              <div key={key} className="flex justify-between items-center">
                <span className="text-[10px] text-gray-500 capitalize">{key.replace(/_/g, ' ')}</span>
                <span className={`text-[10px] font-mono ${val === 'DATA_INCOMPLETE' ? 'text-red-500/50' : 'text-gray-200'}`}>
                  {typeof val === 'number' ?
                    (val > 1 || val < -1 ? val.toLocaleString('en-US', { maximumFractionDigits: 2 }) : (val * 100).toFixed(2) + '%')
                    : val}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

const TradingViewTechnical = ({ data }: { data: any }) => {
  if (!data || data.error) return null;
  const recommendation = data.summary?.RECOMMENDATION || "UNKNOWN";

  return (
    <div className="glass-card p-6 border-[#30363d] bg-[#0d1117]/40">
      <div className="flex justify-between items-center mb-6">
        <h4 className="text-sm font-black uppercase tracking-widest text-[#d4af37]">TradingView Consensus</h4>
        <span className={`px-3 py-1 rounded-full text-xs font-black tracking-widest ${recommendation.includes('BUY') ? 'bg-green-500/20 text-green-400' :
          recommendation.includes('SELL') ? 'bg-red-500/20 text-red-400' :
            'bg-gray-500/20 text-gray-400'
          }`}>
          {recommendation}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-4 text-center">
        <div className="p-3 bg-black/20 rounded-xl border border-[#30363d]">
          <span className="block text-[10px] text-gray-500 uppercase font-black mb-1">Oscillators</span>
          <span className="text-sm font-mono text-gray-200">{data.oscillators?.RECOMMENDATION || 'N/A'}</span>
        </div>
        <div className="p-3 bg-black/20 rounded-xl border border-[#30363d]">
          <span className="block text-[10px] text-gray-500 uppercase font-black mb-1">Moving Avg</span>
          <span className="text-sm font-mono text-gray-200">{data.moving_averages?.RECOMMENDATION || 'N/A'}</span>
        </div>
        <div className="p-3 bg-black/20 rounded-xl border border-[#30363d]">
          <span className="block text-[10px] text-gray-500 uppercase font-black mb-1">Summary</span>
          <div className="flex justify-center gap-2 mt-1">
            <span className="text-[10px] text-green-500 font-black">B: {data.summary?.BUY || 0}</span>
            <span className="text-[10px] text-gray-500 font-black">H: {data.summary?.NEUTRAL || 0}</span>
            <span className="text-[10px] text-red-500 font-black">S: {data.summary?.SELL || 0}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default function Home() {
  const [ticker, setTicker] = useState("");
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);

  const handleAnalyze = async () => {
    if (!ticker) return;
    setLoading(true);
    setAnalysis(null);
    try {
      const response = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker }),
      });
      const data = await response.json();
      setAnalysis(data);
    } catch (error) {
      console.error("Error analyzing stock:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen p-8 max-w-7xl mx-auto">
      <header className="flex flex-col md:flex-row justify-between items-center mb-12 gap-6">
        <div className="flex items-center gap-3">
          <div className="bg-[#d4af37] p-2 rounded-lg">
            <TrendingUp size={32} className="text-black" />
          </div>
          <h1 className="text-4xl font-black gold-gradient tracking-tighter">365 ADVISERS</h1>
        </div>

        <div className="flex gap-2 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={18} />
            <input
              type="text"
              placeholder="Search Ticker (e.g. NVDA)"
              className="w-full bg-[#161b22] border border-[#30363d] pl-10 pr-4 py-3 rounded-xl focus:outline-none focus:border-[#d4af37] transition-all"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
            />
          </div>
          <button
            onClick={handleAnalyze}
            disabled={loading}
            className="bg-[#d4af37] text-black font-bold px-8 py-3 rounded-xl hover:bg-[#f9e29c] transition-all disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? (
              <>
                <Activity key="loading-icon" className="animate-spin" size={18} />
                <span key="loading-text">Analyzing...</span>
              </>
            ) : (
              <>
                <Zap key="ready-icon" size={18} />
                <span key="ready-text">Analyze</span>
              </>
            )}
          </button>
        </div>
      </header>

      {analysis && (
        <div className="space-y-6">
          {/* Top Section: Charts & Verdict */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Price Chart */}
            <section className="lg:col-span-2 glass-card p-6 border-[#30363d]">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-sm font-bold uppercase tracking-widest text-gray-400">Advanced TradingView Chart</h3>
                <span className="text-xs text-[#d4af37] font-mono">{analysis.ticker} | Real-Time</span>
              </div>
              <TradingViewChart symbol={analysis.ticker} />
            </section>

            {/* Final Verdict */}
            <section className="glass-card p-8 border-[#d4af37]/30 bg-[#d4af37]/5 flex flex-col">
              <div className="flex items-center gap-2 mb-4 text-[#d4af37]">
                <ShieldCheck size={20} />
                <h2 className="text-sm uppercase tracking-[0.2em] font-black">Veredicto Dalio</h2>
              </div>
              <div className="flex-1 overflow-y-auto custom-scrollbar">
                <p className="text-xl leading-relaxed font-black gold-gradient italic mb-4">
                  "{analysis.final_verdict}"
                </p>
                {analysis.dalio_response?.summary_table && (
                  <div className="prose prose-invert prose-xs max-w-none prose-table:border prose-table:border-[#d4af37]/20 prose-td:p-2 prose-th:p-2 bg-black/20 p-4 rounded-lg">
                    <div dangerouslySetInnerHTML={{ __html: analysis.dalio_response.summary_table.replace(/\n/g, '<br/>') }} />
                  </div>
                )}
              </div>
              <div className="mt-6 pt-6 border-t border-[#d4af37]/20 flex justify-between items-center">
                <span className="text-xs text-gray-500 uppercase">Decision Orchestrator</span>
                <span className="text-[#d4af37] font-mono text-sm">Gemini 3 Pro</span>
              </div>
            </section>
          </div>

          {/* Middle Section: Fundamental Engine & TradingView Technicals */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-3 space-y-4">
              <div className="flex items-center gap-2">
                <ShieldCheck size={18} className="text-[#d4af37]" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-gray-400">Motor Fundamental Determinístico</h3>
              </div>
              <FundamentalTable engine={analysis.fundamental_metrics} />
            </div>
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <TrendingUp size={18} className="text-[#d4af37]" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-gray-400">TV Validation</h3>
              </div>
              <div className="glass-card p-6 border-[#30363d] bg-[#0d1117]/40">
                <TradingViewTechnicalWidget symbol={analysis.ticker} />
              </div>
            </div>
          </div>

          {/* Graphs Section */}
          <div className="grid grid-cols-1 gap-6">
            <section className="glass-card p-6 border-[#30363d]">
              <div className="flex items-center gap-2 mb-6">
                <BarChart3 size={18} className="text-[#d4af37]" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-gray-400">Flujo de Caja vs Ingresos</h3>
              </div>
              <CashFlowChart data={analysis.chart_data?.cashflow || []} />
            </section>
          </div>

          {/* Master Minds Section: 8 Agents Grid */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Activity size={18} className="text-[#d4af37]" />
              <h3 className="text-sm font-bold uppercase tracking-widest text-gray-400">Comité de 8 Mentes Maestras</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {(analysis.agent_responses || []).slice(0, 8).map((agent: AgentSignal) => (
                <div key={agent.agent_name} className="agent-card glass-card p-5 border-[#30363d] flex flex-col h-[320px] hover:border-[#d4af37]/50 transition-colors group">
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="font-black text-base group-hover:text-[#d4af37] transition-colors">{agent.agent_name}</h3>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-black tracking-tighter ${['BUY', 'AGRESSIVE'].includes(agent.signal) ? 'bg-green-500/10 text-green-400' :
                      ['SELL', 'DEFENSIVE'].includes(agent.signal) ? 'bg-red-500/10 text-red-400' :
                        'bg-gray-500/10 text-gray-400'
                      }`}>
                      {agent.signal}
                    </span>
                  </div>
                  <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
                    <p className="text-[11px] text-gray-400 leading-relaxed text-pretty mb-3">
                      {agent.analysis}
                    </p>
                    {agent.selected_metrics && agent.selected_metrics.length > 0 && (
                      <div className="space-y-1">
                        <span className="text-[8px] font-black text-[#d4af37] uppercase tracking-widest">Métricas Priorizadas</span>
                        <div className="flex flex-wrap gap-1">
                          {agent.selected_metrics.map((m: any, idx: number) => {
                            const label = typeof m === 'string' ? m : (m.metric || m.name || `Metric ${idx}`);
                            const tooltip = typeof m === 'object' ? (m.justification || m.reason) : null;
                            return (
                              <span
                                key={idx}
                                title={tooltip}
                                className="px-1.5 py-0.5 bg-[#d4af37]/10 text-[#f9e29c] rounded-sm text-[8px] font-mono border border-[#d4af37]/20 cursor-help"
                              >
                                {label}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="mt-4 pt-3 border-t border-[#30363d] flex justify-between items-center bg-[#0d1117]/50 -mx-5 -mb-5 p-4 rounded-b-xl">
                    <span className="text-[9px] text-gray-500 uppercase font-bold tracking-widest">Confidence</span>
                    <div className="flex items-center gap-2">
                      <div className="w-12 h-1 bg-[#161b22] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#d4af37]"
                          style={{ width: `${agent.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-[9px] font-mono text-[#d4af37]">{(agent.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {!analysis && !loading && (
        <div className="flex flex-col items-center justify-center h-[60vh] text-center">
          <div className="w-24 h-24 bg-[#161b22] rounded-3xl flex items-center justify-center mb-8 border border-[#30363d]">
            <Activity size={48} className="text-[#d4af37]/20" />
          </div>
          <h2 className="text-2xl font-bold mb-4">Investment Analysis Engine</h2>
          <p className="text-gray-500 max-w-md mx-auto leading-relaxed">
            Ready to deploy deep fundamental and macro analysis. Enter a symbol to activate the Multi-Agent orchestrator.
          </p>
          <div className="mt-8 flex gap-4 text-xs font-mono text-gray-600">
            <span className="flex items-center gap-1"><ShieldCheck size={14} /> Fundamental</span>
            <span className="flex items-center gap-1"><Search size={14} /> Web Search</span>
            <span className="flex items-center gap-1"><Zap size={14} /> Real-time</span>
          </div>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center h-[60vh]">
          <div className="relative">
            <div className="w-20 h-20 border-4 border-[#d4af37]/20 border-t-[#d4af37] rounded-full animate-spin"></div>
            <Activity className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[#d4af37]" size={24} />
          </div>
          <p className="mt-6 text-[#d4af37] font-bold animate-pulse tracking-widest text-sm uppercase">
            Sincronizando Mentes Maestras...
          </p>
        </div>
      )}
    </main>
  );
}
