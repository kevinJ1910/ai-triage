'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Stethoscope, Settings, Shield, RefreshCw, Server, Database, BarChart, ChevronLeft, ChevronRight, LogOut } from 'lucide-react';
import TriageDashboard from '@/components/TriageDashboard';
import ConfigPanel from '@/components/ConfigPanel';
import SecurityPanel from '@/components/SecurityPanel';
import NormalizationMonitor from '@/components/NormalizationMonitor';
import FHIRMonitor from '@/components/FHIRMonitor';
import EMRSimulator from '@/components/EMRSimulator';
import MetricsDashboard from '@/components/MetricsDashboard';
import { Toaster } from 'sonner';

export default function AppNavigation() {
  const [activeTab, setActiveTab] = useState('triage');
  const [isCollapsed, setIsCollapsed] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
    }
  }, [router]);

  const navItems = [
    { id: 'triage', icon: <Stethoscope className="w-5 h-5"/>, label: 'Modulos Core (Triaje)' },
    { id: 'config', icon: <Settings className="w-5 h-5"/>, label: 'Configuración' },
    { id: 'security', icon: <Shield className="w-5 h-5"/>, label: 'Seguridad (RBAC)' },
    { id: 'normalization', icon: <RefreshCw className="w-5 h-5"/>, label: 'Monitor Normalización' },
    { id: 'fhir', icon: <Server className="w-5 h-5"/>, label: 'Monitor FHIR/HL7' },
    { id: 'emr', icon: <Database className="w-5 h-5"/>, label: 'Simulador HCE' },
    { id: 'metrics', icon: <BarChart className="w-5 h-5"/>, label: 'Métricas y Evaluación' },
  ];

  return (
    <div className="flex h-full w-full bg-slate-950 text-slate-200 font-sans overflow-hidden">
      {/* Sidebar Navigation */}
      <aside className={`${isCollapsed ? 'w-16' : 'w-16 md:w-56'} bg-slate-900 border-r border-slate-800 flex flex-col shrink-0 transition-all duration-300 z-10`}>
        <div className="h-14 border-b border-slate-800 flex items-center justify-center md:justify-start px-0 md:px-4 shrink-0 overflow-hidden">
          <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center shrink-0">
            <span className="font-bold text-white tracking-tighter">AI</span>
          </div>
          <span className={`ml-3 font-semibold tracking-tight uppercase text-sm truncate transition-opacity duration-300 ${isCollapsed ? 'opacity-0 hidden md:hidden' : 'opacity-100 hidden md:inline'}`}>AI-Triage</span>
        </div>
        <nav className="flex-1 py-4 flex flex-col gap-1 px-2 overflow-y-auto overflow-x-hidden">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`flex items-center justify-center md:justify-start gap-3 p-2.5 rounded transition-all group ${
                activeTab === item.id 
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30' 
                : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300 border border-transparent'
              }`}
              title={isCollapsed ? item.label : undefined}
            >
              <div className="shrink-0">{item.icon}</div>
              <span className={`text-[10px] font-bold uppercase tracking-widest truncate transition-opacity duration-300 ${isCollapsed ? 'opacity-0 hidden md:hidden' : 'opacity-100 hidden md:inline'}`}>
                {item.label}
              </span>
            </button>
          ))}
        </nav>
        {/* Bottom Actions */}
        <div className="p-2 border-t border-slate-800 flex flex-col items-center justify-center md:justify-start shrink-0 gap-1">
          <button 
            onClick={() => {
              localStorage.removeItem('access_token');
              localStorage.removeItem('refresh_token');
              router.push('/login');
            }}
            className="flex items-center justify-center md:justify-start gap-3 p-2.5 w-full rounded text-red-400 hover:bg-red-950/30 hover:text-red-300 transition-all"
            title={isCollapsed ? "Cerrar Sesión" : "Cerrar Sesión"}
          >
            <div className="shrink-0"><LogOut className="w-5 h-5"/></div>
            <span className={`text-[10px] font-bold uppercase tracking-widest truncate transition-opacity duration-300 ${isCollapsed ? 'opacity-0 hidden md:hidden' : 'opacity-100 hidden md:inline'}`}>
              Cerrar Sesión
            </span>
          </button>
        </div>
        <div className="p-2 border-t border-slate-800 flex items-center justify-center md:justify-start shrink-0">
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="flex items-center justify-center md:justify-start gap-3 p-2.5 w-full rounded text-slate-500 hover:bg-slate-800 hover:text-slate-300 transition-all"
            title={isCollapsed ? "Expandir" : "Colapsar"}
          >
            <div className="shrink-0">
              {isCollapsed ? <ChevronRight className="w-5 h-5"/> : <ChevronLeft className="w-5 h-5"/>}
            </div>
            <span className={`text-[10px] font-bold uppercase tracking-widest truncate transition-opacity duration-300 ${isCollapsed ? 'opacity-0 hidden md:hidden' : 'opacity-100 hidden md:inline'}`}>
              Contraer
            </span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-slate-950 p-2 md:p-3">
        <Toaster theme="dark" position="top-right" richColors />
        {activeTab === 'triage' && <TriageDashboard />}
        {activeTab === 'config' && <ConfigPanel />}
        {activeTab === 'security' && <SecurityPanel />}
        {activeTab === 'normalization' && <NormalizationMonitor />}
        {activeTab === 'fhir' && <FHIRMonitor />}
        {activeTab === 'emr' && <EMRSimulator />}
        {activeTab === 'metrics' && <MetricsDashboard />}
      </div>
    </div>
  );
}
