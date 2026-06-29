import { Database, Settings, Upload } from 'lucide-react';

export default function ConfigPanel() {
  return (
    <div className="flex flex-col h-full w-full bg-slate-900 border border-slate-700 rounded-lg p-4 overflow-y-auto">
      <h2 className="text-xs font-bold uppercase text-slate-300 tracking-widest flex items-center gap-2 mb-4 shrink-0">
        <Settings className="w-4 h-4 text-blue-400" />
        Gestión y Configuración
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Model Management */}
        <div className="bg-slate-800/50 rounded border border-slate-700 p-4">
          <h3 className="text-[10px] uppercase font-bold text-slate-400 mb-3 tracking-widest">Gestión de Modelos IA</h3>
          <div className="space-y-4">
            <div>
              <label className="text-[10px] text-slate-500 uppercase block mb-1">Modelo NER Principal</label>
              <select className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500">
                <option>ClinicalBERT (v2.1 - Recomendado)</option>
                <option>BioBERT (v1.5 - Legacy)</option>
                <option>PubMedBERT (Experimental)</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] text-slate-500 uppercase block mb-1">Motor ASR (Local)</label>
              <select className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500">
                <option>Faster-Whisper (es-medical-v4)</option>
                <option>Whisper Large V3</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] text-slate-500 uppercase block mb-1">Motor de Explicabilidad (LLM)</label>
              <select className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500">
                <option>Gemini 2.5 Flash</option>
                <option>GPT-4o-mini</option>
              </select>
            </div>
          </div>
        </div>
        
        {/* Vocabularies */}
        <div className="bg-slate-800/50 rounded border border-slate-700 p-4 flex flex-col">
          <h3 className="text-[10px] uppercase font-bold text-slate-400 mb-3 tracking-widest block shrink-0">Actualización de Vocabularios</h3>
          <div className="space-y-4 flex-1">
            <div className="flex items-center justify-between p-3 bg-slate-900 rounded border border-slate-700">
              <div>
                <span className="text-xs font-medium block text-slate-200">SNOMED CT (Edición en Español)</span>
                <span className="text-[9px] text-slate-500">Última actualización: 12 Oct 2025</span>
              </div>
              <button className="bg-blue-600/20 text-blue-400 border border-blue-500/50 px-3 py-1.5 rounded text-[10px] font-bold uppercase flex items-center gap-1.5 transition-colors hover:bg-blue-600/40">
                <Upload className="w-3 h-3" /> Cargar
              </button>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-900 rounded border border-slate-700">
              <div>
                <span className="text-xs font-medium block text-slate-200">ICD-10 (CIE-10)</span>
                <span className="text-[9px] text-slate-500">Última actualización: 05 Ene 2026</span>
              </div>
              <button className="bg-blue-600/20 text-blue-400 border border-blue-500/50 px-3 py-1.5 rounded text-[10px] font-bold uppercase flex items-center gap-1.5 transition-colors hover:bg-blue-600/40">
                <Upload className="w-3 h-3" /> Cargar
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
