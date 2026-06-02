import { RefreshCw, ArrowRight } from 'lucide-react';

export default function NormalizationMonitor() {
  return (
    <div className="flex flex-col h-full w-full bg-slate-900 border border-slate-700 rounded-lg p-4 overflow-y-auto">
      <h2 className="text-xs font-bold uppercase text-slate-300 tracking-widest flex items-center gap-2 mb-4 shrink-0">
        <RefreshCw className="w-4 h-4 text-purple-400" />
        Monitor de Normalización
      </h2>
      <div className="flex flex-col md:flex-row gap-4 h-full min-h-[300px]">
        <div className="flex-1 bg-slate-800/50 rounded border border-slate-700 p-4 flex flex-col">
          <h3 className="text-[10px] uppercase font-bold text-red-400 mb-3 tracking-widest shrink-0">Texto Crudo (ASR)</h3>
          <div className="flex-1 p-4 bg-slate-900 rounded border border-slate-700 font-serif text-sm sm:text-base leading-relaxed text-slate-300 italic overflow-y-auto">
            &quot;Siento que me <span className="text-red-300 underline decoration-red-500/50 underline-offset-4 bg-red-500/10 px-1 rounded">aprieta</span> el pecho y me <span className="text-red-300 underline decoration-red-500/50 underline-offset-4 bg-red-500/10 px-1 rounded">falta el aire</span>. Yo tomo posartán pa la <span className="text-red-300 underline decoration-red-500/50 underline-offset-4 bg-red-500/10 px-1 rounded">presión alta</span>...&quot;
          </div>
        </div>
        <div className="flex items-center justify-center shrink-0">
            <ArrowRight className="w-8 h-8 text-slate-600 hidden md:block" />
            <ArrowRight className="w-8 h-8 text-slate-600 block md:hidden rotate-90" />
        </div>
        <div className="flex-1 bg-slate-800/50 rounded border border-slate-700 p-4 flex flex-col">
          <h3 className="text-[10px] uppercase font-bold text-emerald-400 mb-3 tracking-widest shrink-0">Texto Normalizado</h3>
          <div className="flex-1 p-4 bg-slate-900 rounded border border-slate-700 font-serif text-sm sm:text-base leading-relaxed text-slate-200 italic overflow-y-auto">
            &quot;Siento <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-1.5 py-0.5 rounded font-bold not-italic font-sans text-xs mx-1">opresión torácica</span> y <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-1.5 py-0.5 rounded font-bold not-italic font-sans text-xs mx-1">disnea</span>. Yo tomo <span className="bg-blue-500/20 text-blue-300 border border-blue-500/30 px-1.5 py-0.5 rounded font-bold not-italic font-sans text-xs mx-1">losartán</span> para la <span className="bg-orange-500/20 text-orange-300 border border-orange-500/30 px-1.5 py-0.5 rounded font-bold not-italic font-sans text-xs mx-1">hipertensión arterial</span>...&quot;
          </div>
        </div>
      </div>
    </div>
  );
}
