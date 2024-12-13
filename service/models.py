from django.db import models

# Create your models here.

class DomainPurchaseDetails(models.Model):
    domain_name = models.CharField(max_length=100)
    user_email = models.EmailField()
    purchase_date = models.DateField()
    expiry_date = models.DateField()
    price = models.FloatField()

    def __str__(self):
        return self.domain_name
    
    