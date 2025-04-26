from celery import Celery, shared_task
from django.utils import timezone
import requests
import json
import logging
from webhook.models import Subscription, WebhookDeliveryLog
from django.core.cache import cache
from datetime import timedelta
import hmac
import hashlib

app = Celery('webhook_project')
app.config_from_object('django.conf:settings', namespace='CELERY')

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=5)
def deliver_webhook(self, webhook_id, subscription_id, payload, event_type):
    # Cache subscription details
    cache_key = f"subscription:{subscription_id}"
    subscription_data = cache.get(cache_key)

    if not subscription_data:
        subscription = Subscription.objects.get(id=subscription_id)
        subscription_data = {
            'callback_url': subscription.callback_url,
            'event_types': subscription.event_types,
            'secret_key': subscription.secret_key
        }
        cache.set(cache_key, subscription_data, timeout=3600)  # Cache for 1 hour
        logger.info(f"Cached subscription {subscription_id}")

    attempt_number = self.request.retries + 1
    delivery_log = WebhookDeliveryLog(
        webhook_id=webhook_id,
        subscription_id=subscription_id,
        attempt_number=attempt_number,
        created_at=timezone.now()
    )

    try:
        logger.info(f"Delivering webhook {webhook_id} to {subscription_data['callback_url']}, attempt {attempt_number}")

        headers = {
            'X-Event-Type': event_type,
            'X-Webhook-ID': webhook_id,
            'Content-Type': 'application/json',
        }
        if subscription_data['secret_key']:
            payload_bytes = payload.encode('utf-8')
            signature = hmac.new(
                subscription_data['secret_key'].encode('utf-8'),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            headers['X-Hub-Signature-256'] = f'sha256={signature}'

        response = requests.post(
            subscription_data['callback_url'],
            data=payload,
            headers=headers,
            timeout=10
        )

        delivery_log.http_status = response.status_code
        delivery_log.outcome = 'success' if 200 <= response.status_code < 300 else 'failed_attempt'
        delivery_log.error_details = response.text if response.status_code >= 400 else None
        delivery_log.save()

        if delivery_log.outcome != 'success':
            raise Exception(f"Failed with status {response.status_code}: {response.text}")

        logger.info(f"Webhook {webhook_id} delivered successfully")

    except Exception as e:
        delivery_log.outcome = 'failure' if attempt_number == self.max_retries + 1 else 'failed_attempt'
        delivery_log.error_details = str(e)
        if 'response' in locals():
            delivery_log.http_status = response.status_code
        else:
            delivery_log.http_status = 503  # Service unavailable for network/timeout errors
        delivery_log.save()

        if attempt_number <= self.max_retries:
            delays = [10, 30, 60, 300, 900]
            delay = delays[attempt_number - 1] if attempt_number - 1 < len(delays) else 900
            logger.warning(f"Retrying webhook {webhook_id} (attempt {attempt_number + 1}/{self.max_retries + 1}) after {delay}s")
            raise self.retry(countdown=delay)
        else:
            logger.error(f"All retries failed for webhook {webhook_id}: {str(e)}")
            raise Exception(f"All retries failed for webhook {webhook_id}: {str(e)}")

@shared_task
def cleanup_old_logs():
    cutoff = timezone.now() - timedelta(hours=72)
    deleted_count, _ = WebhookDeliveryLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"Deleted {deleted_count} old webhook delivery logs")