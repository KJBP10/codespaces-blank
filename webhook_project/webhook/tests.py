from django.test import TestCase
from rest_framework.test import APIClient
from .models import Subscription

class WebhookTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.subscription = Subscription.objects.create(target_url="https://webhook.site/test")

    def test_create_subscription(self):
        response = self.client.post('/api/subscriptions/', {"target_url": "https://example.com"})
        self.assertEqual(response.status_code, 201)

    def test_ingest_webhook(self):
        response = self.client.post(f'/api/ingest/{self.subscription.id}/', {"data": {"event": "test"}})
        self.assertEqual(response.status_code, 202)
        self.assertIn("webhook_id", response.data)