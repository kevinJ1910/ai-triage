'use client';

import React, { useState, useEffect } from 'react';
import { 
  Stethoscope, 
  Settings, 
  Shield, 
  RefreshCw, 
  Server, 
  Database, 
  BarChart, 
  LogOut, 
  ChevronLeft, 
  ChevronRight,
  Menu,
  X
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Toaster } from 'sonner';

import TriageDashboard from '@/components/TriageDashboard';
import ConfigPanel from '@/components/ConfigPanel';
import SecurityPanel from '@/components/SecurityPanel';
import NormalizationMonitor from '@/components/NormalizationMonitor';
import FHIRMonitor from '@/components/FHIRMonitor';
import EMRSimulator from '@/components/EMRSimulator';
import MetricsDashboard from '@/components/MetricsDashboard';

interface UserProfile {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: string;
  permissions: {
    can_use_transcriber: boolean;
    can_edit_symptoms: boolean;
    can_register_patients: boolean;
    can_view_emr: boolean;
    can_view_fhir: boolean;
    can_manage_config: boolean;
  };
}

export default function AppNavigation() {
  const [activeTab, setActiveTab] = useState<string>('triage');
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [isAuthChecking, setIsAuthChecking] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }

    // Validar token en backend y sincronizar perfil de usuario
    fetch('/api/auth/me/', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })
      .then(res => {
        if (!res.ok) {
          throw new Error('Sesion invalida o expirada');
        }
        return res.json();
      })
      .then(user => {
        setCurrentUser(user);
        localStorage.setItem('user_profile', JSON.stringify(user));
        setIsAuthChecking(false);
      })
      .catch(() => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_profile');
        router.push('/login');
      });
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_profile');
    router.push('/login');
  };

  if (isAuthChecking) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950 text-slate-200">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs font-mono uppercase tracking-widest text-slate-400">Verificando sesion medica...</p>
        </div>
      </div>
    );
  }

  const navItems = [
    // Flujo Clinico y Gestion de Pacientes
    { id: 'triage', icon: <Stethoscope className="w-5 h-5"/>, label: 'Modulo de Triaje', category: 'clinical' },
    { id: 'emr', icon: <Database className="w-5 h-5"/>, label: 'Simulador HCE', category: 'clinical' },
    // Interoperabilidad y Evaluacion IA
    { id: 'normalization', icon: <RefreshCw className="w-5 h-5"/>, label: 'Monitor Normalizacion', category: 'clinical' },
    { id: 'fhir', icon: <Server className="w-5 h-5"/>, label: 'Monitor FHIR/HL7', category: 'clinical' },
    { id: 'metrics', icon: <BarChart className="w-5 h-5"/>, label: 'Metricas y Evaluacion', category: 'clinical' },
    // Administracion y Parametrizacion del Sistema
    { id: 'security', icon: <Shield className="w-5 h-5"/>, label: 'Seguridad y RBAC', category: 'admin' },
    { id: 'config', icon: <Settings className="w-5 h-5"/>, label: 'Configuracion', category: 'admin' },
  ];

  const currentActiveItem = navItems.find(i => i.id === activeTab);

  return (
    <div className="flex flex-col md:flex-row h-full w-full bg-slate-950 text-slate-200 font-sans overflow-hidden">
      {/* Mobile Top Header */}
      <header className="md:hidden h-14 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-3 shrink-0 z-30">
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setMobileMenuOpen(true)}
            aria-label="Abrir menu de navegacion"
            className="p-2 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-blue-600 rounded flex items-center justify-center shrink-0 shadow-sm">
              <span className="font-bold text-white text-xs tracking-tighter">AI</span>
            </div>
            <span className="font-semibold text-xs text-slate-100 truncate">
              {currentActiveItem?.label || 'AI-Triage'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-xs shadow-sm">
            {currentUser?.first_name ? currentUser.first_name[0].toUpperCase() : 'U'}
          </div>
        </div>
      </header>

      {/* Mobile Drawer Backdrop & Menu */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Backdrop */}
          <div 
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />

          {/* Drawer Content */}
          <div className="fixed inset-y-0 left-0 w-72 max-w-[85vw] bg-slate-900 border-r border-slate-800 flex flex-col p-4 shadow-2xl z-50">
            {/* Drawer Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center shrink-0 shadow-md shadow-blue-600/30">
                  <span className="font-bold text-white tracking-tighter">AI</span>
                </div>
                <span className="font-bold tracking-tight uppercase text-sm text-slate-100">
                  AI-Triage
                </span>
              </div>
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Mobile User Profile Card */}
            <div className="py-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5 p-2 rounded-lg bg-slate-950/60 border border-slate-800">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-xs shrink-0">
                  {currentUser?.first_name ? currentUser.first_name[0].toUpperCase() : 'U'}
                </div>
                <div className="overflow-hidden">
                  <div className="text-xs font-semibold text-slate-100 truncate">
                    {currentUser?.full_name || 'Personal Medico'}
                  </div>
                  <div className="text-[10px] text-emerald-400 font-mono uppercase tracking-wider font-bold">
                    {currentUser?.role || 'Medico'}
                  </div>
                </div>
              </div>
            </div>

            {/* Navigation Items in Drawer */}
            <nav className="flex-1 py-3 flex flex-col gap-1 overflow-y-auto">
              {navItems.map(item => {
                const isActive = activeTab === item.id;
                return (
                  <React.Fragment key={item.id}>
                    {item.id === 'security' && (
                      <div className="my-2 pt-2 border-t border-slate-800">
                        <span className="px-3 pb-1 text-[10px] font-mono uppercase tracking-wider text-slate-500 font-bold block">
                          Administracion del Sistema
                        </span>
                      </div>
                    )}
                    <button
                      onClick={() => {
                        setActiveTab(item.id);
                        setMobileMenuOpen(false);
                      }}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all ${
                        isActive 
                          ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20' 
                          : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                      }`}
                    >
                      <div className="shrink-0">{item.icon}</div>
                      <span className="text-xs tracking-wide">
                        {item.label}
                      </span>
                    </button>
                  </React.Fragment>
                );
              })}
            </nav>

            {/* Logout button at bottom of mobile drawer */}
            <div className="pt-3 border-t border-slate-800">
              <button 
                onClick={handleLogout}
                className="flex items-center gap-3 p-2.5 w-full rounded-lg text-red-400 hover:bg-red-950/30 hover:text-red-300 transition-all border border-transparent hover:border-red-900/50"
              >
                <LogOut className="w-5 h-5 shrink-0" />
                <span className="text-xs font-bold uppercase tracking-wider">
                  Cerrar Sesion
                </span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Desktop Sidebar Navigation */}
      <aside className={`hidden md:flex ${isCollapsed ? 'w-16' : 'w-56'} bg-slate-900 border-r border-slate-800 flex-col shrink-0 transition-all duration-300 z-10`}>
        <div className="h-14 border-b border-slate-800 flex items-center justify-center md:justify-start px-0 md:px-4 shrink-0 overflow-hidden">
          <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center shrink-0 shadow-md shadow-blue-600/30">
            <span className="font-bold text-white tracking-tighter">AI</span>
          </div>
          <span className={`ml-3 font-semibold tracking-tight uppercase text-sm truncate transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
            AI-Triage
          </span>
        </div>

        {/* Current User Badge in Desktop Sidebar */}
        <div className="p-2 border-b border-slate-800/80 bg-slate-950/40">
          <div className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg bg-slate-800/50 border border-slate-700/60">
            <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center shrink-0 text-white font-bold text-xs shadow-sm">
              {currentUser?.first_name ? currentUser.first_name[0].toUpperCase() : 'U'}
            </div>
            <div className={`overflow-hidden transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
              <div className="text-xs font-semibold text-slate-200 truncate leading-tight">
                {currentUser?.full_name || 'Personal Medico'}
              </div>
              <div className="text-[10px] text-emerald-400 font-mono uppercase tracking-wider font-bold">
                {currentUser?.role || 'Medico'}
              </div>
            </div>
          </div>
        </div>

        <nav className="flex-1 py-3 flex flex-col gap-1 px-2 overflow-y-auto overflow-x-hidden">
          {navItems.map(item => {
            const isActive = activeTab === item.id;
            return (
              <React.Fragment key={item.id}>
                {item.id === 'security' && (
                  <div className="my-2 pt-2 border-t border-slate-800">
                    <span className={`px-2 pb-1 text-[9px] font-mono uppercase tracking-wider text-slate-500 font-bold block ${isCollapsed ? 'hidden' : 'block'}`}>
                      Administracion
                    </span>
                  </div>
                )}
                <button
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center justify-center md:justify-start gap-3 p-2.5 rounded transition-all group ${
                    isActive 
                      ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20' 
                      : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                  }`}
                  title={isCollapsed ? item.label : undefined}
                >
                  <div className="shrink-0">{item.icon}</div>
                  <span className={`text-[10px] font-bold uppercase tracking-widest truncate transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
                    {item.label}
                  </span>
                </button>
              </React.Fragment>
            );
          })}
        </nav>

        {/* Bottom Actions */}
        <div className="p-2 border-t border-slate-800 flex flex-col items-center justify-center md:justify-start shrink-0 gap-1">
          <button 
            onClick={handleLogout}
            className="flex items-center justify-center md:justify-start gap-3 p-2.5 w-full rounded text-red-400 hover:bg-red-950/30 hover:text-red-300 transition-all border border-transparent hover:border-red-900/50"
            title="Cerrar Sesion"
          >
            <div className="shrink-0"><LogOut className="w-5 h-5"/></div>
            <span className={`text-[10px] font-bold uppercase tracking-widest truncate transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
              Cerrar Sesion
            </span>
          </button>
        </div>

        <div className="p-2 border-t border-slate-800 flex items-center justify-center md:justify-start shrink-0">
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="flex items-center justify-center md:justify-start gap-3 p-2.5 w-full rounded text-slate-500 hover:bg-slate-800 hover:text-slate-300 transition-all"
            title={isCollapsed ? "Expandir" : "Contraer"}
          >
            <div className="shrink-0">
              {isCollapsed ? <ChevronRight className="w-5 h-5"/> : <ChevronLeft className="w-5 h-5"/>}
            </div>
            <span className={`text-[10px] font-bold uppercase tracking-widest truncate transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
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
