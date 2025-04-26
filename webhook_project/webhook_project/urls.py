from django.urls import path, include

urlpatterns = [
    path('', include('webhook.urls')),  # Include webhook.urls at the root level
]