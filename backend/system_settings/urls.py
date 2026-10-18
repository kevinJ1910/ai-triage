from django.urls import path
from .views import (
    SystemConfigView,
    APIKeyListView,
    APIKeyDetailView,
    VocabularySyncView,
    EngineStatusView,
)

urlpatterns = [
    path('', SystemConfigView.as_view(), name='system_config'),
    path('keys/', APIKeyListView.as_view(), name='api_keys_list'),
    path('keys/<int:key_id>/', APIKeyDetailView.as_view(), name='api_key_detail'),
    path('vocabulary/sync/', VocabularySyncView.as_view(), name='vocabulary_sync'),
    path('engines/', EngineStatusView.as_view(), name='engine_status'),
]
