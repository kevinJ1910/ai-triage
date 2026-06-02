from django.urls import path
from . import views

urlpatterns = [
    path('transcribe/', views.transcribe_chunk, name='transcribe_chunk'),
    path('transcribe/reset/', views.reset_session, name='reset_session'),
    path('transcribe/health/', views.health_check, name='health_check'),
]
