# webhook/views.py
from django.views.generic import ListView, DetailView, UpdateView, CreateView
from django.urls import reverse_lazy
from django.http import HttpResponse, HttpResponseRedirect
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Subscription, WebhookDeliveryLog
from .tasks import deliver_webhook
import logging
import uuid
import json
from redis import Redis
from celery import current_app
import hmac
import hashlib
from django.utils import timezone
from .forms import SubscriptionForm
from rest_framework import status

logger = logging.getLogger(__name__)

# UI Views
class SubscriptionListView(ListView):
    model = Subscription
    template_name = 'webhook/subscription_list.html'
    context_object_name = 'subscriptions'

class SubscriptionCreateView(CreateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name = 'webhook/subscription_form.html'
    success_url = reverse_lazy('subscription_list')

    def form_valid(self, form):
        logger.info("Form validated successfully, creating subscription")
        response = super().form_valid(form)
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        logger.error(f"Form validation failed: {form.errors}")
        return super().form_invalid(form)

class SubscriptionUpdateView(UpdateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name = 'webhook/subscription_detail.html'
    success_url = reverse_lazy('subscription_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription_id = str(self.object.id)
        logs = WebhookDeliveryLog.objects.filter(subscription_id=subscription_id)
        context['logs'] = [
            {
                'webhook_id': str(log.webhook_id),
                'attempt_number': log.attempt_number,
                'outcome': log.outcome,
                'http_status': log.http_status,
                'error_details': log.error_details,
                'created_at': log.created_at
            } for log in logs
        ]
        return context

    def form_valid(self, form):
        logger.info(f"Updating subscription {self.object.id}")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form validation failed: {form.errors}")
        return super().form_invalid(form)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if 'test_webhook' in request.POST:
            event_type = request.POST.get('event_type', 'test_event')
            payload = request.POST.get('payload', '{"data": {"message": "test"}}')
            return self.handle_test_webhook(request, event_type, payload)
        elif 'delete' in request.POST:
            subscription_id = str(self.object.id)
            self.object.delete()
            logger.info(f"Deleted subscription {subscription_id}")
            return HttpResponseRedirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def handle_test_webhook(self, request, event_type, payload):
        subscription_id = str(self.object.id)
        webhook_id = str(uuid.uuid4())
        logger.info(f"Queuing test webhook for subscription {subscription_id}, webhook_id {webhook_id}")
        current_app.send_task(
            'webhook.tasks.deliver_webhook',
            args=[webhook_id, subscription_id, payload, event_type],
            queue='celery'
        )
        return HttpResponse('Test webhook queued successfully', status=200)

class SubscriptionDetailView(DetailView):
    model = Subscription
    template_name = 'webhook/subscription_detail.html'
    context_object_name = 'subscription'

# API Views
@api_view(['POST'])
@permission_classes([AllowAny])
def ingest_webhook(request, subscription_id):
    try:
        subscription = Subscription.objects.get(id=subscription_id)
        event_type = request.headers.get('X-Event-Type', 'default_event')
        payload = json.dumps(request.data)
        payload_bytes = payload.encode('utf-8')

        if subscription.secret_key:
            provided_signature = request.headers.get('X-Hub-Signature-256', '')
            if not provided_signature:
                logger.warning(f"Missing X-Hub-Signature-256 header for subscription {subscription_id}")
                return Response({"error": "Missing signature header"}, status=405)
            if not provided_signature.startswith('sha256='):
                logger.warning(f"Invalid signature format for subscription {subscription_id}")
                return Response({"error": "Invalid signature format"}, status=403)
            provided_hash = provided_signature[len('sha256='):]
            secret_bytes = subscription.secret_key.encode('utf-8')
            computed_hash = hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(provided_hash, computed_hash):
                logger.warning(f"Signature verification failed for subscription {subscription_id}")
                return Response({"error": "Invalid signature"}, status=403)
            logger.info(f"Signature verification passed for subscription {subscription_id}")
        else:
            logger.info(f"No secret_key set for subscription {subscription_id}, skipping signature verification")

        redis = Redis(host='redis', port=6379, db=0)
        webhook_id = str(uuid.uuid4())
        lock_key = f"webhook:{webhook_id}"
        lock_acquired = redis.set(lock_key, "locked", ex=60, nx=True)
        if not lock_acquired:
            logger.warning(f"Webhook {webhook_id} already processed or in progress")
            return Response({"error": "Webhook already processed"}, status=409)

        if subscription.event_types and event_type not in subscription.event_types:
            logger.warning(f"Event type {event_type} not subscribed for subscription {subscription_id}")
            return Response({"error": "Event type not subscribed"}, status=400)

        task = deliver_webhook.delay(webhook_id, str(subscription_id), payload, event_type)
        logger.info(f"Queued deliver_webhook task with webhook_id: {webhook_id}, task_id: {task.id}")
        return Response({"webhook_id": webhook_id}, status=202)

    except Subscription.DoesNotExist:
        logger.warning(f"Subscription not found: {subscription_id}")
        return Response({"error": "Subscription not found"}, status=404)
    except Exception as e:
        logger.error(f"Error ingesting webhook: {str(e)}")
        return Response({"error": "Internal server error"}, status=500)

@api_view(['GET'])
def subscription_logs(request, subscription_id):
    try:
        logs = WebhookDeliveryLog.objects.filter(subscription_id=subscription_id).order_by('-created_at')[:20]
        if not logs.exists():
            return Response({"error": "No logs found for this subscription"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'subscription_id': subscription_id,
            'logs': [
                {
                    'webhook_id': str(log.webhook_id),
                    'attempt_number': log.attempt_number,
                    'outcome': log.outcome,
                    'http_status': log.http_status,
                    'error_details': log.error_details,
                    'created_at': log.created_at
                }
                for log in logs
            ]
        })
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_SERVER_ERROR)

@api_view(['GET'])
def webhook_status(request, webhook_id):
    try:
        logs = WebhookDeliveryLog.objects.filter(webhook_id=webhook_id).order_by('-created_at')
        if not logs.exists():
            return Response({"error": "Webhook ID not found"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'webhook_id': webhook_id,
            'logs': [
                {
                    'attempt_number': log.attempt_number,
                    'outcome': log.outcome,
                    'http_status': log.http_status,
                    'error_details': log.error_details,
                    'created_at': log.created_at
                }
                for log in logs
            ]
        })
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_SERVER_ERROR)