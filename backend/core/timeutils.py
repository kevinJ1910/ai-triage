from django.utils import timezone


def local_strftime(dt, fmt: str) -> str:
    """Formatea un datetime aware en la zona horaria del proyecto (settings.TIME_ZONE), no en UTC."""
    return timezone.localtime(dt).strftime(fmt)
