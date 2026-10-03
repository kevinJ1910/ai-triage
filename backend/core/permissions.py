from rest_framework.permissions import BasePermission


def user_has_flag(user, flag: str) -> bool:
    """
    Evalua un permiso granular de accounts.UserPermission en el servidor.
    Administradores y superusuarios tienen todos los permisos.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'role', None) == 'admin':
        return True
    from accounts.models import UserPermission
    try:
        return bool(getattr(user.permissions, flag, False))
    except UserPermission.DoesNotExist:
        return False


class _PermissionFlag(BasePermission):
    flag = ''

    def has_permission(self, request, view):
        return user_has_flag(request.user, self.flag)


def permission_flag(flag: str):
    """Construye una clase de permiso DRF ligada a un campo de UserPermission."""
    return type(
        f'HasFlag_{flag}',
        (_PermissionFlag,),
        {'flag': flag, 'message': f'Permiso denegado: se requiere {flag}.'},
    )


CanUseTranscriber = permission_flag('can_use_transcriber')
CanEditSymptoms = permission_flag('can_edit_symptoms')
CanRegisterPatients = permission_flag('can_register_patients')
CanViewEMR = permission_flag('can_view_emr')
CanViewFHIR = permission_flag('can_view_fhir')
