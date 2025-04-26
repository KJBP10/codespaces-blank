from celery import Celery
from celery.exceptions import Retry
from django.utils import timezone
import requests
import json
import logging
from webhook.models import Subscription, WebhookDeliveryLog
from redis import Redis, RedisError

app = Celery('webhook_project')
app.config_from_object('django.conf:settings', namespace='CELERY')

logger = logging.getLogger(__name__)
redis = Redis(host='redis', port=6379, db=0)

@app.task(bind=True, max_retries=6)
def deliver_webhook(self, webhook_id, subscription_id, payload, event_type, task_id=None):
    try:
        # Use a lock key that includes attempt number to allow retries
        task_lock_key = f"task_lock:{webhook_id}:{self.request.retries + 1}"
        if not redis.set(task_lock_key, "1", ex=3600, nx=True):
            logger.info(f"Task already being processed for webhook_id: {webhook_id}, attempt: {self.request.retries + 1}")
            return

        logger.info(f"Processing deliver_webhook task for webhook_id: {webhook_id}, subscription_id: {subscription_id}")
        subscription = Subscription.objects.get(id=subscription_id)
        attempt_number = self.request.retries + 1

        headers = {
            "X-Event-Type": event_type or "",
            "X-Webhook-ID": webhook_id,
            "X-Attempt-Number": str(attempt_number),
        }

        logger.info(f"Attempt {attempt_number}: Sending POST to {subscription.callback_url} with headers: {headers}")
        response = requests.post(subscription.callback_url, data=payload, headers=headers, timeout=10)
        logger.info(f"Received response: status={response.status_code}, body={response.text[:500]}...")

        outcome = "success" if response.status_code == 200 else "failed_attempt"
        WebhookDeliveryLog.objects.create(
            webhook_id=webhook_id,
            subscription=subscription,
            attempt_number=attempt_number,
            outcome=outcome,
            http_status=response.status_code,
            error_details=None if outcome == "success" else f"HTTP {response.status_code}: {response.text[:500]}",
        )

        if response.status_code != 200:
            retry_seconds = [10, 30, 60, 300, 900][self.request.retries]
            logger.info(f"Retrying task in {retry_seconds} seconds (attempt {attempt_number}/6)")
            redis.delete(task_lock_key)  # Release the lock before retrying
            raise self.retry(countdown=retry_seconds)

        logger.info(f"Webhook delivery succeeded for webhook_id: {webhook_id}")
        redis.delete(task_lock_key)  # Release the lock on success
    except requests.RequestException as e:
        logger.error(f"Request failed for webhook_id: {webhook_id}: {str(e)}")
        subscription = Subscription.objects.get(id=subscription_id)
        WebhookDeliveryLog.objects.create(
            webhook_id=webhook_id,
            subscription=subscription,
            attempt_number=attempt_number,
            outcome="failed_attempt",
            http_status=None,
            error_details=str(e),
        )
        if self.request.retries < 5:  # Allow 6 total attempts (0-5 retries)
            retry_seconds = [10, 30, 60, 300, 900][self.request.retries]
            logger.info(f"Retrying task in {retry_seconds} seconds (attempt {attempt_number}/6)")
            redis.delete(task_lock_key)  # Release the lock before retrying
            raise self.retry(countdown=retry_seconds)
        else:
            logger.error(f"Max retries exceeded for webhook_id: {webhook_id}")
            WebhookDeliveryLog.objects.create(
                webhook_id=webhook_id,
                subscription=subscription,
                attempt_number=attempt_number,
                outcome="failure",
                http_status=None,
                error_details="Max retries exceeded",
            )
    except MaxRetriesExceededError:
        logger.error(f"Max retries exceeded for webhook_id: {webhook_id}")
        subscription = Subscription.objects.get(id=subscription_id)
        WebhookDeliveryLog.objects.create(
            webhook_id=webhook_id,
            subscription=subscription,
            attempt_number=attempt_number,
            outcome="failure",
            http_status=None,
            error_details="Max retries exceeded",
        )
    except Exception as e:
        logger.error(f"Unexpected error for webhook_id: {webhook_id}: {str(e)}")
        subscription = Subscription.objects.get(id=subscription_id)
        WebhookDeliveryLog.objects.create(
            webhook_id=webhook_id,
            subscription=subscription,
            attempt_number=attempt_number,
            outcome="failure",
            http_status=None,
            error_details=str(e),
        )
        raise
    finally:
        # Ensure the lock is released in all cases
        redis.delete(task_lock_key)

@app.task
def cleanup_old_logs():
    """
    Delete webhook delivery logs older than 7 days.
    """
    logger.info("Running cleanup_old_logs task")
    threshold = timezone.now() - timezone.timedelta(days=7)
    deleted_count, _ = WebhookDeliveryLog.objects.filter(created_at__lt=threshold).delete()
    logger.info(f"Deleted {deleted_count} old webhook delivery logs")