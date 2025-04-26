from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Subscription, WebhookDeliveryLog
from .serializers import SubscriptionSerializer, WebhookPayloadSerializer
from .tasks import deliver_webhook
import uuid
from celery import uuid as celery_uuid
from redis import Redis
import json
import logging
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

redis = Redis(host='redis', port=6379, db=0)
logger = logging.getLogger(__name__)

class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = [AllowAny]

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def ingest_webhook(request, subscription_id):
    """
    Handle webhook ingestion for a given subscription.
    Returns 202 Accepted with a webhook_id if successful, or appropriate error status.
    """
    try:
        subscription = Subscription.objects.get(id=subscription_id)
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found: {subscription_id}")
        return Response({"error": "Subscription not found"}, status=404)

    event_type = request.headers.get("X-Event-Type")
    if event_type and event_type not in subscription.event_types:
        logger.info(f"Event ignored for subscription {subscription_id}, event_type: {event_type}")
        return Response({"message": "Event ignored (not subscribed)"}, status=204)

    serializer = WebhookPayloadSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error(f"Invalid payload for subscription {subscription_id}: {serializer.errors}")
        return Response(serializer.errors, status=400)

    webhook_id = str(uuid.uuid4())
    logger.info(f"Generated webhook_id: {webhook_id} for subscription_id: {subscription_id}")

    # Use Redis to prevent duplicate processing (expire after 1 hour)
    redis_key = f"webhook:{webhook_id}"
    if redis.set(redis_key, "1", ex=3600, nx=True):
        logger.info(f"Redis lock acquired for webhook_id: {webhook_id}")
        # Generate a unique task ID to prevent Celery duplicate queuing
        task_id = celery_uuid()
        logger.info(f"Queuing deliver_webhook task with webhook_id: {webhook_id}, task_id: {task_id}")
        deliver_webhook.apply_async(
            args=(webhook_id, str(subscription.id), json.dumps(serializer.validated_data['data']), event_type),
            kwargs={'task_id': task_id},
            task_id=task_id
        )
    else:
        logger.warning(f"Webhook already processed: {webhook_id}")
        return Response({"error": "Webhook already processed"}, status=409)

    return Response({"message": "Webhook received", "webhook_id": webhook_id}, status=202)

@api_view(['GET'])
@permission_classes([AllowAny])
@vary_on_headers('X-Event-Type')
@cache_page(60 * 15)
def webhook_status(request, webhook_id):
    """
    Retrieve the status of all delivery attempts for a given webhook_id.
    """
    try:
        logs = WebhookDeliveryLog.objects.filter(webhook_id=webhook_id).order_by('attempt_number')
        if not logs.exists():
            return Response({"error": "No logs found for this webhook_id"}, status=404)
        
        response_data = {
            "webhook_id": str(webhook_id),
            "logs": [
                {
                    "attempt_number": log.attempt_number,
                    "outcome": log.outcome,
                    "http_status": log.http_status,
                    "error_details": log.error_details,
                    "created_at": log.created_at.isoformat()
                } for log in logs
            ]
        }
        return Response(response_data)
    except Exception as e:
        logger.error(f"Error retrieving webhook status for {webhook_id}: {str(e)}")
        return Response({"error": "Internal server error"}, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
@cache_page(60 * 15)
def subscription_logs(request, subscription_id):
    """
    Retrieve the last 20 delivery logs for a given subscription_id.
    """
    try:
        subscription = Subscription.objects.get(id=subscription_id)
        logs = WebhookDeliveryLog.objects.filter(subscription_id=subscription_id).order_by('-created_at')[:20]
        if not logs.exists():
            return Response({"error": "No logs found for this subscription"}, status=404)
        
        response_data = [
            {
                "webhook_id": str(log.webhook_id),
                "subscription_id": str(subscription_id),
                "attempt_number": log.attempt_number,
                "outcome": log.outcome,
                "http_status": log.http_status,
                "error_details": log.error_details,
                "created_at": log.created_at.isoformat()
            } for log in logs
        ]
        return Response(response_data)
    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found: {subscription_id}")
        return Response({"error": "Subscription not found"}, status=404)
    except Exception as e:
        logger.error(f"Error retrieving subscription logs for {subscription_id}: {str(e)}")
        return Response({"error": "Internal server error"}, status=500)