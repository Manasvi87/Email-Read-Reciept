from django.urls import path

from . import views

app_name = 'tracker'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/emails', views.api_emails, name='api_emails'),
    path('track/<str:email_id>.png', views.track_pixel, name='track_pixel'),
]