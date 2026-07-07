from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from transcription.views import health_check as transcription_health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/triage/', include('triage.urls')),
    path('api/health_check/', transcription_health_check, name='api_health_check'),
    path('api/health_check', transcription_health_check, name='api_health_check_no_slash'),
    path('api/', include('transcription.urls')),
]
