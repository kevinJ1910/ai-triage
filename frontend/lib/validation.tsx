import React from 'react';
import { AlertTriangle } from 'lucide-react';

export interface ValidationResult {
  isValid: boolean;
  warning?: string;
}

/**
 * Validador tipado de correo electronico
 */
export function validateEmail(value: string): ValidationResult {
  if (!value || !value.trim()) {
    return { isValid: false, warning: 'El correo electronico es requerido.' };
  }
  const clean = value.trim();
  const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
  if (!emailRegex.test(clean)) {
    return { isValid: false, warning: 'Formato de correo electronico invalido (ej. usuario@hospital.com).' };
  }
  return { isValid: true };
}

/**
 * Validador tipado para valores numericos con rangos opcionales
 */
export function validateNumeric(
  value: string | number,
  opts?: { min?: number; max?: number; integerOnly?: boolean; label?: string }
): ValidationResult {
  const str = String(value).trim();
  const label = opts?.label || 'El valor';

  if (!str) {
    return { isValid: false, warning: `${label} es requerido.` };
  }

  const num = Number(str);
  if (isNaN(num)) {
    return { isValid: false, warning: `${label} debe ser un valor numerico valido.` };
  }

  if (opts?.integerOnly && !Number.isInteger(num)) {
    return { isValid: false, warning: `${label} debe ser un numero entero.` };
  }

  if (opts?.min !== undefined && num < opts.min) {
    return { isValid: false, warning: `${label} no puede ser menor a ${opts.min}.` };
  }

  if (opts?.max !== undefined && num > opts.max) {
    return { isValid: false, warning: `${label} no puede ser mayor a ${opts.max}.` };
  }

  return { isValid: true };
}

/**
 * Validador tipado para fechas (YYYY-MM-DD)
 */
export function validateDate(
  value: string,
  opts?: { maxDate?: string; minDate?: string; label?: string }
): ValidationResult {
  const label = opts?.label || 'La fecha';
  if (!value || !value.trim()) {
    return { isValid: false, warning: `${label} es requerida.` };
  }

  const parsed = new Date(value);
  if (isNaN(parsed.getTime())) {
    return { isValid: false, warning: `${label} no tiene un formato de fecha valido (AAAA-MM-DD).` };
  }

  if (opts?.maxDate) {
    const max = new Date(opts.maxDate);
    if (parsed > max) {
      return { isValid: false, warning: `${label} no puede ser posterior a ${opts.maxDate}.` };
    }
  }

  if (opts?.minDate) {
    const min = new Date(opts.minDate);
    if (parsed < min) {
      return { isValid: false, warning: `${label} no puede ser anterior a ${opts.minDate}.` };
    }
  }

  return { isValid: true };
}

/**
 * Validador tipado para codigos OTP (exactamente 6 digitos numericos)
 */
export function validateOtpCode(value: string): ValidationResult {
  if (!value || !value.trim()) {
    return { isValid: false, warning: 'El codigo de verificacion es requerido.' };
  }
  const clean = value.trim();
  if (!/^\d+$/.test(clean)) {
    return { isValid: false, warning: 'El codigo debe contener solo digitos numericos.' };
  }
  if (clean.length !== 6) {
    return { isValid: false, warning: `El codigo debe tener exactamente 6 digitos (actual: ${clean.length}).` };
  }
  return { isValid: true };
}

/**
 * Validador tipado para documentos de identidad
 */
export function validateDocumentId(value: string): ValidationResult {
  if (!value || !value.trim()) {
    return { isValid: false, warning: 'El documento de identidad es requerido.' };
  }
  const clean = value.trim();
  if (clean.length < 3) {
    return { isValid: false, warning: 'El documento debe tener al menos 3 caracteres.' };
  }
  if (!/^[a-zA-Z0-9-]+$/.test(clean)) {
    return { isValid: false, warning: 'El documento solo puede contener letras, numeros o guiones.' };
  }
  return { isValid: true };
}

/**
 * Validador tipado para telefonos
 */
export function validatePhone(value: string): ValidationResult {
  if (!value || !value.trim()) {
    return { isValid: true }; // Campo opcional
  }
  const clean = value.trim();
  const digitsCount = (clean.match(/\d/g) || []).length;
  if (!/^\+?[0-9\s-]{7,20}$/.test(clean) || digitsCount < 7) {
    return {
      isValid: false,
      warning: 'Formato de telefono invalido (debe contener entre 7 y 20 caracteres: digitos, espacios, guiones o prefijo + opcional).'
    };
  }
  return { isValid: true };
}

/**
 * Validador tipado para contrasenas
 */
export function validatePassword(password: string, confirmPassword?: string): ValidationResult {
  if (!password) {
    return { isValid: false, warning: 'La contrasena es requerida.' };
  }
  if (password.length < 6) {
    return { isValid: false, warning: 'La contrasena debe tener al menos 6 caracteres.' };
  }
  if (confirmPassword !== undefined && password !== confirmPassword) {
    return { isValid: false, warning: 'Las contrasenas no coinciden.' };
  }
  return { isValid: true };
}

/**
 * Componente visual reutilizable para advertencias en formularios
 */
export function InputWarning({ warning, id }: { warning?: string | null; id?: string }) {
  if (!warning) return null;
  return (
    <div 
      id={id} 
      role="alert" 
      className="flex items-center gap-1.5 mt-1 text-[11px] text-amber-400 font-medium animate-fadeIn"
    >
      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
      <span>{warning}</span>
    </div>
  );
}
