from django.urls import path
from .views import (
    UserListView,
    UserPermissionUpdateView,
    AuditLogListView
)

urlpatterns = [
    path('users/', UserListView.as_view(), name='security_users_list'),
    path('users/<int:user_id>/permissions/', UserPermissionUpdateView.as_view(), name='security_user_permissions'),
    path('audit/', AuditLogListView.as_view(), name='security_audit'),
    path('audit-logs/', AuditLogListView.as_view(), name='security_audit_logs'),
]
