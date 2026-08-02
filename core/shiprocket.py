import json
import requests
from django.conf import settings
from core.models import Shipment

BASE_URL = "https://apiv2.shiprocket.in/v1/external"


def get_shiprocket_token():
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "email": settings.SHIPROCKET_EMAIL,
            "password": settings.SHIPROCKET_PASSWORD
        }
    )

    print("SHIPROCKET LOGIN STATUS:", response.status_code)
    print("SHIPROCKET LOGIN RESPONSE:", response.text)

    if response.status_code == 200:
        token = response.json().get("token")
        if not token:
            raise Exception("Shiprocket login succeeded but token missing")
        return token

    raise Exception("Shiprocket login failed")


def create_shiprocket_order(order):
    token = get_shiprocket_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "order_id": str(order.id),
        "order_date": order.created_at.strftime("%Y-%m-%d"),
        "pickup_location": "home",  # MUST match Shiprocket pickup nickname
        "billing_customer_name": order.address.full_name,
        "billing_address": order.address.address_line1,
        "billing_city": order.address.city,
        "billing_pincode": str(order.address.postal_code),
        "billing_state": order.address.state,
        "billing_country": "India",
        "billing_email": order.user.email or "test@example.com",
        "billing_phone": str(order.address.phone),
        "shipping_is_billing": True,
        "order_items": [
            {
                "name": item.product.name[:100],
                "sku": str(item.product.id),
                "units": item.quantity,
                "selling_price": float(item.price),
            }
            for item in order.items.all()
        ],
        "payment_method": "COD" if not order.is_paid else "Prepaid",
        "sub_total": float(
            sum(item.price * item.quantity for item in order.items.all())
        ),
        "length": 10,
        "breadth": 10,
        "height": 10,
        "weight": 0.5,
    }

    response = requests.post(
        f"{BASE_URL}/orders/create/adhoc",
        json=payload,
        headers=headers,
        timeout=20
    )

    try:
        data = response.json()
    except Exception:
        raise Exception(f"Shiprocket non-JSON response: {response.text}")

    if response.status_code not in (200, 201):
        raise Exception(f"Shiprocket error: {data}")

    # ✅ REQUIRED KEYS
    shiprocket_order_id = data.get("order_id")
    shipment_id = data.get("shipment_id")

    if not shiprocket_order_id or not shipment_id:
        raise Exception(f"Invalid Shiprocket response: {data}")

    # ✅ SAVE SHIPMENT
    shipment, _ = Shipment.objects.get_or_create(order=order)
    shipment.shiprocket_order_id = shiprocket_order_id
    shipment.shipment_id = shipment_id
    shipment.status = "created"
    shipment.save()

    # ✅ UPDATE ORDER STATUS
    order.status = "confirmed"
    order.save(update_fields=["status"])

    return True

