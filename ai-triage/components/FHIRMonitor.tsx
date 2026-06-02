import { Server, CheckCircle2, Clock } from 'lucide-react';

export default function FHIRMonitor() {
  return (
    <div className="flex flex-col h-full w-full bg-slate-900 border border-slate-700 rounded-lg p-4 overflow-y-auto">
      <h2 className="text-xs font-bold uppercase text-slate-300 tracking-widest flex items-center gap-2 mb-4 shrink-0">
        <Server className="w-4 h-4 text-orange-400" />
        Monitor de Interoperabilidad (FHIR R4)
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 h-full min-h-[350px]">
        <div className="md:col-span-1 bg-slate-800/50 rounded border border-slate-700 p-4 flex flex-col min-h-0">
          <h3 className="text-[10px] uppercase font-bold text-slate-400 mb-3 tracking-widest shrink-0">Historial de Envíos</h3>
          <div className="space-y-2 flex-1 overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-700">
            {[1,2,3].map((i) => (
              <div key={i} className={`p-2.5 rounded border transition-colors ${i === 1 ? 'bg-slate-700/80 border-blue-500/50 shadow-md' : 'bg-slate-900 border-slate-700 hover:border-slate-500'} cursor-pointer`}>
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-[10px] font-mono font-bold text-slate-300">REQ-8{i}92</span>
                  <span className="text-[9px] px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 rounded font-bold border border-emerald-500/30">201 Created</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[9px] text-slate-500 font-mono uppercase">Resource: Encounter</span>
                  <span className="text-[9px] text-slate-500 flex items-center gap-1"><Clock className="w-2.5 h-2.5"/> 12:4{i} PM</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="md:col-span-2 bg-slate-800/50 rounded border border-slate-700 p-4 flex flex-col min-h-0">
          <h3 className="text-[10px] uppercase font-bold text-slate-400 mb-3 tracking-widest flex justify-between items-center shrink-0">
            <span>Payload R4 (Último Envío)</span>
            <span className="text-emerald-400 flex items-center gap-1.5 bg-emerald-500/10 px-2 py-1 rounded border border-emerald-500/30"><CheckCircle2 className="w-3 h-3" /> Validado vs Schema</span>
          </h3>
          <pre className="flex-1 bg-slate-950 p-4 border border-slate-700 rounded text-[10px] sm:text-xs font-mono text-blue-300 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
{`{
  "resourceType": "Encounter",
  "status": "arrived",
  "class": {
    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
    "code": "EMER",
    "display": "Emergency"
  },
  "priority": {
    "coding": [
      {
        "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
        "code": "L2",
        "display": "Emergencia"
      }
    ]
  },
  "reasonCode": [
    {
      "coding": [
        {
          "system": "http://snomed.info/sct",
          "code": "29857009",
          "display": "Chest pain"
        }
      ]
    }
  ]
}`}
          </pre>
        </div>
      </div>
    </div>
  );
}
