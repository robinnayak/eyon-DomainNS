from django.shortcuts import render, HttpResponse
from django.conf import settings
from django.http import JsonResponse
import requests
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime
import stripe
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from django.shortcuts import redirect

# Create your views here.

current_time = datetime.utcnow()
stripe.api_key = settings.STRIPE_SECRET_KEY
DOMAIN = settings.DOMAIN


def home(request):
    return HttpResponse("Welcome to the Domain Service Provider")


@csrf_exempt
def get_list_domains(request):
    if request.method == "POST":
        try:
            # Parse the JSON body from the POST request
            data = json.loads(request.body.decode("utf-8"))
            print(data)
            domain_keyword = data.get(
                "domain_name", "defaultdomain"
            )  # Use a default if not provided

            # Define extensions and prepare API headers
            extensions = data.get("extensions", [])

            # extensions = [
            #     ".com", ".in", ".org", ".net", ".info", ".co", ".io",
            #     ".biz", ".us", ".uk", ".ca", ".au", ".eu", ".asia", ".de",
            # ]
            base_url = "https://api.ote-godaddy.com/v1/domains/available"
            headers = {
                "content-type": "application/json",
                "Authorization": f"sso-key {settings.GODADDY_API_KEY}:{settings.GODADDY_API_SECRET_KEY}",
            }

            available_domains = []

            # Query the GoDaddy API for each extension
            for ext in extensions:
                domain = f"{domain_keyword}{ext}"
                url = f"{base_url}?domain={domain}"
                response = requests.get(url, headers=headers)
                result = response.json()

                # Check if the domain is available
                if result.get("available"):
                    available_domains.append(result)

            # Return the list of available domains as JSON response
            return JsonResponse(
                {"available_domains": available_domains}, safe=False, status=200
            )
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)


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
def success(request):
    session_id = request.GET.get("session_id")
    print(session_id)
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        print(session)
        return JsonResponse({"message": "Payment successful", "session": session})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def cancel(request):
    return HttpResponse("Payment Cancelled")


@csrf_exempt
def stripe_webhook(request):
    if request.method == "POST":
        payload = request.body
        endpoint_secret = settings.WEBHOOK_ENDPOINT_SECRET
        sig_header = request.headers("STRIPE_SIGNATURE")  # Use .get to avoid KeyError
        event = None
        # Check if the signature header is present
        if not sig_header:
            return JsonResponse({"error": "Signature header not found"}, status=400)

        try:
            # Verify the event using the signature and endpoint secret
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError as e:
            # Invalid payload
            print(f"Error pasrsing payload: {e}")
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            print(f"Signature verification failed: {e}")
            return HttpResponse(status=400)
        # Process the webhook event
        if event["type"] == "checkout.session.completed":
            # Perform actions after successful payment
            session = event["data"]["object"]
            print(session)
            print("Payment was successful.")
            return JsonResponse({"status": "Payment was successful"}, status=200)
        else:
            print("Unhandled event type:", event["type"])

        return HttpResponse(status=200)
    # Reject non-POST requests
    return JsonResponse(
        {"error": "Invalid request method, POST only allowed"}, status=405
    )


@csrf_exempt
def purchase_domain(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        # Parse request data
        data = json.loads(request.body.decode("utf-8"))
        required_fields = [
            "domain_name",
            "email",
            "period",
            "first_name",
            "last_name",
            "phone",
            "address1",
            "city",
            "state",
            "postal_code",
            "country",
            "amount",
        ]

        # Validate required fields
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({"error": f"{field} is required"}, status=400)

        domain_name = data["domain_name"]
        email = data["email"]
        period = int(data["period"])
        first_name = data["first_name"]
        last_name = data["last_name"]
        phone = data["phone"]
        address1 = data["address1"]
        address2 = data.get("address2", "")
        city = data["city"]
        state = data["state"]
        postal_code = data["postal_code"]
        country = data["country"]
        amount = int(data["amount"])
        currency = data.get("currency", "USD").lower()

        if amount <= 0:
            return JsonResponse({"error": "Amount must be greater than 0"}, status=400)

        # Create Stripe checkout session
        checkout_url = create_checkout_session(domain_name, amount, period, email)

        if not checkout_url:
            return JsonResponse(
                {"error": "Failed to create Stripe checkout session"}, status=500
            )

        # Extract TLD and fetch agreement keys
        tlds = [domain_name.split(".")[-1]]  # Extract TLD from domain name
        agreements = domain_agreement(tlds)

        if not agreements or "agreementKey" not in agreements[0]:
            return JsonResponse(
                {"error": "Missing legal agreement consent"}, status=400
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
                "agreementKeys": [agreement_key],
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
                "phone": phone,
                "nameFirst": first_name,
                "nameLast": last_name,
            },
            "contactBilling": {
                "addressMailing": {
                    "address1": address1,
                    "address2":address2,
                    "city": city,
                    "country": country,
                    "postalCode": postal_code,
                    "state": state,
                },
                "email": email,
                "fax": phone,
                "jobTitle": "string",
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
                "phone": phone,
                "nameFirst": first_name,
                "nameLast": last_name,
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
                "fax": phone,
                "jobTitle": "string",
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
            "period": period,
            "privacy": False,
            "renewAuto": True,
        }

        # Send request to GoDaddy API
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()

        if response.status_code == 200:
            return JsonResponse(
                {
                    "domain_name": domain_name,
                    "status": response_data.get("status", "PENDING"),
                    "order_id": response_data.get("orderId"),
                    "currency": response_data.get("currency"),
                    "total": response_data.get("total"),
                    "item_count": response_data.get("itemCount"),
                    "checkout_url": checkout_url,
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


def create_checkout_session(domain_name, amount, period, email):
    
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": amount
                        * 100,  # Stripe requires the price in cents
                        "product_data": {
                            "name": domain_name,
                            "description": f"Registration for {period} year(s)",
                        },
                    },
                    "quantity": 1,
                },
            ],
            mode="payment",
            billing_address_collection="required",
            success_url=f"{DOMAIN}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{DOMAIN}/cancel",
            customer_email=email,
        )
        return checkout_session.url
    except Exception as e:
        print(f"Error creating checkout session: {e}")
        return None


@csrf_exempt
def verify_registrant_email(request, domain):
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
                {
                    "error": response.json().get(
                        "message", "Failed to send verification email"
                    )
                },
                status=response.status_code,
            )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# def search_domain_name(request):
#     # domain_name = request.GET.get('domain_name')
#     domain_name = "roomaltersuite.com"

#     if not domain_name:
#         return JsonResponse({"error": "Domain name is required"}, status=400)

#     url = f"https://api.ote-godaddy.com/v1/domains/available?domain={domain_name}"
#     headers = {
#         "content-type": "application/json",
#         "Authorization": f"sso-key {settings.GODADDY_API_KEY}:{settings.GODADDY_API_SECRET_KEY}",
#     }

#     try:
#         response = requests.get(url, headers=headers)
#         data = response.json()
#         if data["available"]:
#             return JsonResponse(
#                 {
#                     "domain_name": domain_name,
#                     "available": data["available"],
#                     "price": data["price"] / 1000000,
#                     "subscription_year": data["period"],
#                     "currency": data["currency"],
#                 },
#                 status=200,
#             )
#         else:
#             return JsonResponse(
#                 {"domain_name": domain_name, "available": data["available"]}, status=500
#             )
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=500)
