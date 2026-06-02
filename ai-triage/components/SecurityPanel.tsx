import { Shield, Users, FileLock2 } from 'lucide-react';

export default function SecurityPanel() {
  return (
    <div className="flex flex-col h-full w-full bg-slate-900 border border-slate-700 rounded-lg p-4 overflow-y-auto">
      <h2 className="text-xs font-bold uppercase text-slate-300 tracking-widest flex items-center gap-2 mb-4 shrink-0">
        <Shield className="w-4 h-4 text-emerald-400" />
        Seguridad y Roles (RBAC)
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Usuarios y Roles */}
        <div className="bg-slate-800/50 rounded border border-slate-700 p-4">
          <h3 className="text-[10px] uppercase font-bold text-slate-400 mb-3 tracking-widest flex items-center gap-1.5"><Users className="w-3 h-3 text-blue-400"/> Control de Acceso</h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between p-2.5 bg-slate-900/50 border border-slate-700 rounded">
              <div>
                <span className="text-xs font-medium block text-slate-200">Dr. Rodriguez</span>
                <span className="text-[9px] font-mono text-slate-500">ID: USR-8492</span>
              </div>
              <span className="text-[9px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/50 uppercase font-bold tracking-widest">Médico</span>
            </div>
            <div className="flex items-center justify-between p-2.5 bg-slate-900/50 border border-slate-700 rounded">
              <div>
                <span className="text-xs font-medium block text-slate-200">Enf. Martinez</span>
                <span className="text-[9px] font-mono text-slate-500">ID: USR-1023</span>
              </div>
              <span className="text-[9px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 uppercase font-bold tracking-widest">Triaje</span>
            </div>
            <div className="flex items-center justify-between p-2.5 bg-slate-900/50 border border-slate-700 rounded">
              <div>
                <span className="text-xs font-medium block text-slate-200">SysAdmin</span>
                <span className="text-[9px] font-mono text-slate-500">ID: ADM-001</span>
              </div>
              <span className="text-[9px] px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/50 uppercase font-bold tracking-widest">Admin</span>
            </div>
          </div>
        </div>

        {/* Auditoría */}
        <div className="bg-slate-800/50 rounded border border-slate-700 p-4 flex flex-col">
          <h3 className="text-[10px] uppercase font-bold text-slate-400 mb-3 tracking-widest flex items-center gap-1.5"><FileLock2 className="w-3 h-3 text-purple-400"/> Logs de Auditoría (Ley 1581 HCE)</h3>
          <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-slate-600">
            {[
              { time: "2026-05-28 06:15:02", user: "USR-8492", action: "FHIR_EXPORT", resource: "Encounter/10923", status: "SUCCESS" },
              { time: "2026-05-28 06:10:45", user: "USR-8492", action: "READ_SESSION", resource: "Session/A491", status: "SUCCESS" },
              { time: "2026-05-28 06:05:12", user: "USR-1023", action: "MODEL_CONFIG_CHANGE", resource: "System", status: "DENIED" },
              { time: "2026-05-28 06:00:22", user: "ADM-001", action: "UPDATE_VOCABULARY", resource: "SNOMED CT", status: "SUCCESS" },
              { time: "2026-05-27 18:32:10", user: "USR-1023", action: "FHIR_EXPORT", resource: "Encounter/10922", status: "SUCCESS" }
            ].map((log, i) => (
              <div key={i} className="bg-slate-900 p-2 rounded border-l-2 border-slate-600 text-[10px] font-mono text-slate-300">
                <div className="flex justify-between mb-1">
                  <span className="text-slate-500">{log.time}</span>
                  <span className={`px-1.5 py-0.5 rounded font-bold ${log.status==='SUCCESS'?'bg-emerald-500/20 text-emerald-400':'bg-red-500/20 text-red-400'}`}>{log.status}</span>
                </div>
                <div><span className="text-blue-400">{log.user}</span> executed <span className="text-amber-400">{log.action}</span> on {log.resource}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
