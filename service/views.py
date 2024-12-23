from django.shortcuts import render, HttpResponse, get_object_or_404
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
from .models import CheckoutSession, Purchase
import csv
from .serializers import CheckoutSessionSerializer,PurchaseSerializer

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

        checkout_session = CheckoutSession.objects.filter(
            domain_name=data["domain_name"], email=data["email"]
        )
        if not checkout_session.exists():
            return JsonResponse({"error": "Invalid checkout session"}, status=400)
        print("= ================================")
        print("checkout session from purchase",checkout_session)
        checkout_session = checkout_session.first()
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
                # "entityType": "INDIVIDUAL",  # Add entityType here
                # "language": "en", 
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
            # "privacy": False,
            "renewAuto": True,
        }

        # Send request to GoDaddy API
        response = requests.post(url, headers=headers, json=payload)

        response_data = response.json()
        response_data["status"] = "SUCCESS" if response.status_code == 200 else "FAILED"
        print(response_data)
        if response.status_code == 200:

            # Save purchase details in the database
            purchase = Purchase.objects.create(
                order_id=response_data.get("orderId"),  # Generate a unique order ID
                checkout_session=checkout_session,
                first_name=data["first_name"],
                last_name=data["last_name"],
                phone=data["phone"],
                address1=data["address1"],
                address2=data.get("address2", ""),
                city=data["city"],
                state=data["state"],
                postal_code=data["postal_code"],
                country=data["country"],
                amount=Decimal(data["amount"]),
                currency=data.get("currency", "USD").upper(),
                status="SUCCESS",
            )
            print("Purchase details saved: =======================  ")
            print(purchase)
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
def create_checkout_session(request):
    if request.method == "POST":
        try:
            # Get the product details from the POST request
            data = json.loads(request.body.decode("utf-8"))
            domain_name = data.get("name")

            product_price = (
                Decimal(data.get("price")) * 100
            )  # Convert to cents for Stripe
            product_period = data.get("period")
            user_email = data.get("email")

            print("=====================================")
            print(domain_name, product_price, product_period, user_email)

            # Create a Stripe checkout session
            checkout_session = stripe.checkout.Session.create(
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": int(
                                product_price
                            ),  # Stripe requires the price in cents
                            "product_data": {
                                "name": domain_name,
                                "description": f"Registration for {product_period} year(s)",
                                # 'images': ['https://images.unsplash.com/photo-1579202673506-ca3ce28943ef'],
                            },
                        },
                        "quantity": 1,
                    },
                ],
                mode="payment",
                billing_address_collection="required",
                # success_url=DOMAIN + '/success?session_id={CHECKOUT_SESSION_ID}',
                success_url=(
                    f"{DOMAIN}/success?"
                    f"session_id={{CHECKOUT_SESSION_ID}}"
                    f"&domain_name={domain_name}"
                    f"&period={product_period}"
                ),
                cancel_url=DOMAIN + "/cancel",
                customer_email=user_email,
            )
            # Save checkout session details in the database
            checkoutdb_session = CheckoutSession.objects.create(
                session_id=checkout_session.id,
                domain_name=domain_name,
                email=user_email,
                period=product_period,
                price=product_price,
                currency="usd",
            )

            print(f"Session ID: {checkout_session.id}")
            print(f"Checkout URL: {checkoutdb_session}")
            return JsonResponse({"session": checkout_session.url}, status=200)
        except Exception as error:
            return JsonResponse({"error": str(error)}, status=500)

    return JsonResponse(
        {"error": "Invalid request method, POST only Allowed!"}, status=405
    )


@csrf_exempt
def success(request):
    # session_id = request.GET.get("session_id")
    # print(session_id)
    try:
        data = json.loads(request.body.decode("utf-8"))
        session_id = data.get("session_id")
        session = stripe.checkout.Session.retrieve(session_id)
        print(session)
        return JsonResponse({"message": "Payment successful", "session": session})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def cancel(request):
    return HttpResponse("Payment Cancelled")



class CheckoutSessionView(APIView):
    def get(self, request):
        try:
            checkout_sessions = CheckoutSession.objects.all()
            serializer = CheckoutSessionSerializer(checkout_sessions, many=True)
            return Response({"checkout_sessions": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PurchaseAPIView(APIView):
    def get(self, request, session_id):
        checkout_session = get_object_or_404(CheckoutSession, session_id=session_id)
        purchases = Purchase.objects.filter(checkout_session=checkout_session)
        serializer = PurchaseSerializer(purchases, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, session_id):
        checkout_session = get_object_or_404(CheckoutSession, session_id=session_id)

        data = request.data.copy()
        data['checkout_session'] = checkout_session.id

        serializer = PurchaseSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
def export_to_csv(request):
    file_path = 'domainserviceprovider\CSVdata\purchases.csv'
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="purchases.csv"'
    
    writer = csv.writer(response)
    
    writer.writerow(['session id','Domain Name','Email','Period','Price','Currency','Created At'])
    sessions = CheckoutSession.objects.all()
    
    for session in sessions:
        writer.writerow([
            session.session_id,
            session.domain_name,
            session.email,
            session.period,
            session.price,
            session.currency,
            session.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    return response


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
