from django.contrib import admin
from .models import DomainPurchaseDetails

# Register your models here.

class DomainPurchaseDetailsAdmin(admin.ModelAdmin):
    
    list_display = ['domain_name','user_email','purchase_date','expiry_date','price']
    search_fields = ['domain_name','user_email']
    

admin.site.register(DomainPurchaseDetails,DomainPurchaseDetailsAdmin)