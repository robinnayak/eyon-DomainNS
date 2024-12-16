from django.contrib import admin
from .models import CheckoutSession, Purchase


@admin.register(CheckoutSession)
class CheckoutSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'domain_name', 'period', 'price', 'currency', 'created_at']
    search_fields = ['session_id', 'domain_name']
    list_filter = ['currency', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = [
        'order_id',
        'checkout_session',
        'get_email',  # Custom method to display email
        'first_name',
        'last_name',
        'amount',
        'currency',
        'status',
        'created_at'
    ]
    search_fields = ['order_id', 'checkout_session__domain_name', 'first_name', 'last_name']
    list_filter = ['status', 'currency', 'created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['checkout_session']

    def get_email(self, obj):
        """Retrieve the email from the related CheckoutSession."""
        return obj.checkout_session.email

    get_email.short_description = 'Email'  # Column name in the admin interface
