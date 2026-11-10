import logging
from django.core.mail import EmailMultiAlternatives, get_connection
from django.conf import settings

logger = logging.getLogger(__name__)


def _resolve_from_email() -> str:
    default_from = getattr(settings, 'DEFAULT_FROM_EMAIL', 'AI-Triage <no-reply@hospital.com>')
    host_user = (getattr(settings, 'EMAIL_HOST_USER', '') or '').strip()
    if host_user and default_from == 'AI-Triage <no-reply@hospital.com>':
        return f"AI-Triage <{host_user}>"
    return default_from


def _dispatch_email(subject: str, text_content: str, html_content: str, recipient: str) -> bool:
    from_email = _resolve_from_email()
    to_email = [recipient]
    sent_primary = False

    msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
    msg.attach_alternative(html_content, "text/html")
    try:
        msg.send(fail_silently=False)
        logger.info(f"Correo enviado exitosamente a {recipient} via {getattr(settings, 'EMAIL_HOST', 'default')}")
        sent_primary = True
    except Exception as e:
        logger.error(f"Fallo al enviar correo primario a {recipient}: {e}")

    # Si el servidor primario es externo (ej. smtp.gmail.com), replicar o hacer fallback en Mailpit local
    primary_host = (getattr(settings, 'EMAIL_HOST', '') or '').strip().lower()
    if primary_host not in ('mailpit', 'localhost', '127.0.0.1'):
        try:
            mailpit_conn = get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                host='mailpit',
                port=1025,
                username='',
                password='',
                use_tls=False,
                fail_silently=True,
            )
            mirror_msg = EmailMultiAlternatives(subject, text_content, from_email, to_email, connection=mailpit_conn)
            mirror_msg.attach_alternative(html_content, "text/html")
            mirror_msg.send(fail_silently=True)
        except Exception:
            pass

    return sent_primary


def send_verification_email(user, code: str):
    """
    Envia correo de verificacion de registro con codigo OTP de 6 digitos.
    Estilizado con la paleta de colores oscuros y diseno clinico del proyecto AI-Triage.
    """
    subject = f"Codigo de Verificacion AI-Triage: {code}"

    text_content = f"""
AI-Triage - Sistema de Clasificacion Medica Inteligente
Hola {user.full_name},

Tu codigo de verificacion para activar tu cuenta es: {code}

Este codigo es valido durante 15 minutos. Si no solicitaste este registro, por favor ignora este mensaje.
"""

    html_content = f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verificacion de Cuenta - AI-Triage</title>
</head>
<body style="margin: 0; padding: 0; background-color: #020617; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #020617; padding: 40px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" max-width="540px" style="max-width: 540px; background-color: #0f172a; border: 1px solid #1e293b; border-radius: 16px; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 24px; background: linear-gradient(135deg, rgba(37, 99, 235, 0.15) 0%, rgba(16, 185, 129, 0.1) 100%); border-bottom: 1px solid #1e293b;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td>
                    <div style="display: inline-block; background: #2563eb; color: #ffffff; font-weight: 800; font-size: 14px; padding: 6px 12px; border-radius: 8px; letter-spacing: 1px;">AI</div>
                    <span style="margin-left: 10px; font-size: 16px; font-weight: 700; letter-spacing: 1.5px; color: #e2e8f0; text-transform: uppercase;">AI-Triage</span>
                  </td>
                  <td align="right">
                    <span style="font-size: 11px; font-weight: 600; color: #10b981; background-color: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.5px;">Seguridad Clinica</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding: 32px;">
              <h1 style="margin: 0 0 12px; font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">Verificacion de Cuenta</h1>
              <p style="margin: 0 0 24px; font-size: 14px; line-height: 1.6; color: #94a3b8;">
                Estimado(a) <strong style="color: #f1f5f9;">{user.full_name}</strong>, para completar tu registro en el sistema hospitalario AI-Triage e iniciar sesion, introduce el siguiente codigo de un solo uso (OTP):
              </p>

              <!-- OTP Block -->
              <div style="text-align: center; margin: 32px 0;">
                <div style="display: inline-block; background-color: #020617; border: 1px solid #334155; border-radius: 12px; padding: 18px 36px; box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6);">
                  <span style="font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace; font-size: 32px; font-weight: 800; letter-spacing: 10px; color: #38bdf8;">{code}</span>
                </div>
              </div>

              <div style="background-color: rgba(30, 41, 59, 0.6); border-left: 3px solid #3b82f6; border-radius: 6px; padding: 12px 16px; margin-bottom: 24px;">
                <p style="margin: 0; font-size: 12px; line-height: 1.5; color: #cbd5e1;">
                  El codigo de seguridad expirara en <strong>15 minutos</strong>. No compartas este codigo con nadie.
                </p>
              </div>

              <p style="margin: 0; font-size: 13px; color: #64748b; line-height: 1.5;">
                Rol asignado: <span style="color: #93c5fd; text-transform: uppercase; font-weight: 600;">{user.role}</span><br>
                Identificacion: <span style="color: #cbd5e1;">{user.document_id or 'No registrada'}</span>
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 24px 32px; background-color: #090d16; border-top: 1px solid #1e293b; text-align: center;">
              <p style="margin: 0 0 6px; font-size: 11px; color: #475569;">
                AI-Triage - Asistente Inteligente de Triaje y Soporte Clinico Hospitalario
              </p>
              <p style="margin: 0; font-size: 10px; color: #334155;">
                Mensaje automatico emitido conforme a protocolos de seguridad de historia clinica y datos en salud.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return _dispatch_email(subject, text_content, html_content, user.email)

