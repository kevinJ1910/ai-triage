'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { setAccessToken } from '@/lib/api';
import ThemeToggle from '@/components/ThemeToggle';
import { 
  Lock, 
  Mail, 
  Activity, 
  ArrowRight, 
  ShieldCheck, 
  AlertCircle, 
  Eye, 
  EyeOff, 
  User, 
  FileBadge, 
  Phone, 
  CheckCircle2, 
  RefreshCw,
  KeyRound,
  X,
  Stethoscope,
  Check
} from 'lucide-react';
import { 
  validateEmail, 
  validateDocumentId, 
  validatePhone, 
  validatePassword, 
  validateOtpCode, 
  InputWarning 
} from '@/lib/validation';

function extractErrorMessage(data: unknown, fallback: string): string {
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  if (typeof data === 'object') {
    const record = data as Record<string, unknown>;
    if (typeof record.detail === 'string') return record.detail;
    if (typeof record.error === 'string') return record.error;
    if (typeof record.message === 'string') return record.message;

    const keys = Object.keys(record);
    if (keys.length > 0) {
      const firstVal = record[keys[0]];
      const msg = Array.isArray(firstVal) ? firstVal.join(', ') : String(firstVal);
      const fieldLabels: Record<string, string> = {
        email: 'Correo',
        password: 'Contraseña',
        confirm_password: 'Confirmar contraseña',
        new_password: 'Nueva contraseña',
        code: 'Código de verificación',
        document_id: 'Documento',
        phone: 'Teléfono',
        role: 'Rol',
        non_field_errors: 'Error',
      };
      const label = fieldLabels[keys[0]] || keys[0];
      return `${label}: ${msg}`;
    }
  }
  return fallback;
}

