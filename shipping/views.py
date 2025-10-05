from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import requests
from .utils import NimbusPostAPI
from core.models import Order, OrderItem, Shipment 
import json


@csrf_exempt
def create_shipment_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            order_id = data.get("order_id")
            order = Order.objects.filter(id=order_id).first()

            if not order:
                return JsonResponse({"error": "Order not found"}, status=404)

            # ✅ Get address details from Address model
            address = order.address
            if not address:
                return JsonResponse({"error": "Address not found for order"}, status=400)

            # NimbusPost token (replace with your working token)
            token = "YOUR_NIMBUSPOST_TOKEN"
            url = "https://api.nimbuspost.com/v1/shipments"

            payload = {
                "order_number": str(order.id),
                "payment_type": "COD" if order.payment_method == "COD" else "Prepaid",
                "cod_amount": float(order.total_price) if order.payment_method == "COD" else 0.0,
                "order_amount": float(order.total_price),
                "consignee": {
                    "name": address.full_name,
                    "address": f"{address.address_line1}, {address.address_line2}" if address.address_line2 else address.address_line1,
                    "pincode": address.postal_code,
                    "phone": address.phone,
                    "state": address.state,
                    "city": address.city,
                },
                # Ship-from details (replace with your vendor/shop details)
                "pickup": {
                    "name": "Kartloop Store",
                    "address": "Your warehouse address",
                    "pincode": "110001",
                    "phone": "9999999999",
                    "state": "Delhi",
                    "city": "New Delhi",
                },
                # Example product data from order items
                "products": [
                    {
                        "name": item.product.name,
                        "sku": f"SKU-{item.product.id}",
                        "units": item.quantity,
                        "selling_price": float(item.price),
                        "weight": 0.5  # You can replace with actual product weight if available
                    }
                    for item in order.items.all()
                ]
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }

            response = requests.post(url, headers=headers, json=payload)
            resp_data = response.json()

            if response.status_code == 200:
                # Save shipment record
                Shipment.objects.create(
                    order_id=order.id,
                    tracking_id=resp_data.get("tracking_id"),
                    courier_name=resp_data.get("courier_name"),
                    status=resp_data.get("status", "Created")
                )
                return JsonResponse({"message": "Shipment created successfully", "data": resp_data})
            else:
                return JsonResponse({"error": "Failed to create shipment", "details": resp_data}, status=400)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@require_http_methods(["GET"])
def track_shipment_view(request, tracking_id):
    if not tracking_id:
        return JsonResponse({"error": "Tracking ID is required"}, status=400)

    try:
        api = NimbusPostAPI()
        response = api.track_shipment(tracking_id)
        return JsonResponse(response, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def test_nimbuspost_view(request):
    """
    Live API test — tries to fetch a courier list from NimbusPost.
    """
    try:
        api = NimbusPostAPI()
        
        # Example live API call — Get couriers list (change to create_shipment if you want)
        response = api.get_courier_list()
        
        return JsonResponse({
            "status": "success",
            "live_response": response
        })
    
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)
