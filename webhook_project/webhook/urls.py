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
    path('ui/subscriptions/', SubscriptionListView.as_view(), name='subscription_list'),
    path('ui/subscriptions/create/', SubscriptionCreateView.as_view(), name='subscription_create'),
    path('ui/subscriptions/<uuid:pk>/update/', SubscriptionUpdateView.as_view(), name='subscription_update'),
    path('ui/subscriptions/<uuid:pk>/', SubscriptionDetailView.as_view(), name='subscription_detail'),
    # API routes
    path('api/ingest/<uuid:subscription_id>/', ingest_webhook, name='ingest_webhook'),
    path('api/webhooks/<uuid:webhook_id>/status/', webhook_status, name='webhook_status'),
    path('api/subscriptions/<uuid:subscription_id>/logs/', subscription_logs, name='subscription_logs'),
]