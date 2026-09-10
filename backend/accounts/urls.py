from django.urls import path
from .views import (
    CustomTokenObtainPairView,
    RegisterView,
    VerifyCodeView,
    ResendCodeView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    UserProfileView,
    UserListView,
    UserPermissionUpdateView,
    AuditLogListView
)

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='auth_login'),
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('verify/', VerifyCodeView.as_view(), name='auth_verify'),
    path('verify-code/', VerifyCodeView.as_view(), name='auth_verify_code'),
    path('resend-code/', ResendCodeView.as_view(), name='auth_resend_code'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='auth_password_reset'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='auth_password_reset_request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='auth_password_reset_confirm'),
    path('me/', UserProfileView.as_view(), name='auth_me'),
    
    # Rutas RBAC y Seguridad
    path('users/', UserListView.as_view(), name='security_users_list'),
    path('users/<int:user_id>/permissions/', UserPermissionUpdateView.as_view(), name='security_user_permissions'),
    path('audit/', AuditLogListView.as_view(), name='security_audit'),
    path('audit-logs/', AuditLogListView.as_view(), name='security_audit_logs'),
]
