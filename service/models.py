from django.db import models

class CheckoutSession(models.Model):
    session_id = models.CharField(max_length=255, unique=True)
    domain_name = models.CharField(max_length=255)
    email = models.EmailField()
    period = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session ID: {self.session_id} - Domain: {self.domain_name}"


class Purchase(models.Model):
    order_id = models.CharField(max_length=255, unique=True)
    checkout_session = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, related_name='purchases')
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    address1 = models.CharField(max_length=255)
    address2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10)
    status = models.CharField(max_length=50, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order ID: {self.order_id} - Domain: {self.checkout_session.domain_name}"
