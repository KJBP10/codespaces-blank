# webhook/tests.py
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Subscription, WebhookDeliveryLog
from django.urls import reverse
import uuid

class WebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.subscription = Subscription.objects.create(
            callback_url='https://httpbin.org/post',
            event_types=['test'],
            secret_key='test-secret'
        )
        self.webhook_id = str(uuid.uuid4())  # Generate a valid UUID

    def test_webhook_status(self):
        WebhookDeliveryLog.objects.create(
            webhook_id=self.webhook_id,  # Use the valid UUID
            subscription_id=self.subscription.id,
            attempt_number=1,
            outcome='success',
            http_status=200
        )
        response = self.client.get(reverse('webhook_status', args=[self.webhook_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['webhook_id'], self.webhook_id)

    def test_subscription_logs(self):
        WebhookDeliveryLog.objects.create(
            webhook_id=self.webhook_id,  # Use the valid UUID
            subscription_id=self.subscription.id,
            attempt_number=1,
            outcome='success',
            http_status=200
        )
        response = self.client.get(reverse('subscription_logs', args=[self.subscription.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['subscription_id'], str(self.subscription.id))