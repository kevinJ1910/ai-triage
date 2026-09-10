'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
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
  ArrowLeft
} from 'lucide-react';

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
  const [regDocumentId, setRegDocumentId] = useState('');
  const [regPhone, setRegPhone] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regRole, setRegRole] = useState<'medico' | 'enfermero' | 'admin'>('medico');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');
  const [showRegPassword, setShowRegPassword] = useState(false);

  // OTP Verification state
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false);
  const [otpEmail, setOtpEmail] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [otpSuccessMessage, setOtpSuccessMessage] = useState('');

  // Password Reset state
  const [isResettingPassword, setIsResettingPassword] = useState(false);
  const [resetStep, setResetStep] = useState<1 | 2>(1);
  const [resetEmail, setResetEmail] = useState('');
  const [resetCode, setResetCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');

  // Status state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [infoMessage, setInfoMessage] = useState('');

  // --- Handlers ---
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setInfoMessage('');

    try {
      const response = await fetch('/api/auth/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.code === 'account_not_verified') {
          setOtpEmail(data.email || loginEmail);
          setIsVerifyingOtp(true);
          setInfoMessage('Tu cuenta requiere verificacion. Introduce el codigo OTP enviado a tu correo.');
          return;
        }
        throw new Error(data.detail || data.non_field_errors?.[0] || 'Credenciales invalidas');
      }

      localStorage.setItem('access_token', data.access);
      localStorage.setItem('refresh_token', data.refresh);
      if (data.user) {
        localStorage.setItem('user_profile', JSON.stringify(data.user));
      }

      router.push('/');
    } catch (err: any) {
      setError(err.message || 'Error al conectar con el servidor');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setInfoMessage('');

    if (regPassword !== regConfirmPassword) {
      setError('Las contrasenas no coinciden.');
      setLoading(false);
      return;
    }

    try {
      const response = await fetch('/api/auth/register/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name: regFirstName,
          last_name: regLastName,
          document_id: regDocumentId,
          phone: regPhone,
          email: regEmail,
          role: regRole,
          password: regPassword,
          confirm_password: regConfirmPassword,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        const errorKey = Object.keys(data)[0];
        const errorMsg = Array.isArray(data[errorKey]) ? data[errorKey][0] : data[errorKey];
        throw new Error(${errorKey}: );
      }

      setOtpEmail(regEmail);
      setIsVerifyingOtp(true);
      setInfoMessage('Registro exitoso. Se envio un codigo OTP de 6 digitos a tu correo.');
    } catch (err: any) {
      setError(err.message || 'Error al procesar el registro');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/auth/verify-code/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: otpEmail, code: otpCode.trim() }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.code?.[0] || data.detail || 'Codigo invalido o expirado');
      }

      setOtpSuccessMessage('Correo verificado exitosamente. Redirigiendo...');
      if (data.access) {
        localStorage.setItem('access_token', data.access);
        localStorage.setItem('refresh_token', data.refresh);
        if (data.user) {
          localStorage.setItem('user_profile', JSON.stringify(data.user));
        }
      }

      setTimeout(() => {
        router.push('/');
      }, 1000);
    } catch (err: any) {
      setError(err.message || 'Error al verificar el codigo');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setLoading(true);
    setError('');
    setInfoMessage('');

    try {
      const response = await fetch('/api/auth/resend-code/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: otpEmail }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.email?.[0] || data.detail || 'No se pudo reenviar el codigo');
      }

      setInfoMessage('Nuevo codigo OTP reenviado. Revisa tu bandeja o Mailpit.');
    } catch (err: any) {
      setError(err.message || 'Error al reenviar');
    } finally {
      setLoading(false);
    }
  };

  const handleRequestPasswordReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/auth/password-reset/request/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: resetEmail }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.email?.[0] || data.detail || 'Error al solicitar codigo');
      }

      setResetStep(2);
      setInfoMessage('Codigo de autorizacion enviado a tu correo.');
    } catch (err: any) {
      setError(err.message || 'Error al procesar la solicitud');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmPasswordReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    if (newPassword !== confirmNewPassword) {
      setError('Las contrasenas no coinciden.');
      setLoading(false);
      return;
    }

    try {
      const response = await fetch('/api/auth/password-reset/confirm/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: resetEmail,
          code: resetCode.trim(),
          new_password: newPassword,
          confirm_password: confirmNewPassword,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.code?.[0] || data.confirm_password?.[0] || data.detail || 'Error al actualizar contrasena');
      }

      setInfoMessage('Contrasena restablecida con exito. Ahora puedes iniciar sesion.');
      setIsResettingPassword(false);
      setResetStep(1);
      setActiveTab('login');
      setLoginEmail(resetEmail);
    } catch (err: any) {
      setError(err.message || 'Error al actualizar contrasena');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background Orbs */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[45%] h-[45%] rounded-full bg-blue-900/20 blur-[130px]"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[45%] h-[45%] rounded-full bg-indigo-900/20 blur-[130px]"></div>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md z-10 text-center">
        <div className="flex justify-center">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-xl shadow-blue-500/20 border border-blue-400/20">
            <Activity className="w-7 h-7 text-white" />
          </div>
        </div>
        <h1 className="mt-4 text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          AI-Triage
        </h1>
        <p className="mt-1 text-xs sm:text-sm text-slate-400">
          Plataforma de Soporte Clinico Hospitalario
        </p>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-lg z-10">
        <div className="bg-slate-900/80 backdrop-blur-xl py-6 px-4 shadow-2xl shadow-black/60 rounded-2xl sm:px-8 border border-slate-800">
          
          {/* Global Alert Messages */}
          {error && (
            <div className="mb-4 bg-red-950/40 border border-red-500/40 rounded-xl p-3 flex items-start gap-3">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <p className="text-xs text-red-200">{error}</p>
            </div>
          )}

          {infoMessage && (
            <div className="mb-4 bg-blue-950/40 border border-blue-500/40 rounded-xl p-3 flex items-start gap-3">
              <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
              <p className="text-xs text-blue-200">{infoMessage}</p>
            </div>
          )}

          {/* VIEW: OTP Verification */}
          {isVerifyingOtp ? (
            <div className="space-y-5">
              <div className="text-center">
                <div className="w-12 h-12 mx-auto rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-3">
                  <KeyRound className="w-6 h-6 text-emerald-400" />
                </div>
                <h2 className="text-lg font-bold text-white">Verificacion de Correo</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Introduce el codigo OTP de 6 digitos enviado a:
                  <span className="block font-semibold text-slate-200 mt-0.5">{otpEmail}</span>
                </p>
              </div>

              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 text-center mb-2">
                    Codigo OTP
                  </label>
                  <input
                    type="text"
                    required
                    maxLength={6}
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/[^0-9]/g, ''))}
                    className="block w-full text-center tracking-[10px] text-2xl font-mono bg-slate-950 border border-slate-700 rounded-xl py-3 text-emerald-400 placeholder-slate-600 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                    placeholder="000000"
                  />
                </div>

                {otpSuccessMessage && (
                  <p className="text-center text-xs text-emerald-400 font-medium animate-pulse">
                    {otpSuccessMessage}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading || otpCode.length < 6}
                  className="w-full py-3 px-4 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-lg shadow-emerald-600/20 transition-all disabled:opacity-50"
                >
                  {loading ? 'Verificando...' : 'Verificar y Continuar'}
                </button>

                <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs text-slate-400">
                  <button
                    type="button"
                    onClick={handleResendOtp}
                    disabled={loading}
                    className="flex items-center gap-1 text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Reenviar Codigo
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setIsVerifyingOtp(false);
                      setError('');
                    }}
                    className="flex items-center gap-1 text-slate-400 hover:text-slate-300 transition-colors"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" /> Volver
                  </button>
                </div>

                <div className="p-2.5 bg-slate-950/60 rounded-lg border border-slate-800 text-[10px] text-slate-500 text-center">
                  SMTP Local activo en Docker: Inspecciona el correo en <code className="text-blue-400">http://localhost:8025</code> (Mailpit).
                </div>
              </form>
            </div>
          ) : isResettingPassword ? (
            /* VIEW: Password Reset */
            <div className="space-y-5">
              <div className="text-center">
                <div className="w-12 h-12 mx-auto rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-3">
                  <Lock className="w-6 h-6 text-red-400" />
                </div>
                <h2 className="text-lg font-bold text-white">Recuperar Contrasena</h2>
                <p className="text-xs text-slate-400 mt-1">
                  {resetStep === 1 
                    ? 'Ingresa tu correo para recibir el codigo de autorizacion'
                    : Ingresa el codigo enviado a  y tu nueva clave}
                </p>
              </div>

              {resetStep === 1 ? (
                <form onSubmit={handleRequestPasswordReset} className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Correo Electronico
                    </label>
                    <div className="relative">
                      <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-3.5" />
                      <input
                        type="email"
                        required
                        value={resetEmail}
                        onChange={(e) => setResetEmail(e.target.value)}
                        className="block w-full pl-9 bg-slate-950 border border-slate-800 rounded-xl py-2.5 text-slate-200 text-xs focus:ring-2 focus:ring-blue-500"
                        placeholder="usuario@hospital.com"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-2.5 px-4 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 shadow-md transition-all disabled:opacity-50"
                  >
                    {loading ? 'Enviando...' : 'Enviar Codigo de Recuperacion'}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleConfirmPasswordReset} className="space-y-3">
                  <div>
                    <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1 text-center">
                      Codigo OTP de 6 Digitos
                    </label>
                    <input
                      type="text"
                      required
                      maxLength={6}
                      value={resetCode}
                      onChange={(e) => setResetCode(e.target.value.replace(/[^0-9]/g, ''))}
                      className="block w-full text-center tracking-[8px] text-xl font-mono bg-slate-950 border border-slate-700 rounded-xl py-2 text-red-400"
                      placeholder="000000"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Nueva Contrasena
                    </label>
                    <input
                      type="password"
                      required
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="block w-full bg-slate-950 border border-slate-800 rounded-xl py-2 px-3 text-slate-200 text-xs"
                      placeholder="Minimo 6 caracteres"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Confirmar Nueva Contrasena
                    </label>
                    <input
                      type="password"
                      required
                      value={confirmNewPassword}
                      onChange={(e) => setConfirmNewPassword(e.target.value)}
                      className="block w-full bg-slate-950 border border-slate-800 rounded-xl py-2 px-3 text-slate-200 text-xs"
                      placeholder="Repite la contrasena"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-2.5 px-4 rounded-xl text-xs font-semibold text-white bg-red-600 hover:bg-red-500 shadow-md transition-all disabled:opacity-50"
                  >
                    {loading ? 'Restableciendo...' : 'Guardar Nueva Contrasena'}
                  </button>
                </form>
              )}

              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsResettingPassword(false);
                    setResetStep(1);
                    setError('');
                  }}
                  className="text-xs text-slate-400 hover:text-slate-200 inline-flex items-center gap-1"
                >
                  <ArrowLeft className="w-3 h-3" /> Regresar al Inicio de Sesion
                </button>
              </div>
            </div>
          ) : (
            /* VIEW: Standard Tabbed Login & Register */
            <div>
              {/* Tabs Switcher */}
              <div className="flex border-b border-slate-800 mb-6">
                <button
                  onClick={() => { setActiveTab('login'); setError(''); setInfoMessage(''); }}
                  className={lex-1 pb-3 text-xs uppercase font-bold tracking-wider transition-all border-b-2 }
                >
                  Iniciar Sesion
                </button>
                <button
                  onClick={() => { setActiveTab('register'); setError(''); setInfoMessage(''); }}
                  className={lex-1 pb-3 text-xs uppercase font-bold tracking-wider transition-all border-b-2 }
                >
                  Registro Nuevo
                </button>
              </div>

              {activeTab === 'login' ? (
                /* TAB: Login */
                <form className="space-y-4" onSubmit={handleLogin}>
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Correo Electronico
                    </label>
                    <div className="relative">
                      <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-3.5" />
                      <input
                        type="email"
                        required
                        value={loginEmail}
                        onChange={(e) => setLoginEmail(e.target.value)}
                        className="block w-full pl-9 bg-slate-950 border border-slate-800 rounded-xl py-2.5 text-slate-200 text-xs focus:ring-2 focus:ring-blue-500"
                        placeholder="admin@hospital.com"
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="block text-xs font-medium text-slate-300">
                        Contrasena
                      </label>
                      <button
                        type="button"
                        onClick={() => { setIsResettingPassword(true); setError(''); }}
                        className="text-[11px] text-blue-400 hover:text-blue-300"
                      >
                        Olvidaste tu clave?
                      </button>
                    </div>
                    <div className="relative">
                      <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-3.5" />
                      <input
                        type={showLoginPassword ? 'text' : 'password'}
                        required
                        value={loginPassword}
                        onChange={(e) => setLoginPassword(e.target.value)}
                        className="block w-full pl-9 pr-9 bg-slate-950 border border-slate-800 rounded-xl py-2.5 text-slate-200 text-xs focus:ring-2 focus:ring-blue-500"
                        placeholder="••••••••"
                      />
                      <button
                        type="button"
                        onClick={() => setShowLoginPassword(!showLoginPassword)}
                        className="absolute right-3 top-3 text-slate-500 hover:text-slate-300"
                      >
                        {showLoginPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full flex justify-center items-center gap-2 py-3 px-4 rounded-xl text-xs font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-lg shadow-blue-600/20 transition-all disabled:opacity-50"
                  >
                    {loading ? 'Autenticando...' : 'Ingresar al Sistema'}
                    <ArrowRight className="w-4 h-4" />
                  </button>

                  <div className="p-2.5 bg-slate-950/60 rounded-lg border border-slate-800 text-[11px] text-slate-400 flex justify-between items-center">
                    <span>Usuario demo predeterminado:</span>
                    <span className="font-mono text-blue-400 font-bold">admin@hospital.com / admin</span>
                  </div>
                </form>
              ) : (
                /* TAB: Register */
                <form className="space-y-3" onSubmit={handleRegister}>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[11px] font-medium text-slate-300 mb-1">Nombre</label>
                      <div className="relative">
                        <User className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                        <input
                          type="text"
                          required
                          value={regFirstName}
                          onChange={(e) => setRegFirstName(e.target.value)}
                          className="block w-full pl-8 bg-slate-950 border border-slate-800 rounded-lg py-2 text-slate-200 text-xs"
                          placeholder="Carlos"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-slate-300 mb-1">Apellidos</label>
                      <input
                        type="text"
                        required
                        value={regLastName}
                        onChange={(e) => setRegLastName(e.target.value)}
                        className="block w-full px-3 bg-slate-950 border border-slate-800 rounded-lg py-2 text-slate-200 text-xs"
                        placeholder="Rodriguez"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[11px] font-medium text-slate-300 mb-1">Cedula / Tarjeta</label>
                      <div className="relative">
                        <FileBadge className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                        <input
                          type="text"
                          required
                          value={regDocumentId}
                          onChange={(e) => setRegDocumentId(e.target.value)}
                          className="block w-full pl-8 bg-slate-950 border border-slate-800 rounded-lg py-2 text-slate-200 text-xs"
                          placeholder="1020304050"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-slate-300 mb-1">Telefono</label>
                      <div className="relative">
                        <Phone className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                        <input
                          type="text"
                          value={regPhone}
                          onChange={(e) => setRegPhone(e.target.value)}
                          className="block w-full pl-8 bg-slate-950 border border-slate-800 rounded-lg py-2 text-slate-200 text-xs"
                          placeholder="+57 300 1234567"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    <div className="col-span-2">
                      <label className="block text-[11px] font-medium text-slate-300 mb-1">Correo Institucional</label>
                      <div className="relative">
                        <Mail className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                        <input
                          type="email"
                          required
                          value={regEmail}
                          onChange={(e) => setRegEmail(e.target.value)}
                          className="block w-full pl-8 bg-slate-950 border border-slate-800 rounded-lg py-2 text-slate-200 text-xs"
                          placeholder="doctor@hospital.com"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-slate-300 mb-1">Rol</label>
                      <select
                        value={regRole}
                        onChange={(e: any) => setRegRole(e.target.value)}
                        className="block w-full bg-slate-950 border border-slate-800 rounded-lg py-2 px-2 text-slate-200 text-xs"
                      >
                        <option value="medico">Medico</option>
                        <option value="enfermero">Enfermero</option>
                        <option value="admin">Administrador</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[11px] font-medium text-slate-300 mb-1">Contrasena</label>
                      <input
                        type={showRegPassword ? 'text' : 'password'}
                        required
                        value={regPassword}
                        onChange={(e) => setRegPassword(e.target.value)}
                        className="block w-full bg-slate-950 border border-slate-800 rounded-lg py-2 px-3 text-slate-200 text-xs"
                        placeholder="Minimo 6 digitos"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-slate-300 mb-1">Repetir Contrasena</label>
                      <input
                        type={showRegPassword ? 'text' : 'password'}
                        required
                        value={regConfirmPassword}
                        onChange={(e) => setRegConfirmPassword(e.target.value)}
                        className="block w-full bg-slate-950 border border-slate-800 rounded-lg py-2 px-3 text-slate-200 text-xs"
                        placeholder="Confirmar"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full mt-2 py-3 px-4 rounded-xl text-xs font-semibold text-white bg-gradient-to-r from-blue-600 to-emerald-600 hover:from-blue-500 hover:to-emerald-500 shadow-lg shadow-emerald-600/20 transition-all disabled:opacity-50"
                  >
                    {loading ? 'Procesando Registro...' : 'Completar Registro y Enviar Codigo'}
                  </button>
                </form>
              )}
            </div>
          )}

          <div className="mt-6 border-t border-slate-800/80 pt-4 flex items-center justify-center gap-2 text-xs text-slate-500">
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
            <span>Auditoria de seguridad y cifrado hospitalario activo</span>
          </div>
        </div>
      </div>
    </div>
  );
}
