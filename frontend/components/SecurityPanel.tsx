'use client';

import { useState, useEffect, useCallback } from 'react';
import { 
  Shield, 
  Users, 
  FileLock2, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  Lock, 
  Sliders, 
  ChevronDown, 
  ChevronUp,
  Search,
  Filter,
  Mic,
  Edit3,
  UserPlus,
  Database,
  Server,
  Settings
} from 'lucide-react';
import { toast } from 'sonner';
import { fetchWithAuth } from '@/lib/api';

interface UserPermissionData {
  can_use_transcriber: boolean;
  can_edit_symptoms: boolean;
  can_register_patients: boolean;
  can_view_emr: boolean;
  can_view_fhir: boolean;
  can_manage_config: boolean;
}

interface UserItem {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  document_id: string;
  phone: string;
  role: 'admin' | 'medico' | 'enfermero';
  is_verified: boolean;
  permissions: UserPermissionData;
  date_joined: string;
}

interface AuditLogItem {
  id: number;
  timestamp: string;
  user: string;
  user_email: string;
  role: string;
  action: string;
  resource: string;
  status: string;
  ip_address: string;
  details: string;
}

export default function SecurityPanel() {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedUserId, setExpandedUserId] = useState<number | null>(null);
  const [actionFilter, setActionFilter] = useState('ALL');
  const [updatingPermKey, setUpdatingPermKey] = useState<string | null>(null);

  const loadSecurityData = useCallback(async () => {
    setLoading(true);
    try {
      const [usersRes, logsRes] = await Promise.all([
        fetchWithAuth('/api/security/users/'),
        fetchWithAuth('/api/security/audit-logs/'),
      ]);

      if (usersRes.ok) {
        const usersData = await usersRes.json();
        setUsers(usersData);
        setExpandedUserId(prev => (prev === null && usersData.length > 0 ? usersData[0].id : prev));
      }

      if (logsRes.ok) {
        const logsData = await logsRes.json();
        setAuditLogs(logsData);
      }
    } catch (err: any) {
      toast.error('Error al sincronizar datos de seguridad y auditoria');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadSecurityData();
  }, [loadSecurityData]);

  const handleTogglePermission = async (userId: number, permKey: keyof UserPermissionData, currentValue: boolean) => {
    const updatingId = `${userId}-${permKey}`;
    setUpdatingPermKey(updatingId);

    // Optimistic UI update
    setUsers(prev => prev.map(u => {
      if (u.id === userId) {
        return {
          ...u,
          permissions: {
            ...u.permissions,
            [permKey]: !currentValue,
          },
        };
      }
      return u;
    }));

    try {
      const res = await fetchWithAuth(`/api/security/users/${userId}/permissions/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [permKey]: !currentValue }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Fallo al actualizar permiso');
      }

      toast.success('Permiso actualizado correctamente en la base de datos');
      // Recargar logs para ver el cambio reflejado en auditoria
      const logsRes = await fetchWithAuth('/api/security/audit-logs/');
      if (logsRes.ok) {
        setAuditLogs(await logsRes.json());
      }
    } catch (err: any) {
      toast.error(err.message || 'Error al persistir permiso');
      // Revertir cambio optimista
      setUsers(prev => prev.map(u => {
        if (u.id === userId) {
          return {
            ...u,
            permissions: {
              ...u.permissions,
              [permKey]: currentValue,
            },
          };
        }
        return u;
      }));
    } finally {
      setUpdatingPermKey(null);
    }
  };

  const permissionDefinitions: { key: keyof UserPermissionData; label: string; desc: string; icon: any }[] = [
    {
      key: 'can_use_transcriber',
      label: 'Transcriptor ASR en Vivo',
      desc: 'Habilita la captura y transcripcion de voz con Faster-Whisper en tiempo real.',
      icon: <Mic className="w-3.5 h-3.5 text-blue-400" />,
    },
    {
      key: 'can_edit_symptoms',
      label: 'Editar Sintomas y Nivel de Triaje',
      desc: 'Permite al profesional modificar entidades clinicas y reclasificar la severidad manual.',
      icon: <Edit3 className="w-3.5 h-3.5 text-amber-400" />,
    },
    {
      key: 'can_register_patients',
      label: 'Registrar Nuevos Pacientes',
      desc: 'Capacidad para crear fichas clinicas y asociar datos demograficos de urgencias.',
      icon: <UserPlus className="w-3.5 h-3.5 text-emerald-400" />,
    },
    {
      key: 'can_view_emr',
      label: 'Acceso a Simulador HCE',
      desc: 'Permiso para consultar el historial medico, antecedentes y resumenes generados por IA.',
      icon: <Database className="w-3.5 h-3.5 text-purple-400" />,
    },
    {
      key: 'can_view_fhir',
      label: 'Interoperabilidad FHIR / HL7',
      desc: 'Autorizacion para inspeccionar y exportar recursos clinicos estandarizados.',
      icon: <Server className="w-3.5 h-3.5 text-orange-400" />,
    },
    {
      key: 'can_manage_config',
      label: 'Gestion de Motores y Llaves API',
      desc: 'Privilegio de administrador para alternar modelos IA y registrar credenciales cifradas.',
      icon: <Settings className="w-3.5 h-3.5 text-red-400" />,
    },
  ];

  const filteredLogs = auditLogs.filter(log => {
    if (actionFilter === 'ALL') return true;
    return log.action.toUpperCase().includes(actionFilter);
  });

  return (
    <div className="flex flex-col h-full w-full bg-[var(--surface-base)] border border-[var(--surface-border)] rounded-2xl p-4 sm:p-6 overflow-y-auto space-y-6 shadow-xl">
      {/* Header Seguridad */}
      <div className="flex items-center justify-between border-b border-[var(--surface-border)] pb-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xs sm:text-sm font-semibold text-slate-100 tracking-wide uppercase">
              Seguridad y Control de Acceso (RBAC)
            </h2>
            <p className="text-[11px] text-slate-400">
              Administracion de roles, matriz de permisos granulares y auditoria inmutable (Ley 1581 / HIPAA)
            </p>
          </div>
        </div>

        <button
          onClick={() => { setRefreshing(true); loadSecurityData(); }}
          disabled={refreshing}
          className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-300 bg-[var(--surface-card)] hover:bg-slate-800 border border-[var(--surface-border)] transition-colors flex items-center gap-2"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-sky-400' : ''}`} />
          Refrescar Datos
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0">
        {/* LEFT COLUMN: User Directory & Granular Permissions */}
        <div className="bg-[var(--surface-panel)] rounded-2xl border border-[var(--surface-border)] p-4 sm:p-5 flex flex-col min-h-[400px] shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-[var(--surface-border)] mb-4 shrink-0">
            <div className="flex items-center gap-2.5 text-slate-200">
              <Users className="w-4 h-4 text-sky-400" />
              <h3 className="text-xs uppercase font-semibold tracking-wider text-slate-200">
                Usuarios y Matriz de Permisos
              </h3>
            </div>
            <span className="text-[11px] text-slate-500 font-mono">
              {users.length} usuarios registrados
            </span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {users.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 bg-[var(--surface-card)] rounded-xl border border-[var(--surface-border)]">
                No se encontraron usuarios en la base de datos.
              </div>
            ) : (
              users.map(u => {
                const isExpanded = expandedUserId === u.id;
                return (
                  <div
                    key={u.id}
                    className="bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl overflow-hidden transition-all shadow-sm"
                  >
                    {/* User Summary Header */}
                    <div 
                      onClick={() => setExpandedUserId(isExpanded ? null : u.id)}
                      className="p-3.5 flex items-center justify-between cursor-pointer hover:bg-slate-800/40 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-600 to-teal-700 flex items-center justify-center text-white font-bold text-xs shadow-sm">
                          {u.first_name ? u.first_name[0].toUpperCase() : u.email[0].toUpperCase()}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold text-slate-100">{u.full_name}</span>
                            <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider border ${
                              u.role === 'admin' 
                                ? 'bg-red-500/10 text-red-400 border-red-500/30' 
                                : u.role === 'medico'
                                ? 'bg-sky-500/10 text-sky-400 border-sky-500/30'
                                : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                            }`}>
                              {u.role}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono mt-0.5">
                            <span>{u.email}</span>
                            <span className="text-slate-600">•</span>
                            <span>Doc: {u.document_id || 'N/A'}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-[11px] text-slate-400 font-medium hidden sm:inline">
                          {isExpanded ? 'Ocultar' : 'Configurar'}
                        </span>
                        {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                      </div>
                    </div>

                    {/* Permissions Expanded Grid */}
                    {isExpanded && (
                      <div className="p-3.5 bg-[var(--surface-base)] border-t border-[var(--surface-border)] space-y-3">
                        <div className="flex items-center justify-between pb-1">
                          <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">
                            Permisos Asignados en Base de Datos
                          </span>
                          <span className="text-[10px] text-emerald-400 font-mono flex items-center gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Sincronizacion en tiempo real
                          </span>
                        </div>

                        <div className="space-y-2">
                          {permissionDefinitions.map(def => {
                            const isAllowed = u.permissions ? u.permissions[def.key] : false;
                            const isUpdating = updatingPermKey === `${u.id}-${def.key}`;

                            return (
                              <div
                                key={def.key}
                                className="flex items-center justify-between p-2.5 rounded-xl bg-[var(--surface-panel)] border border-[var(--surface-border)] hover:border-slate-700 transition-all"
                              >
                                <div className="flex items-start gap-3 pr-2">
                                  <div className="p-1.5 rounded-lg bg-[var(--surface-card)] shrink-0 mt-0.5 border border-[var(--surface-border)]">
                                    {def.icon}
                                  </div>
                                  <div>
                                    <span className="text-xs font-medium text-slate-200 block">
                                      {def.label}
                                    </span>
                                    <span className="text-[11px] text-slate-400 block leading-tight">
                                      {def.desc}
                                    </span>
                                  </div>
                                </div>

                                <button
                                  onClick={() => handleTogglePermission(u.id, def.key, isAllowed)}
                                  disabled={isUpdating}
                                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                                    isAllowed ? 'bg-emerald-600' : 'bg-slate-700'
                                  } ${isUpdating ? 'opacity-50' : ''}`}
                                >
                                  <span
                                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${
                                      isAllowed ? 'translate-x-4' : 'translate-x-0'
                                    }`}
                                  />
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Real Audit Logs */}
        <div className="bg-[var(--surface-panel)] rounded-2xl border border-[var(--surface-border)] p-4 sm:p-5 flex flex-col min-h-[400px] shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-[var(--surface-border)] mb-4 shrink-0">
            <div className="flex items-center gap-2.5 text-slate-200">
              <FileLock2 className="w-4 h-4 text-teal-400" />
              <h3 className="text-xs uppercase font-semibold tracking-wider text-slate-200">
                Pistas de Auditoria Inmutable (Ley 1581)
              </h3>
            </div>

            {/* Filter Selector */}
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl py-1.5 px-3 text-[11px] text-slate-300 focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              <option value="ALL">Todas las Acciones</option>
              <option value="LOGIN">Inicios de Sesion</option>
              <option value="REGISTER">Registros</option>
              <option value="RBAC">Cambios de Permisos</option>
              <option value="API_KEY">Llaves API</option>
              <option value="CONFIG">Configuracion</option>
              <option value="VOCABULARY">Vocabularios</option>
            </select>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
            {filteredLogs.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 bg-[var(--surface-card)] rounded-xl border border-[var(--surface-border)]">
                No hay eventos registrados para el filtro seleccionado.
              </div>
            ) : (
              filteredLogs.map(log => (
                <div
                  key={log.id}
                  className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--surface-border)] hover:border-slate-700 transition-all font-mono text-[11px] text-slate-300 space-y-1.5 shadow-sm"
                >
                  <div className="flex justify-between items-center text-slate-500 text-[10px]">
                    <span>{log.timestamp}</span>
                    <span className={`px-2 py-0.5 rounded-full font-semibold uppercase ${
                      log.status === 'SUCCESS' 
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                        : 'bg-red-500/10 text-red-400 border border-red-500/20'
                    }`}>
                      {log.status === 'SUCCESS' ? 'EXITO' : 'DENEGADO'}
                    </span>
                  </div>

                  <div className="text-slate-200 font-sans text-xs">
                    <span className="text-sky-400 font-medium">{log.user}</span> ({log.role}) 
                    {' '}ejecuto <span className="font-mono text-amber-400 font-semibold">{log.action}</span> 
                    {' '}en <span className="text-teal-300 font-mono">{log.resource}</span>
                  </div>

                  {log.details && (
                    <div className="text-slate-400 text-[11px] bg-[var(--surface-base)] p-2 rounded-lg border border-[var(--surface-border)]">
                      {log.details}
                    </div>
                  )}

                  {log.ip_address && (
                    <div className="text-[10px] text-slate-500 text-right font-mono">
                      IP: {log.ip_address}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
