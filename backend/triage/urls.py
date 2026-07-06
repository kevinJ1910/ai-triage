from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TriageSessionViewSet

router = DefaultRouter()
router.register(r'sessions', TriageSessionViewSet, basename='triage-session')

urlpatterns = [
    path('', include(router.urls)),
]
