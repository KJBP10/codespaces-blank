# webhook/urls.py
from django.urls import path
from .views import (
    SubscriptionListView,
    SubscriptionCreateView,
    SubscriptionUpdateView,
    SubscriptionDetailView,
    ingest_webhook,
    subscription_logs,
    webhook_status,
)

urlpatterns = [
    # UI routes
    path('subscriptions/', SubscriptionListView.as_view(), name='subscription_list'),
    path('subscriptions/create/', SubscriptionCreateView.as_view(), name='subscription_create'),
    path('subscriptions/<uuid:pk>/update/', SubscriptionUpdateView.as_view(), name='subscription_update'),
    path('subscriptions/<uuid:pk>/', SubscriptionDetailView.as_view(), name='subscription_detail'),
    # API routes
    path('ingest/<uuid:subscription_id>/', ingest_webhook, name='ingest_webhook'),
    path('webhooks/<uuid:webhook_id>/status/', webhook_status, name='webhook_status'),
    path('subscriptions/<uuid:subscription_id>/logs/', subscription_logs, name='subscription_logs'),
]