from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubscriptionViewSet, ingest_webhook, webhook_status, subscription_logs

router = DefaultRouter()
router.register(r'subscriptions', SubscriptionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('ingest/<uuid:subscription_id>/', ingest_webhook),
    path('webhooks/<uuid:webhook_id>/status/', webhook_status),
    path('subscriptions/<uuid:subscription_id>/logs/', subscription_logs),
]