export default function LoginPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');
  
  // Login form state
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);

  // Register form state
  const [regFirstName, setRegFirstName] = useState('');
  const [regLastName, setRegLastName] = useState('');
  const [regDocType, setRegDocType] = useState('CC');
  const [regDocNumber, setRegDocNumber] = useState('');
  const [regPhone, setRegPhone] = useState('');
  const [regRole, setRegRole] = useState('medico');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');
  const [showRegPassword, setShowRegPassword] = useState(false);

  // Verification modal state
  const [isVerifyModalOpen, setIsVerifyModalOpen] = useState(false);
  const [verifyEmail, setVerifyEmail] = useState('');
  const [verifyCode, setVerifyCode] = useState('');
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);

  // Forgot password modal state
  const [isForgotModalOpen, setIsForgotModalOpen] = useState(false);
  const [forgotStep, setForgotStep] = useState<1 | 2>(1);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotCode, setForgotCode] = useState('');
  const [forgotNewPassword, setForgotNewPassword] = useState('');
  const [forgotConfirmPassword, setForgotConfirmPassword] = useState('');
  const [forgotLoading, setForgotLoading] = useState(false);

  // UI status state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [infoMessage, setInfoMessage] = useState('');

  // Validaciones tipadas en tiempo real
  const loginEmailWarning = loginEmail ? validateEmail(loginEmail).warning : null;
  const loginPasswordWarning = loginPassword ? validatePassword(loginPassword).warning : null;

  const regEmailWarning = regEmail ? validateEmail(regEmail).warning : null;
  const regDocWarning = regDocNumber ? validateDocumentId(regDocNumber).warning : null;
  const regPhoneWarning = regPhone ? validatePhone(regPhone).warning : null;
  const regPasswordWarning = regPassword ? validatePassword(regPassword).warning : null;
  const regConfirmPasswordWarning = regConfirmPassword ? validatePassword(regPassword, regConfirmPassword).warning : null;

  const verifyCodeWarning = verifyCode ? validateOtpCode(verifyCode).warning : null;

  const forgotEmailWarning = forgotEmail ? validateEmail(forgotEmail).warning : null;
  const forgotCodeWarning = forgotCode ? validateOtpCode(forgotCode).warning : null;
  const forgotNewPasswordWarning = forgotNewPassword ? validatePassword(forgotNewPassword).warning : null;
  const forgotConfirmPasswordWarning = forgotConfirmPassword ? validatePassword(forgotNewPassword, forgotConfirmPassword).warning : null;

  // Handle Login Submit
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setInfoMessage('');

    const emailCheck = validateEmail(loginEmail);
    if (!emailCheck.isValid) {
      setError(emailCheck.warning || 'Correo institucional invalido.');
      return;
    }

    setLoading(true);

    try {
      const res = await fetch('/api/auth/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: loginEmail.trim().toLowerCase(),
          password: loginPassword
        })
      });

      const data = await res.json();

      if (!res.ok) {
        if ((res.status === 403 || res.status === 400) && (data.needs_verification || data.code === 'account_not_verified')) {
          setVerifyEmail(loginEmail.trim().toLowerCase());
          setVerifyCode('');
          setError('');
          setInfoMessage('Cuenta pendiente de verificacion. Se ha enviado un nuevo codigo OTP de 6 digitos a su correo.');
          setIsVerifyModalOpen(true);
          return;
        }
        throw new Error(extractErrorMessage(data, 'Credenciales invalidas o error de servidor.'));
      }

      // El access token queda en memoria; el refresh lo fija el backend en una cookie httpOnly
      setAccessToken(data.access);
      localStorage.setItem('user_profile', JSON.stringify(data.user));

      router.push('/');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al iniciar sesion';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Handle Register Submit
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setInfoMessage('');

    const emailCheck = validateEmail(regEmail);
    if (!emailCheck.isValid) {
      setError(emailCheck.warning || 'Correo institucional invalido.');
      return;
    }

    const docCheck = validateDocumentId(regDocNumber);
    if (!docCheck.isValid) {
      setError(docCheck.warning || 'Documento de identidad invalido.');
      return;
    }

    const phoneCheck = validatePhone(regPhone);
    if (!phoneCheck.isValid) {
      setError(phoneCheck.warning || 'Formato de telefono invalido.');
      return;
    }

    const passCheck = validatePassword(regPassword, regConfirmPassword);
    if (!passCheck.isValid) {
      setError(passCheck.warning || 'Contrasenas no validas.');
      return;
    }

    setLoading(true);

    const formattedDocId = regDocNumber.trim()
      ? (regDocType ? `${regDocType}-${regDocNumber.trim()}` : regDocNumber.trim())
      : undefined;

    try {
      const res = await fetch('/api/auth/register/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: regEmail.trim().toLowerCase(),
          password: regPassword,
          confirm_password: regConfirmPassword,
          first_name: regFirstName.trim(),
          last_name: regLastName.trim(),
          document_id: formattedDocId,
          document_type: regDocType,
          document_number: regDocNumber.trim(),
          phone: regPhone.trim(),
          phone_number: regPhone.trim(),
          role: regRole
        })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(extractErrorMessage(data, 'Error en el registro'));
      }

      setVerifyEmail(regEmail.trim().toLowerCase());
      setIsVerifyModalOpen(true);
      setInfoMessage('Registro completado. Por favor ingrese el codigo de 6 digitos enviado a su correo.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error en el registro';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Handle OTP Verification Submit
  const handleVerifyCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const codeCheck = validateOtpCode(verifyCode);
    if (!codeCheck.isValid) {
      setError(codeCheck.warning || 'Codigo de verificacion no valido.');
      return;
    }

    setVerifyLoading(true);

    try {
      const res = await fetch('/api/auth/verify/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: verifyEmail.trim().toLowerCase(),
          code: verifyCode.trim()
        })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(extractErrorMessage(data, 'Codigo de verificacion incorrecto o expirado.'));
      }

      setIsVerifyModalOpen(false);
      setVerifyCode('');
      if (data.access && data.user) {
        setAccessToken(data.access);
        localStorage.setItem('user_profile', JSON.stringify(data.user));
        router.push('/');
        return;
      }
      setInfoMessage('Cuenta verificada exitosamente. Ya puede iniciar sesion con sus credenciales.');
      setActiveTab('login');
      setLoginEmail(verifyEmail);
      setLoginPassword('');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Fallo en la verificacion';
      setError(msg);
    } finally {
      setVerifyLoading(false);
    }
  };

  // Handle Resend OTP Code
  const handleResendCode = async () => {
    setError('');
    setResendLoading(true);
    try {
      const res = await fetch('/api/auth/resend-code/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: verifyEmail.trim().toLowerCase(),
          purpose: 'activation'
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(extractErrorMessage(data, 'No fue posible reenviar el codigo.'));
      }
      setInfoMessage('Nuevo codigo OTP enviado a su bandeja de correo.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al reenviar codigo';
      setError(msg);
    } finally {
      setResendLoading(false);
    }
  };

  // Handle Request Password Reset
  const handleRequestPasswordReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const emailCheck = validateEmail(forgotEmail);
    if (!emailCheck.isValid) {
      setError(emailCheck.warning || 'Correo institucional invalido.');
      return;
    }

    setForgotLoading(true);

    try {
      const res = await fetch('/api/auth/password-reset/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: forgotEmail.trim().toLowerCase() })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(extractErrorMessage(data, 'Error al procesar la solicitud.'));
      }
      setForgotStep(2);
      setInfoMessage('Codigo de recuperacion enviado. Ingrese el codigo y su nueva clave.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Fallo en la solicitud';
      setError(msg);
    } finally {
      setForgotLoading(false);
    }
  };

  // Handle Confirm Password Reset
  const handleConfirmPasswordReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const codeCheck = validateOtpCode(forgotCode);
    if (!codeCheck.isValid) {
      setError(codeCheck.warning || 'Codigo de verificacion invalido.');
      return;
    }

    const passCheck = validatePassword(forgotNewPassword, forgotConfirmPassword);
    if (!passCheck.isValid) {
      setError(passCheck.warning || 'Contrasenas no validas.');
      return;
    }

    setForgotLoading(true);

    try {
      const res = await fetch('/api/auth/password-reset/confirm/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: forgotEmail.trim().toLowerCase(),
          code: forgotCode.trim(),
          new_password: forgotNewPassword,
          confirm_password: forgotConfirmPassword
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(extractErrorMessage(data, 'Codigo invalido o error al actualizar clave.'));
      }
      setIsForgotModalOpen(false);
      setForgotStep(1);
      setForgotEmail('');
      setForgotCode('');
      setForgotNewPassword('');
      setForgotConfirmPassword('');
      setInfoMessage('Contrasena actualizada con exito. Ingrese con su nueva clave.');
      setActiveTab('login');
      setLoginPassword('');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al actualizar contrasena';
      setError(msg);
    } finally {
      setForgotLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between items-center p-4 sm:p-6 md:p-8 selection:bg-slate-700 selection:text-slate-100">
      {/* Hospital Institutional Header */}
      <header className="w-full max-w-4xl flex items-center justify-between py-4 border-b border-slate-800 text-xs text-slate-400">
        <div className="flex items-center gap-2.5 font-medium text-slate-200">
          <div className="w-6 h-6 rounded bg-slate-800 border border-slate-700 flex items-center justify-center text-sky-400 font-semibold text-xs">
            +
          </div>
          <span>Christus Sinergia Salud</span>
          <span className="text-slate-600 hidden sm:inline">|</span>
          <span className="text-slate-400 hidden sm:inline">Servicio de Urgencias y Admision</span>
        </div>
        <div className="flex items-center gap-3 text-slate-400 text-[11px]">
          <span className="hidden sm:inline">Estacion Asistencial Conectada</span>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          <ThemeToggle showLabel={false} className="p-1.5" />
        </div>
      </header>

      {/* Main Authentication Box */}
      <main className="w-full max-w-md my-auto py-8 z-10">
        <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-xl p-6 sm:p-8">
          {/* Header / Logo */}
          <div className="flex flex-col items-center mb-6 text-center">
            <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center border border-slate-700 text-sky-400 mb-3 shadow-sm">
              <Activity className="w-5 h-5" />
            </div>
            <h1 className="text-lg md:text-xl font-semibold tracking-tight text-slate-100 flex items-center gap-2">
              AI-Triage Hospitalario
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Sistema de Clasificacion Clinica y Soporte a la Decision Medica
            </p>
          </div>

        {/* Global Notifications */}
        {error && (
          <div className="mb-4 p-3.5 bg-red-500/10 border border-red-500/20 rounded-2xl text-xs text-red-400 flex items-start gap-2.5 animate-in fade-in duration-200">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {infoMessage && (
          <div className="mb-4 p-3.5 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl text-xs text-emerald-400 flex items-start gap-2.5 animate-in fade-in duration-200">
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{infoMessage}</span>
          </div>
        )}

        {/* Tabs Switcher */}
        <div className="grid grid-cols-2 gap-1 p-1 bg-[var(--surface-card)] rounded-2xl border border-[var(--surface-border)] mb-6">
          <button
            type="button"
            onClick={() => { setActiveTab('login'); setError(''); setInfoMessage(''); }}
            className={`py-2 text-xs font-semibold rounded-xl transition-all ${
              activeTab === 'login'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Iniciar Sesion
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('register'); setError(''); setInfoMessage(''); }}
            className={`py-2 text-xs font-semibold rounded-xl transition-all ${
              activeTab === 'register'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Registro de Personal
          </button>
        </div>

        {/* Form: Login */}
        {activeTab === 'login' && (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Correo Institucional
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  placeholder="usuario@hospital.com"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500 transition-colors"
                />
              </div>
              <InputWarning warning={loginEmailWarning} id="login-email-warning" />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Contrasena
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setForgotEmail(loginEmail);
                    setIsForgotModalOpen(true);
                  }}
                  className="text-xs text-sky-400 hover:text-sky-300 hover:underline"
                >
                  Olvidaste tu contrasena?
                </button>
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type={showLoginPassword ? 'text' : 'password'}
                  required
                  placeholder="••••••••"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  className="w-full pl-10 pr-10 py-2.5 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500 transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowLoginPassword(!showLoginPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  {showLoginPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <InputWarning warning={loginPasswordWarning} id="login-password-warning" />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold uppercase tracking-wider transition-all shadow-sm flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Verificando credenciales...
                </>
              ) : (
                <>
                  <span>Ingresar al Sistema</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        )}

        {/* Form: Register */}
        {activeTab === 'register' && (
          <form onSubmit={handleRegister} className="space-y-3.5 max-h-[60vh] overflow-y-auto pr-1">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Nombres
                </label>
                <div className="relative">
                  <User className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    required
                    placeholder="Carlos"
                    value={regFirstName}
                    onChange={(e) => setRegFirstName(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Apellidos
                </label>
                <input
                  type="text"
                  required
                  placeholder="Gomez"
                  value={regLastName}
                  onChange={(e) => setRegLastName(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Tipo Doc
                </label>
                <select
                  value={regDocType}
                  onChange={(e) => setRegDocType(e.target.value)}
                  className="w-full px-2 py-2 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                >
                  <option value="CC">CC</option>
                  <option value="CE">CE</option>
                  <option value="TI">TI</option>
                  <option value="PA">PA</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Numero Documento
                </label>
                <div className="relative">
                  <FileBadge className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    required
                    placeholder="1098765432"
                    value={regDocNumber}
                    onChange={(e) => setRegDocNumber(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500 font-mono"
                  />
                </div>
                <InputWarning warning={regDocWarning} id="reg-doc-warning" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Telefono
                </label>
                <div className="relative">
                  <Phone className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="tel"
                    placeholder="3001234567"
                    value={regPhone}
                    onChange={(e) => setRegPhone(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500 font-mono"
                  />
                </div>
                <InputWarning warning={regPhoneWarning} id="reg-phone-warning" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Rol Clinico
                </label>
                <select
                  value={regRole}
                  onChange={(e) => setRegRole(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                >
                  <option value="medico">Medico de Urgencias</option>
                  <option value="enfermero">Enfermero(a) Jefe</option>
                  <option value="admin">Administrador del Sistema</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Correo Institucional
              </label>
              <div className="relative">
                <Mail className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  placeholder="doctor@hospital.com"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                />
              </div>
              <InputWarning warning={regEmailWarning} id="reg-email-warning" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Contrasena
                </label>
                <div className="relative">
                  <Lock className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type={showRegPassword ? 'text' : 'password'}
                    required
                    placeholder="Min. 8 car."
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    className="w-full pl-9 pr-8 py-2 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowRegPassword(!showRegPassword)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                  >
                    {showRegPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
                <InputWarning warning={regPasswordWarning} id="reg-pass-warning" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Confirmar
                </label>
                <input
                  type="password"
                  required
                  placeholder="Repetir clave"
                  value={regConfirmPassword}
                  onChange={(e) => setRegConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                />
                <InputWarning warning={regConfirmPasswordWarning} id="reg-confirm-warning" />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-3 py-2.5 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold uppercase tracking-wider transition-all shadow-sm flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Registrando y enviando codigo...
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  <span>Completar Registro</span>
                </>
              )}
            </button>
          </form>
        )}

          {/* Institutional Compliance Disclaimer */}
          <div className="mt-6 pt-4 border-t border-slate-800 text-[11px] text-slate-500 leading-relaxed">
            <p>
              Acceso restringido a personal de salud autorizado. La informacion clinica esta protegida por secreto profesional y la normatividad vigente de historia clinica.
            </p>
          </div>
        </div>
      </main>

      {/* Hospital Footer */}
      <footer className="w-full max-w-4xl py-4 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between text-[11px] text-slate-500 gap-2">
        <span>AI-Triage v2.4 — Sistema Hospitalario de Urgencias</span>
        <span>Soporte Tecnico: ext. 4100 | soporte@hospital.com</span>
      </footer>

      {/* Modal: OTP Verification */}
      {isVerifyModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-slate-800 rounded-lg text-sky-400 border border-slate-700">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <h3 className="font-semibold text-slate-100 text-sm">Verificacion de Seguridad OTP</h3>
              </div>
              <button
                onClick={() => setIsVerifyModalOpen(false)}
                className="text-slate-400 hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-400">
              Se ha enviado un codigo de 6 digitos a <span className="text-sky-400 font-semibold">{verifyEmail}</span>.
              (Revise su bandeja de entrada o Mailpit en el puerto 8025).
            </p>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {infoMessage && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-400 flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{infoMessage}</span>
              </div>
            )}

            <form onSubmit={handleVerifyCode} className="space-y-4">
              <div>
                <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-2 text-center">
                  Codigo de Verificacion (6 digitos)
                </label>
                <input
                  type="text"
                  maxLength={6}
                  required
                  placeholder="000000"
                  value={verifyCode}
                  onChange={(e) => setVerifyCode(e.target.value.replace(/[^0-9]/g, ''))}
                  className="w-full py-3 text-center text-2xl font-mono tracking-widest bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-2xl text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
                />
                <InputWarning warning={verifyCodeWarning} id="verify-code-warning" />
              </div>

              <div className="flex gap-2.5">
                <button
                  type="button"
                  onClick={handleResendCode}
                  disabled={resendLoading}
                  className="flex-1 py-2.5 bg-[var(--surface-card)] hover:bg-slate-800 text-slate-300 rounded-xl text-xs font-medium transition-colors border border-[var(--surface-border)]"
                >
                  {resendLoading ? 'Reenviando...' : 'Reenviar Codigo'}
                </button>
                <button
                  type="submit"
                  disabled={verifyLoading || verifyCode.length < 6}
                  className="flex-1 py-2.5 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold transition-colors disabled:opacity-50 shadow-sm"
                >
                  {verifyLoading ? 'Validando...' : 'Validar Cuenta'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Forgot Password */}
      {isForgotModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-slate-800 rounded-lg text-sky-400 border border-slate-700">
                  <KeyRound className="w-5 h-5" />
                </div>
                <h3 className="font-semibold text-slate-100 text-sm">Recuperacion de Contrasena</h3>
              </div>
              <button
                onClick={() => { setIsForgotModalOpen(false); setForgotStep(1); }}
                className="text-slate-400 hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {infoMessage && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-400 flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{infoMessage}</span>
              </div>
            )}

            {forgotStep === 1 ? (
              <form onSubmit={handleRequestPasswordReset} className="space-y-4">
                <p className="text-xs text-slate-400">
                  Ingrese su correo institucional para enviarle un codigo OTP de restablecimiento.
                </p>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                    Correo
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="usuario@hospital.com"
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                  />
                  <InputWarning warning={forgotEmailWarning} id="forgot-email-warning" />
                </div>
                <button
                  type="submit"
                  disabled={forgotLoading}
                  className="w-full py-2.5 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold transition-colors disabled:opacity-50 shadow-sm"
                >
                  {forgotLoading ? 'Enviando codigo...' : 'Enviar Codigo OTP'}
                </button>
              </form>
            ) : (
              <form onSubmit={handleConfirmPasswordReset} className="space-y-4">
                <p className="text-xs text-slate-400">
                  Ingrese el codigo recibido y su nueva clave de acceso.
                </p>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                    Codigo OTP (6 digitos)
                  </label>
                  <input
                    type="text"
                    maxLength={6}
                    required
                    placeholder="000000"
                    value={forgotCode}
                    onChange={(e) => setForgotCode(e.target.value.replace(/[^0-9]/g, ''))}
                    className="w-full py-2 text-center text-xl font-mono tracking-widest bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
                  />
                  <InputWarning warning={forgotCodeWarning} id="forgot-code-warning" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                    Nueva Contrasena
                  </label>
                  <input
                    type="password"
                    required
                    placeholder="Minimo 6 caracteres"
                    value={forgotNewPassword}
                    onChange={(e) => setForgotNewPassword(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                  />
                  <InputWarning warning={forgotNewPasswordWarning} id="forgot-pass-warning" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                    Confirmar Contrasena
                  </label>
                  <input
                    type="password"
                    required
                    placeholder="Repetir nueva clave"
                    value={forgotConfirmPassword}
                    onChange={(e) => setForgotConfirmPassword(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-[var(--surface-card)] border border-[var(--surface-border)] rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                  />
                  <InputWarning warning={forgotConfirmPasswordWarning} id="forgot-confirm-warning" />
                </div>
                <button
                  type="submit"
                  disabled={forgotLoading || forgotCode.length < 6}
                  className="w-full py-2.5 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold transition-colors disabled:opacity-50 shadow-sm"
                >
                  {forgotLoading ? 'Actualizando...' : 'Restablecer Contrasena'}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
