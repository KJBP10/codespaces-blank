from django.db import models
import uuid

class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    callback_url = models.URLField(max_length=255)
    event_types = models.JSONField(default=list)  # Stores a list of event types, e.g., ["test_event"]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.id)

class WebhookDeliveryLog(models.Model):
    webhook_id = models.UUIDField()
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='logs')
    attempt_number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=20)
    http_status = models.IntegerField(null=True, blank=True)
    error_details = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Log for webhook {self.webhook_id}, attempt {self.attempt_number}"