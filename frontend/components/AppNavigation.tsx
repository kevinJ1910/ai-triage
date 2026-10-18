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
  X,
  EyeOff,
  Activity,
  HeartPulse
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Toaster } from 'sonner';
import { fetchWithAuth, logout } from '@/lib/api';

import TriageDashboard from '@/components/TriageDashboard';
import ConfigPanel from '@/components/ConfigPanel';
import SecurityPanel from '@/components/SecurityPanel';
import NormalizationMonitor from '@/components/NormalizationMonitor';
import FHIRMonitor from '@/components/FHIRMonitor';
import EMRSimulator from '@/components/EMRSimulator';
import MetricsDashboard from '@/components/MetricsDashboard';
import BlindReview from '@/components/BlindReview';
import EngineStatus from '@/components/EngineStatus';

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
    // Validar sesion en backend (renueva el access token con la cookie httpOnly si hace falta)
    fetchWithAuth('/api/auth/me/', {
      headers: { 'Content-Type': 'application/json' }
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
        localStorage.removeItem('user_profile');
        router.push('/login');
      });
  }, [router]);

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  if (isAuthChecking) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[#0b1120] text-slate-200">
        <div className="flex flex-col items-center gap-3 p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-md">
          <div className="relative flex items-center justify-center">
            <div className="w-10 h-10 border-2 border-sky-500/20 border-t-sky-500 rounded-full animate-spin" />
            <HeartPulse className="w-5 h-5 text-sky-400 absolute animate-pulse" />
          </div>
          <div className="text-center">
            <p className="text-xs font-semibold tracking-wider text-slate-200 uppercase">Estación Clínica AI-Triage</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Verificando credenciales de personal médico...</p>
          </div>
        </div>
      </div>
    );
  }

  // Solo se muestran los paneles que el servidor permite usar (los mismos permisos que exige cada endpoint).
  const perms = currentUser?.permissions;
  const isAdmin = currentUser?.role === 'admin';
  const canSee = (id: string): boolean => {
    switch (id) {
      case 'emr': return isAdmin || !!perms?.can_view_emr;
      case 'blind': return isAdmin || !!perms?.can_edit_symptoms;
      case 'normalization': return isAdmin || !!perms?.can_use_transcriber;
      case 'fhir': return isAdmin || !!perms?.can_view_fhir;
      case 'security': return isAdmin;
      case 'config': return isAdmin || !!perms?.can_manage_config;
      default: return true;
    }
  };

  const clinicalItems = [
    { id: 'triage', icon: <Stethoscope className="w-4 h-4"/>, label: 'Modulo de Triaje' },
    { id: 'emr', icon: <Database className="w-4 h-4"/>, label: 'Simulador HCE' },
    { id: 'blind', icon: <EyeOff className="w-4 h-4"/>, label: 'Validacion Ciega' },
  ].filter(item => canSee(item.id));

  const qualityItems = [
    { id: 'metrics', icon: <BarChart className="w-4 h-4"/>, label: 'Metricas y Evaluacion' },
    { id: 'normalization', icon: <RefreshCw className="w-4 h-4"/>, label: 'Monitor Normalizacion' },
    { id: 'fhir', icon: <Server className="w-4 h-4"/>, label: 'Monitor FHIR/HL7' },
  ].filter(item => canSee(item.id));

  const adminItems = [
    { id: 'security', icon: <Shield className="w-4 h-4"/>, label: 'Seguridad y RBAC' },
    { id: 'config', icon: <Settings className="w-4 h-4"/>, label: 'Configuracion' },
  ].filter(item => canSee(item.id));

  const allNavItems = [...clinicalItems, ...qualityItems, ...adminItems];
  // Si la pestaña activa deja de estar permitida, se vuelve al triaje.
  const visibleTab = allNavItems.some(i => i.id === activeTab) ? activeTab : 'triage';
  const currentActiveItem = allNavItems.find(i => i.id === visibleTab);

  return (
    <div className="flex flex-col md:flex-row h-full w-full bg-[#0b1120] text-slate-200 font-sans overflow-hidden">
      {/* Mobile Top Header */}
      <header className="md:hidden h-14 bg-slate-900/90 backdrop-blur-md border-b border-slate-800/80 flex items-center justify-between px-3 shrink-0 z-30">
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setMobileMenuOpen(true)}
            aria-label="Abrir menu de navegacion"
            className="p-2 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-sky-600 rounded-lg flex items-center justify-center shrink-0 shadow-sm shadow-sky-600/30">
              <Activity className="w-4 h-4 text-white" />
            </div>
            <div>
              <span className="font-semibold text-xs text-slate-100 block leading-tight">
                {currentActiveItem?.label || 'AI-Triage'}
              </span>
              <span className="text-[10px] text-slate-400 block">Urgencias Hospitalarias</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-sky-400 font-bold text-xs">
            {currentUser?.first_name ? currentUser.first_name[0].toUpperCase() : 'U'}
          </div>
        </div>
      </header>

      {/* Mobile Drawer Backdrop & Menu */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div 
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />

          <div className="fixed inset-y-0 left-0 w-72 max-w-[85vw] bg-slate-900/95 border-r border-slate-800 flex flex-col p-4 shadow-2xl z-50 backdrop-blur-xl">
            {/* Drawer Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 bg-sky-600 rounded-lg flex items-center justify-center shrink-0 shadow-md shadow-sky-600/25">
                  <Activity className="w-4 h-4 text-white" />
                </div>
                <div>
                  <span className="font-semibold text-sm text-slate-100 block">AI-Triage</span>
                  <span className="text-[10px] text-slate-400">Servicio de Urgencias</span>
                </div>
              </div>
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Mobile User Profile Card */}
            <div className="py-3 border-b border-slate-800/80">
              <div className="flex items-center gap-2.5 p-2 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <div className="w-8 h-8 rounded-full bg-sky-950 border border-sky-800/60 flex items-center justify-center text-sky-300 font-bold text-xs shrink-0">
                  {currentUser?.first_name ? currentUser.first_name[0].toUpperCase() : 'U'}
                </div>
                <div className="overflow-hidden">
                  <div className="text-xs font-medium text-slate-200 truncate">
                    {currentUser?.full_name || 'Personal Medico'}
                  </div>
                  <div className="text-[10px] text-sky-400 font-medium capitalize">
                    {currentUser?.role || 'Medico'}
                  </div>
                </div>
              </div>
            </div>

            {/* Navigation Items in Drawer */}
            <nav className="flex-1 py-3 flex flex-col gap-1 overflow-y-auto">
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 py-1">Atención Clínica</div>
              {clinicalItems.map(item => {
                const isActive = visibleTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setActiveTab(item.id);
                      setMobileMenuOpen(false);
                    }}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all ${
                      isActive 
                        ? 'bg-sky-600/20 text-sky-300 border border-sky-500/30 font-medium' 
                        : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
                    }`}
                  >
                    <div className="shrink-0">{item.icon}</div>
                    <span className="text-xs">{item.label}</span>
                  </button>
                );
              })}

              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 py-1 mt-3">Evaluación y Calidad</div>
              {qualityItems.map(item => {
                const isActive = visibleTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setActiveTab(item.id);
                      setMobileMenuOpen(false);
                    }}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all ${
                      isActive 
                        ? 'bg-sky-600/20 text-sky-300 border border-sky-500/30 font-medium' 
                        : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
                    }`}
                  >
                    <div className="shrink-0">{item.icon}</div>
                    <span className="text-xs">{item.label}</span>
                  </button>
                );
              })}

              {adminItems.length > 0 && <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 py-1 mt-3">Administración del Sistema</div>}
              {adminItems.map(item => {
                const isActive = visibleTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setActiveTab(item.id);
                      setMobileMenuOpen(false);
                    }}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all ${
                      isActive 
                        ? 'bg-sky-600/20 text-sky-300 border border-sky-500/30 font-medium' 
                        : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
                    }`}
                  >
                    <div className="shrink-0">{item.icon}</div>
                    <span className="text-xs">{item.label}</span>
                  </button>
                );
              })}
            </nav>

            <div className="pt-2 border-t border-slate-800/80">
              <EngineStatus />
            </div>

            {/* Logout button at bottom of mobile drawer */}
            <div className="pt-3 border-t border-slate-800/80">
              <button 
                onClick={handleLogout}
                className="flex items-center gap-3 p-2.5 w-full rounded-lg text-rose-400 hover:bg-rose-950/30 hover:text-rose-300 transition-all border border-transparent hover:border-rose-900/40 text-xs font-medium"
              >
                <LogOut className="w-4 h-4 shrink-0" />
                <span>Cerrar Sesion</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Desktop Sidebar Navigation */}
      <aside className={`hidden md:flex ${isCollapsed ? 'w-16' : 'w-60'} bg-slate-900/95 border-r border-slate-800/80 flex-col shrink-0 transition-all duration-300 z-10 backdrop-blur-md`}>
        {/* Brand header */}
        <div className="h-16 border-b border-slate-800/80 flex items-center px-4 shrink-0 overflow-hidden justify-between">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 bg-sky-600 rounded-lg flex items-center justify-center shrink-0 shadow-md shadow-sky-600/30">
              <Activity className="w-4 h-4 text-white" />
            </div>
            <div className={`transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
              <span className="font-semibold text-sm text-slate-100 block leading-tight tracking-tight">AI-Triage</span>
              <span className="text-[10px] text-slate-400 block leading-tight">Clínica Christus Sinergia</span>
            </div>
          </div>
        </div>

        {/* Current User Badge in Desktop Sidebar */}
        <div className="p-3 border-b border-slate-800/80 bg-slate-950/30">
          <div className="flex items-center gap-2.5 px-2.5 py-2 rounded-xl bg-slate-800/40 border border-slate-800">
            <div className="w-7 h-7 rounded-full bg-sky-950 border border-sky-800/50 flex items-center justify-center shrink-0 text-sky-300 font-semibold text-xs">
              {currentUser?.first_name ? currentUser.first_name[0].toUpperCase() : 'U'}
            </div>
            <div className={`overflow-hidden transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
              <div className="text-xs font-medium text-slate-200 truncate leading-tight">
                {currentUser?.full_name || 'Personal Medico'}
              </div>
              <div className="text-[10px] text-sky-400 font-mono tracking-wide font-medium mt-0.5">
                {currentUser?.role || 'medico'}
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Sections */}
        <nav className="flex-1 py-3 flex flex-col gap-4 px-2 overflow-y-auto overflow-x-hidden">
          {/* Section 1: Atencion Clinica */}
          <div className="flex flex-col gap-0.5">
            <span className={`px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500 ${isCollapsed ? 'hidden' : 'block'}`}>
              Atención Clínica
            </span>
            {clinicalItems.map(item => {
              const isActive = visibleTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center ${isCollapsed ? 'justify-center' : 'justify-start'} gap-2.5 px-2.5 py-2 rounded-lg text-left transition-all ${
                    isActive 
                      ? 'bg-sky-600/15 text-sky-200 border border-sky-500/30 font-medium shadow-sm' 
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
                  }`}
                  title={isCollapsed ? item.label : undefined}
                >
                  <div className={`shrink-0 ${isActive ? 'text-sky-400' : 'text-slate-400'}`}>{item.icon}</div>
                  <span className={`text-xs truncate transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
                    {item.label}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Section 2: Evaluacion y Calidad */}
          <div className="flex flex-col gap-0.5">
            <span className={`px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500 ${isCollapsed ? 'hidden' : 'block'}`}>
              Evaluación y Métricas
            </span>
            {qualityItems.map(item => {
              const isActive = visibleTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center ${isCollapsed ? 'justify-center' : 'justify-start'} gap-2.5 px-2.5 py-2 rounded-lg text-left transition-all ${
                    isActive 
                      ? 'bg-sky-600/15 text-sky-200 border border-sky-500/30 font-medium shadow-sm' 
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
                  }`}
                  title={isCollapsed ? item.label : undefined}
                >
                  <div className={`shrink-0 ${isActive ? 'text-sky-400' : 'text-slate-400'}`}>{item.icon}</div>
                  <span className={`text-xs truncate transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
                    {item.label}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Section 3: Administracion */}
          {adminItems.length > 0 && <div className="flex flex-col gap-0.5">
            <span className={`px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500 ${isCollapsed ? 'hidden' : 'block'}`}>
              Administración
            </span>
            {adminItems.map(item => {
              const isActive = visibleTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center ${isCollapsed ? 'justify-center' : 'justify-start'} gap-2.5 px-2.5 py-2 rounded-lg text-left transition-all ${
                    isActive 
                      ? 'bg-sky-600/15 text-sky-200 border border-sky-500/30 font-medium shadow-sm' 
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
                  }`}
                  title={isCollapsed ? item.label : undefined}
                >
                  <div className={`shrink-0 ${isActive ? 'text-sky-400' : 'text-slate-400'}`}>{item.icon}</div>
                  <span className={`text-xs truncate transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
                    {item.label}
                  </span>
                </button>
              );
            })}
          </div>}
        </nav>

        <div className="border-t border-slate-800/80 px-2 py-1 shrink-0">
          <EngineStatus compact={isCollapsed} />
        </div>

        {/* Bottom Actions */}
        <div className="p-2 border-t border-slate-800/80 flex flex-col items-center shrink-0 gap-1 bg-slate-950/20">
          <button 
            onClick={handleLogout}
            className="flex items-center justify-start gap-2.5 px-2.5 py-2 w-full rounded-lg text-rose-400 hover:bg-rose-950/30 hover:text-rose-300 transition-all border border-transparent hover:border-rose-900/40 text-xs font-medium"
            title="Cerrar Sesion"
          >
            <div className="shrink-0"><LogOut className="w-4 h-4"/></div>
            <span className={`truncate transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
              Cerrar Sesion
            </span>
          </button>

          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="flex items-center justify-start gap-2.5 px-2.5 py-1.5 w-full rounded-lg text-slate-500 hover:bg-slate-800/50 hover:text-slate-300 transition-all text-xs"
            title={isCollapsed ? "Expandir panel" : "Contraer panel"}
          >
            <div className="shrink-0">
              {isCollapsed ? <ChevronRight className="w-4 h-4"/> : <ChevronLeft className="w-4 h-4"/>}
            </div>
            <span className={`text-[11px] truncate transition-opacity duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>
              Contraer
            </span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-[#0b1120] p-2 md:p-3">
        <Toaster theme="dark" position="bottom-right" richColors closeButton duration={4000} />
        {visibleTab === 'triage' && <TriageDashboard userProfile={currentUser} />}
        {visibleTab === 'config' && <ConfigPanel />}
        {visibleTab === 'security' && <SecurityPanel />}
        {visibleTab === 'normalization' && <NormalizationMonitor />}
        {visibleTab === 'fhir' && <FHIRMonitor />}
        {visibleTab === 'emr' && <EMRSimulator />}
        {visibleTab === 'metrics' && <MetricsDashboard />}
        {visibleTab === 'blind' && <BlindReview />}
      </div>
    </div>
  );
}
