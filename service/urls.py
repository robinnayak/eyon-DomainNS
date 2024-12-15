from django.urls import path,include
from . import views
urlpatterns = [
    path('', views.home, name='home' ), # Added the service app url
    # path('search-domain/', views.search_domain_name, name='search-domain' ), # Added the service app url
    path('purchase-domain/', views.purchase_domain, name='purchase-domain' ), # Added the service app url
    path('list-domains/', views.get_list_domains, name='list-domains' ), # Added the service app url
    path('domain-agreement/', views.domain_agreement, name='domain-agreement' ), # Added the service app url
    path('success/', views.success, name='success' ), # Added the service app url
    path('cancel/', views.cancel, name='cancel' ), # Added the service app url
    path('checkout-session/', views.checkout_session, name='checkout-session' ), # Added the service app url
    path('stripe-webhook/',views.stripe_webhook, name='stripe-webhook'),
]