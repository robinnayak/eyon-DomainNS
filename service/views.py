from django.shortcuts import render, HttpResponse
from django.conf import settings
from django.http import JsonResponse
import requests
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime
import stripe
# Create your views here.

current_time = datetime.utcnow()
stripe.api_key = settings.STRIPE_SECRET_KEY

def home(request):
    return HttpResponse("Welcome to the Domain Service Provider")


def get_list_domains(request):
    base_url = "https://api.ote-godaddy.com/v1/domains/available"
    headers = {
        "content-type": "application/json",
        "Authorization": f"sso-key {settings.GODADDY_API_KEY}:{settings.GODADDY_API_SECRET_KEY}",
    }
    domain_keyword = "roomaltersuite"
    extensions = [
        ".com",
        ".in",
        ".org",
        ".net",
        ".info",
        ".co",
        ".io",
        ".biz",
        ".us",
        ".uk",
        ".ca",
        ".au",
        ".eu",
        ".asia",
        ".de",
    ]
    available_domains = []

    try:
        for ext in extensions:
            domain = f"{domain_keyword}{ext}"
            url = f"{base_url}?domain={domain}"
            response = requests.get(url, headers=headers)
            result = response.json()
            # Check if the domain is available
            if result.get("available"):
                available_domains.append(result)

        return JsonResponse(
            {"available_domains": available_domains}, safe=False, status=200
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def domain_agreement(tlds, privacy="false"):
    # tlds = ["com", "net", "org"]  # Replace with supported TLDs
    # privacy = "false"  # Set to "true" if you want agreements for privacy protection
    tlds_query = "&".join([f"tlds={tld}" for tld in tlds])  # Build TLDs query parameter

    url = f"https://api.ote-godaddy.com/v1/domains/agreements?{tlds_query}&privacy={privacy}"
    headers = {
        "content-type": "application/json",
        "Authorization": f"sso-key {settings.GODADDY_API_KEY}:{settings.GODADDY_API_SECRET_KEY}",
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        if response.status_code == 200:
            data = response.json()
            return data  # Return the agreements data
        else:
            return JsonResponse(
                {"error": response.json().get("message", "Failed to fetch agreements")},
                status=response.status_code,
            )
    except requests.exceptions.RequestException as req_err:
        return JsonResponse({"error": str(req_err)}, status=500)
    except ValueError as val_err:
        return JsonResponse({"error": str(val_err)}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def purchase_domain(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        # Parse request data
        data = json.loads(request.body.decode("utf-8"))
        domain_name = data.get("domain_name")
        email = data.get("email")
        period = data.get("period")
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        phone = data.get("phone")
        address1 = data.get("address1")
        address2 = data.get("address2", "")
        city = data.get("city")
        state = data.get("state")
        postal_code = data.get("postal_code")
        country = data.get("country")
        fax = data.get("fax", "+1.2125551234")
        amount = data.get("amount", 0)
        currency = data.get("currency", "USD")
        payment_method = data.get("payment_method", "card")
        
        # Validate required fields
        if not all(
            [
                domain_name,
                email,
                period,
                first_name,
                last_name,
                phone,
                address1,
                city,
                state,
                postal_code,
                country,
            ]
        ):
            return JsonResponse({"error": "All fields are required"}, status=400)

        #Process Payment using Stripe
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            receipt_email=email,
            confirm=True,
        )
        
        if payment_intent["status"] != "succeeded":
            return JsonResponse(
                {"error": "Payment failed", "payment_intent": payment_intent},
                status=400,
            )
        
        
        # Extract TLD and fetch agreement keys
        tlds = [domain_name.split(".")[-1]]  # Extract TLD from domain name
        agreements = domain_agreement(tlds)
        if not agreements or "agreementKey" not in agreements[0]:
            return JsonResponse(
                {
                    "error": "End-user must read and consent to all of the following legal agreements: DNRA DNPA"
                },
                status=400,
            )

        agreement_key = agreements[0]["agreementKey"]

        # Prepare consent fields
        agreed_at = datetime.now().isoformat() + "Z"  # ISO8601 format with UTC
        agreed_by = request.META.get("REMOTE_ADDR", "127.0.0.1")

        # GoDaddy API endpoint and headers
        url = "https://api.ote-godaddy.com/v1/domains/purchase"
        headers = {
            "content-type": "application/json",
            "Authorization": f"sso-key {settings.GODADDY_API_KEY}:{settings.GODADDY_API_SECRET_KEY}",
        }

        # Data payload for domain registration
        payload = {
            "consent": {
                "agreedAt": agreed_at,
                "agreedBy": agreed_by,
                "agreementKeys": [
                    agreement_key,
                ],
            },
            "contactAdmin": {
                "addressMailing": {
                    "address1": address1,
                    "address2": address2,
                    "city": city,
                    "country": country,
                    "postalCode": postal_code,
                    "state": state,
                },
                "email": email,
                "fax": fax,
                "jobTitle": "ABC company",
                "nameFirst": first_name,
                "nameLast": last_name,
                "nameMiddle": "string",
                "organization": "string",
                "phone": phone,
            },
            "contactBilling": {
                "addressMailing": {
                    "address1": address1,
                    "address2": address2,
                    "city": city,
                    "country": country,
                    "postalCode": postal_code,
                    "state": state,
                },
                "email": email,
                "fax": fax,
                "jobTitle": "ABC company",
                "nameFirst": first_name,
                "nameLast": last_name,
                "nameMiddle": "string",
                "organization": "string",
                "phone": phone,
            },
            "contactRegistrant": {
                "addressMailing": {
                    "address1": address1,
                    "address2": address2,
                    "city": city,
                    "country": country,
                    "postalCode": postal_code,
                    "state": state,
                },
                "email": email,
                "fax": fax,
                "jobTitle": "ABC company",
                "nameFirst": first_name,
                "nameLast": last_name,
                "nameMiddle": "string",
                "organization": "string",
                "phone": phone,
            },
            "contactTech": {
                "addressMailing": {
                    "address1": address1,
                    "address2": address2,
                    "city": city,
                    "country": country,
                    "postalCode": postal_code,
                    "state": state,
                },
                "email": email,
                "fax": fax,
                "jobTitle": "ABC company",
                "nameFirst": first_name,
                "nameLast": last_name,
                "nameMiddle": "string",
                "organization": "string",
                "phone": phone,
            },
            "domain": domain_name,
            "nameServers": [
                "ns01.domaincontrol.com",
                "ns02.domaincontrol.com",
            ],
            "period": 1,
            "privacy": False,
            "renewAuto": True,
        }
        # Send request to GoDaddy API
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        print(response_data)
        if response.status_code == 200:
            return JsonResponse(
                {
                    "domain_name": domain_name,
                    "status": response_data.get("status", "PENDING"),
                    "order_id": response_data.get("orderId"),
                    "currency": response_data.get("currency"),
                    "total": response_data.get("total"),
                    "item_count": response_data.get("itemCount"),
                },
                status=200,
            )
        else:
            return JsonResponse(
                {
                    "error": response_data.get("message", "An error occurred"),
                    "fields": response_data.get("fields", {}),
                },
                status=response.status_code,
            )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def verify_registrant_email(request,domain):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. Use POST."}, status=400)
    try:
        url = f"https://api.ote-godaddy.com/v1/domains/{domain}/verifyRegistrantEmail"
        headers = {
            "content-type": "application/json",
            "Authorization": f"sso-key {settings.GODADDY_API_KEY}:{settings.GODADDY_API_SECRET_KEY}",
        }
        response = requests.post(url, headers=headers)
        print(response.json())
        if response.status_code == 200:
            return JsonResponse({"message": "Verification email sent"}, status=200)
        else:
            return JsonResponse(
                {"error": response.json().get("message", "Failed to send verification email")},
                status=response.status_code,
            )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
        
def search_domain_name(request):
    # domain_name = request.GET.get('domain_name')
    domain_name = "roomaltersuite.com"

    if not domain_name:
        return JsonResponse({"error": "Domain name is required"}, status=400)

    url = f"https://api.ote-godaddy.com/v1/domains/available?domain={domain_name}"
    headers = {
        "content-type": "application/json",
        "Authorization": f"sso-key {settings.GODADDY_API_KEY}:{settings.GODADDY_API_SECRET_KEY}",
    }

    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data["available"]:
            return JsonResponse(
                {
                    "domain_name": domain_name,
                    "available": data["available"],
                    "price": data["price"] / 1000000,
                    "subscription_year": data["period"],
                    "currency": data["currency"],
                },
                status=200,
            )
        else:
            return JsonResponse(
                {"domain_name": domain_name, "available": data["available"]}, status=500
            )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