def send_password_reset_email(user, code: str):
    """
    Envia correo para restablecer contrasena con codigo OTP de 6 digitos.
    """
    subject = f"Restablecimiento de Contrasena AI-Triage: {code}"

    text_content = f"""
AI-Triage - Recuperacion de Acceso
Hola {user.full_name},

Se ha solicitado restablecer la contrasena de tu cuenta en AI-Triage.
Tu codigo de autorizacion es: {code}

Este codigo expira en 15 minutos. Si tu no realizaste esta solicitud, reportalo de inmediato al administrador.
"""

    html_content = f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Recuperacion de Acceso - AI-Triage</title>
</head>
<body style="margin: 0; padding: 0; background-color: #020617; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #020617; padding: 40px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" max-width="540px" style="max-width: 540px; background-color: #0f172a; border: 1px solid #1e293b; border-radius: 16px; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 24px; background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(245, 158, 11, 0.1) 100%); border-bottom: 1px solid #1e293b;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td>
                    <div style="display: inline-block; background: #dc2626; color: #ffffff; font-weight: 800; font-size: 14px; padding: 6px 12px; border-radius: 8px; letter-spacing: 1px;">AI</div>
                    <span style="margin-left: 10px; font-size: 16px; font-weight: 700; letter-spacing: 1.5px; color: #e2e8f0; text-transform: uppercase;">AI-Triage</span>
                  </td>
                  <td align="right">
                    <span style="font-size: 11px; font-weight: 600; color: #f87171; background-color: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.5px;">Recuperacion</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding: 32px;">
              <h1 style="margin: 0 0 12px; font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">Solicitud de Nueva Contrasena</h1>
              <p style="margin: 0 0 24px; font-size: 14px; line-height: 1.6; color: #94a3b8;">
                Hola <strong style="color: #f1f5f9;">{user.full_name}</strong>, hemos recibido una peticion para reestablecer la clave de acceso a tu panel hospitalario. Usa el siguiente codigo OTP:
              </p>

              <!-- OTP Block -->
              <div style="text-align: center; margin: 32px 0;">
                <div style="display: inline-block; background-color: #020617; border: 1px solid #334155; border-radius: 12px; padding: 18px 36px; box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6);">
                  <span style="font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace; font-size: 32px; font-weight: 800; letter-spacing: 10px; color: #f87171;">{code}</span>
                </div>
              </div>

              <div style="background-color: rgba(30, 41, 59, 0.6); border-left: 3px solid #ef4444; border-radius: 6px; padding: 12px 16px; margin-bottom: 24px;">
                <p style="margin: 0; font-size: 12px; line-height: 1.5; color: #cbd5e1;">
                  Este codigo vence en <strong>15 minutos</strong>. Si no solicitaste este cambio, no hagas nada y reportalo a seguridad de TI.
                </p>
              </div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 24px 32px; background-color: #090d16; border-top: 1px solid #1e293b; text-align: center;">
              <p style="margin: 0; font-size: 10px; color: #475569;">
                Servicio seguro de emision de credenciales medicas AI-Triage
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return _dispatch_email(subject, text_content, html_content, user.email)
