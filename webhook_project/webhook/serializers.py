from rest_framework import serializers
from .models import Subscription, WebhookDeliveryLog

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['id', 'target_url', 'event_types', 'created_at']
        read_only_fields = ['id', 'created_at']

class WebhookPayloadSerializer(serializers.Serializer):
    data = serializers.DictField()

    def validate_data(self, value):
        if not value:
            raise serializers.ValidationError("The 'data' field cannot be empty.")
        return value

class DeliveryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDeliveryLog
        fields = ['id', 'webhook_id', 'subscription', 'attempt_number', 'created_at', 'outcome', 'http_status', 'error_details']
        read_only_fields = ['id', 'webhook_id', 'subscription', 'attempt_number', 'created_at', 'outcome', 'http_status', 'error_details']