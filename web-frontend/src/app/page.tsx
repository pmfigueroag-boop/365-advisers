"use client";

import { useState } from "react";
import { PriceChart, CashFlowChart } from "@/components/Charts";
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
}

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
                <h3 className="text-sm font-bold uppercase tracking-widest text-gray-400">Desempeño del Ticker</h3>
                <span className="text-xs text-[#d4af37] font-mono">{analysis.ticker} | 1Y History</span>
              </div>
              <PriceChart data={analysis.chart_data?.prices || []} />
            </section>

            {/* Final Verdict */}
            <section className="glass-card p-8 border-[#d4af37]/30 bg-[#d4af37]/5 flex flex-col">
              <div className="flex items-center gap-2 mb-4 text-[#d4af37]">
                <ShieldCheck size={20} />
                <h2 className="text-sm uppercase tracking-[0.2em] font-black">Veredicto Dalio</h2>
              </div>
              <div className="flex-1">
                <p className="text-xl leading-relaxed font-medium italic text-gray-200">
                  "{analysis.final_verdict}"
                </p>
              </div>
              <div className="mt-6 pt-6 border-t border-[#d4af37]/20 flex justify-between items-center">
                <span className="text-xs text-gray-500 uppercase">Decision Orchestrator</span>
                <span className="text-[#d4af37] font-mono text-sm">Gemini 3 Pro</span>
              </div>
            </section>
          </div>

          {/* Middle Section: Cash Flow Chart */}
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
                    <p className="text-[11px] text-gray-400 leading-relaxed text-pretty">
                      {agent.analysis}
                    </p>
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
