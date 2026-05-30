import { BarChart, Percent, ShieldCheck, Zap } from 'lucide-react';

export default function MetricsDashboard() {
  return (
    <div className="flex flex-col h-full w-full bg-slate-900 border border-slate-700 rounded-lg p-4 overflow-y-auto">
      <h2 className="text-xs font-bold uppercase text-slate-300 tracking-widest flex items-center gap-2 mb-4 shrink-0">
        <BarChart className="w-4 h-4 text-emerald-400" />
        Dashboard de Métricas y Evaluación
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        {/* Technical Metrics */}
        <div className="bg-slate-800/50 rounded border border-slate-700 p-4">
          <div className="text-[10px] font-bold uppercase text-slate-400 tracking-widest flex items-center gap-1.5"><Zap className="w-3 h-3 text-amber-400"/> Latencia ASR</div>
          <div className="text-3xl font-mono text-white mt-3 font-bold">1.2<span className="text-sm text-slate-500 font-sans font-normal ml-1">seg</span></div>
          <div className="text-[9px] text-emerald-400 mt-2 uppercase font-bold flex justify-between items-center">
            <span>Objetivo &lt; 2.0s</span>
            <span className="px-1 py-0.5 bg-emerald-500/20 rounded">OK</span>
          </div>
        </div>
        <div className="bg-slate-800/50 rounded border border-slate-700 p-4">
          <div className="text-[10px] font-bold uppercase text-slate-400 tracking-widest flex items-center gap-1.5"><Percent className="w-3 h-3 text-red-400"/> WER (Word Error Rate)</div>
          <div className="text-3xl font-mono text-white mt-3 font-bold">8.4<span className="text-sm text-slate-500 font-sans font-normal ml-1">%</span></div>
          <div className="text-[9px] text-emerald-400 mt-2 uppercase font-bold flex justify-between items-center">
            <span>Objetivo &lt; 15%</span>
            <span className="px-1 py-0.5 bg-emerald-500/20 rounded">OK</span>
          </div>
        </div>
        <div className="bg-slate-800/50 rounded border border-slate-700 p-4">
          <div className="text-[10px] font-bold uppercase text-slate-400 tracking-widest flex items-center gap-1.5"><BarChart className="w-3 h-3 text-indigo-400"/> F1-Score NER</div>
          <div className="text-3xl font-mono text-white mt-3 font-bold">0.89</div>
          <div className="text-[9px] text-emerald-400 mt-2 uppercase font-bold flex justify-between items-center">
            <span>Objetivo &gt; 0.85</span>
            <span className="px-1 py-0.5 bg-emerald-500/20 rounded">OK</span>
          </div>
        </div>
        <div className="bg-slate-800/50 rounded border border-slate-700 p-4">
          <div className="text-[10px] font-bold uppercase text-slate-400 tracking-widest flex items-center gap-1.5"><ShieldCheck className="w-3 h-3 text-blue-400"/> Índice Kappa</div>
          <div className="text-3xl font-mono text-white mt-3 font-bold">0.92</div>
          <div className="text-[9px] text-emerald-400 mt-2 uppercase font-bold flex justify-between items-center">
            <span>Concordancia Humano-IA</span>
            <span className="px-1 py-0.5 bg-emerald-500/20 rounded">ALTA</span>
          </div>
        </div>
      </div>
      <div className="flex-1 bg-slate-800/50 rounded border border-slate-700 p-4 flex flex-col min-h-[200px]">
        <h3 className="text-[10px] uppercase font-bold text-slate-400 mb-4 tracking-widest">Evaluación Clínica (Calidad de la Justificación)</h3>
        {/* Simple Bar Chart Visualization */}
        <div className="flex-1 flex items-end gap-6 p-4 h-full border-b border-l border-slate-600 ml-4 pb-8 relativr">
           <div className="relative w-full max-w-xs bg-blue-600 hover:bg-blue-500 transition-colors rounded-t h-[95%] text-center group border border-blue-500/50 shadow-[inset_0_4px_10px_rgba(255,255,255,0.2)]">
              <span className="absolute -top-7 left-1/2 -translate-x-1/2 text-xs font-mono font-bold text-white">95%</span>
              <span className="absolute -bottom-7 w-full text-center text-[10px] text-slate-400 uppercase font-bold">Precisión Clínica R4</span>
           </div>
           <div className="relative w-full max-w-xs bg-indigo-600 hover:bg-indigo-500 transition-colors rounded-t h-[82%] text-center group border border-indigo-500/50 shadow-[inset_0_4px_10px_rgba(255,255,255,0.2)]">
              <span className="absolute -top-7 left-1/2 -translate-x-1/2 text-xs font-mono font-bold text-white">82%</span>
              <span className="absolute -bottom-7 w-full text-center text-[10px] text-slate-400 uppercase font-bold">Claridad Explicativa</span>
           </div>
           <div className="relative w-full max-w-xs bg-emerald-600 hover:bg-emerald-500 transition-colors rounded-t h-[89%] text-center group border border-emerald-500/50 shadow-[inset_0_4px_10px_rgba(255,255,255,0.2)]">
              <span className="absolute -top-7 left-1/2 -translate-x-1/2 text-xs font-mono font-bold text-white">89%</span>
              <span className="absolute -bottom-7 w-full text-center text-[10px] text-slate-400 uppercase font-bold">Completitud FHIR</span>
           </div>
        </div>
      </div>
    </div>
  );
}
