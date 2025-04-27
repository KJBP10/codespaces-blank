# webhook_project/urls.py
from django.urls import path, include
from django.views.generic.base import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/ui/subscriptions/create/', permanent=False), name='home'),
    path('ui/', include('webhook.urls')),
    path('api/', include('webhook.urls')),
]