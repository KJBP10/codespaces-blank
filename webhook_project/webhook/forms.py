from django import forms
from django.utils import timezone
from .models import Subscription

class SubscriptionForm(forms.ModelForm):
    event_types = forms.CharField(
        required=False,
        help_text="Enter event types as a comma-separated list (e.g., event1, event2)",
        widget=forms.TextInput(attrs={'placeholder': 'e.g., event1, event2'})
    )

    class Meta:
        model = Subscription
        fields = ['callback_url', 'event_types', 'secret_key']
        widgets = {
            'callback_url': forms.URLInput(attrs={'placeholder': 'https://example.com/webhook'}),
            'secret_key': forms.TextInput(attrs={'placeholder': 'Enter a secret key'}),
        }

    def clean_event_types(self):
        event_types = self.cleaned_data['event_types']
        if event_types:
            cleaned_events = [event.strip() for event in event_types.split(',') if event.strip()]
            if not cleaned_events:
                raise forms.ValidationError("At least one event type must be valid.")
            return cleaned_events
        return []  # Default to empty list if not provided

    def save(self, *args, **kwargs):
        instance = super().save(commit=False)
        instance.event_types = self.cleaned_data['event_types'] or []  # Ensure event_types is set
        instance.updated_at = timezone.now()  # Update timestamp
        instance.save()
        return instance