import { Database, User } from 'lucide-react';

export default function EMRSimulator() {
  return (
    <div className="flex flex-col h-full w-full bg-slate-100 border border-slate-300 rounded-lg overflow-hidden font-sans">
      <div className="h-12 bg-blue-900 border-b border-blue-950 flex items-center px-4 shrink-0 shadow-md z-10">
        <div className="w-6 h-6 bg-white rounded flex items-center justify-center mr-3">
            <Database className="w-4 h-4 text-blue-900" />
        </div>
        <h2 className="text-xs font-bold uppercase text-white tracking-widest drop-shadow-md">
          Sistema HIS/EMR Simulado (Clínica-Core v5.2)
        </h2>
      </div>
      <div className="flex-1 p-4 bg-slate-200 grid grid-cols-1 md:grid-cols-4 gap-4 overflow-y-auto">
        {/* Pacientes Activos */}
        <div className="bg-white rounded-md shadow-md p-4 text-slate-800 flex flex-col md:col-span-1 border border-slate-300">
           <h3 className="text-[10px] font-bold uppercase text-slate-500 mb-3 border-b-2 border-slate-100 pb-2 tracking-wider">Pacientes en Espera</h3>
           <div className="space-y-3 flex-1 overflow-y-auto pr-1">
              <div className="bg-red-50 p-3 rounded-md border border-red-200 shadow-sm relative overflow-hidden">
                <div className="absolute left-0 top-0 bottom-0 w-1 bg-red-500"></div>
                <div className="flex justify-between items-start mb-1">
                   <span className="text-xs font-bold text-slate-900">Juan Pérez</span>
                   <span className="px-1.5 py-0.5 bg-red-600 text-white text-[9px] font-bold rounded shadow-sm">ESI-2</span>
                </div>
                <span className="text-[9px] text-slate-500 uppercase block font-medium">Ingresado via FHIR API</span>
              </div>
           </div>
        </div>
        {/* Detalle Clínico */}
        <div className="bg-white rounded-md shadow-md p-5 text-slate-800 md:col-span-3 border border-slate-300 flex flex-col">
           <h3 className="text-xs font-bold uppercase text-blue-900 mb-4 border-b-2 border-slate-100 pb-2 flex items-center gap-2"><User className="w-4 h-4 text-blue-600" /> Pantalla de Enfermería / Detalle Clínico</h3>
           <div className="flex-1">
              <div className="grid grid-cols-2 gap-6 mb-6 bg-slate-50 p-4 rounded-md border border-slate-200">
                 <div>
                    <label className="text-[9px] uppercase text-slate-500 font-bold tracking-wider mb-1 block">Nombre del Paciente</label>
                    <div className="text-sm font-bold text-slate-900">Juan Pérez</div>
                 </div>
                 <div>
                    <label className="text-[9px] uppercase text-slate-500 font-bold tracking-wider mb-1 block">Motivo de Consulta (NER Extracted)</label>
                    <div className="text-sm text-slate-700 font-medium">Dolor torácico opresivo, diaforesis.</div>
                 </div>
              </div>
              <div>
                  <label className="text-[9px] uppercase text-slate-500 font-bold tracking-wider mb-2 block flex items-center gap-2">Anotaciones de Triaje Automático <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-[8px]">AI GENERATED</span></label>
                  <div className="bg-blue-50/50 p-4 rounded-md border border-blue-100 text-sm text-slate-700 italic leading-relaxed">
                     Paciente varón presenta sintomatología compatible con síndrome coronario agudo (SCA). La irradiación del dolor a mandíbula y la diaforesis asociada categorizan el riesgo como Nivel 2.
                  </div>
              </div>
           </div>
           <div className="mt-6 pt-4 border-t border-slate-200 flex justify-end">
             <button className="bg-blue-700 text-white px-5 py-2 rounded-md text-[10px] uppercase font-bold shadow-md hover:bg-blue-800 transition tracking-widest">Aceptar y Asignar Box</button>
           </div>
        </div>
      </div>
    </div>
  );
}
