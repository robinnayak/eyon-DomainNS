from rest_framework import serializers
from .models import CheckoutSession, Purchase

class CheckoutSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckoutSession
        fields = [
            'session_id',
            'domain_name',
            'email',
            'period',
            'price',
            'currency',
            'created_at',
        ]


class PurchaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Purchase
        fields = [
            'order_id',
            'checkout_session',  # This can show the session ID or other details depending on related settings
            'first_name',
            'last_name',
            'phone',
            'address1',
            'address2',
            'city',
            'state',
            'postal_code',
            'country',
            'amount',
            'currency',
            'status',
            'created_at',
        ]
