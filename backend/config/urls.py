from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from transcription.views import health_check as transcription_health_check
from triage.views import fhir_sync as triage_fhir_sync

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/', include('accounts.urls')),
    path('api/security/', include('accounts.urls_security')),
    path('api/config/', include('system_settings.urls')),
    path('api/triage/', include('triage.urls')),
    path('api/health_check/', transcription_health_check, name='api_health_check'),
    path('api/health_check', transcription_health_check, name='api_health_check_no_slash'),
    path('api/fhir', triage_fhir_sync, name='fhir_sync_no_slash'),
    path('api/fhir/', triage_fhir_sync, name='fhir_sync'),
    path('api/', include('transcription.urls')),
]
