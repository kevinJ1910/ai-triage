import { describe, it, expect } from 'vitest';
import {
  validateEmail,
  validateNumeric,
  validateDate,
  validateOtpCode,
  validateDocumentId,
  validatePhone,
  validatePassword,
} from '../lib/validation';

describe('Frontend Validation Module', () => {
  describe('validateEmail', () => {
    it('accepts valid email addresses', () => {
      expect(validateEmail('doctor@hospital.com').isValid).toBe(true);
      expect(validateEmail('admin.urgencias@salud.gov.co').isValid).toBe(true);
    });

    it('rejects invalid emails and returns descriptive warning', () => {
      const res1 = validateEmail('not-an-email');
      expect(res1.isValid).toBe(false);
      expect(res1.warning).toContain('Formato de correo electronico invalido');

      const res2 = validateEmail('missingdomain@');
      expect(res2.isValid).toBe(false);

      const res3 = validateEmail('');
      expect(res3.isValid).toBe(false);
      expect(res3.warning).toContain('requerido');
    });
  });

  describe('validateNumeric', () => {
    it('accepts valid numbers and adheres to bounds', () => {
      expect(validateNumeric('42').isValid).toBe(true);
      expect(validateNumeric(100, { min: 10, max: 200 }).isValid).toBe(true);
    });

    it('rejects non-numeric strings with warning', () => {
      const res = validateNumeric('abc', { label: 'El nivel' });
      expect(res.isValid).toBe(false);
      expect(res.warning).toContain('debe ser un valor numerico');
    });

    it('validates min and max constraints', () => {
      const resMin = validateNumeric(5, { min: 10, label: 'El tiempo' });
      expect(resMin.isValid).toBe(false);
      expect(resMin.warning).toContain('no puede ser menor a 10');

      const resMax = validateNumeric(250, { max: 100, label: 'La dosis' });
      expect(resMax.isValid).toBe(false);
      expect(resMax.warning).toContain('no puede ser mayor a 100');
    });

    it('enforces integerOnly constraint', () => {
      const res = validateNumeric('3.14', { integerOnly: true, label: 'El nivel' });
      expect(res.isValid).toBe(false);
      expect(res.warning).toContain('numero entero');
    });
  });

  describe('validateDate', () => {
    it('accepts valid date strings', () => {
      expect(validateDate('1990-05-15').isValid).toBe(true);
    });

    it('rejects invalid date format', () => {
      const res = validateDate('not-a-date');
      expect(res.isValid).toBe(false);
      expect(res.warning).toContain('formato de fecha valido');
    });

    it('validates maxDate constraint (no future birth dates)', () => {
      const res = validateDate('2099-01-01', { maxDate: '2026-09-10', label: 'Fecha de nacimiento' });
      expect(res.isValid).toBe(false);
      expect(res.warning).toContain('no puede ser posterior a');
    });
  });

  describe('validateOtpCode', () => {
    it('accepts exactly 6 numeric digits', () => {
      expect(validateOtpCode('123456').isValid).toBe(true);
      expect(validateOtpCode('000000').isValid).toBe(true);
    });

    it('rejects non-numeric characters', () => {
      const res = validateOtpCode('12A456');
      expect(res.isValid).toBe(false);
      expect(res.warning).toContain('solo digitos numericos');
    });

    it('rejects length not equal to 6', () => {
      const resShort = validateOtpCode('12345');
      expect(resShort.isValid).toBe(false);
      expect(resShort.warning).toContain('exactamente 6 digitos');

      const resLong = validateOtpCode('1234567');
      expect(resLong.isValid).toBe(false);
      expect(resLong.warning).toContain('exactamente 6 digitos');
    });
  });

  describe('validateDocumentId', () => {
    it('accepts valid document IDs', () => {
      expect(validateDocumentId('1098765432').isValid).toBe(true);
      expect(validateDocumentId('CC-889977').isValid).toBe(true);
    });

    it('rejects too short or invalid characters', () => {
      const resShort = validateDocumentId('12');
      expect(resShort.isValid).toBe(false);
      expect(resShort.warning).toContain('al menos 3 caracteres');

      const resInvalid = validateDocumentId('DOC #123');
      expect(resInvalid.isValid).toBe(false);
      expect(resInvalid.warning).toContain('letras, numeros o guiones');
    });
  });

  describe('validatePassword', () => {
    it('validates length and confirmation matching', () => {
      expect(validatePassword('SecurePass123!').isValid).toBe(true);
      expect(validatePassword('SecurePass123!', 'SecurePass123!').isValid).toBe(true);

      const resShort = validatePassword('123');
      expect(resShort.isValid).toBe(false);
      expect(resShort.warning).toContain('al menos 6 caracteres');

      const resMismatch = validatePassword('Password123!', 'DifferentPass123!');
      expect(resMismatch.isValid).toBe(false);
      expect(resMismatch.warning).toContain('no coinciden');
    });
  });
});
