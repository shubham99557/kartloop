from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from core.models import Product, Order
from users.models import CustomerProfile
from openai import OpenAI
import os
from dotenv import load_dotenv
import re

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key='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')

@csrf_exempt
def chat_with_ai(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    try:
        message = request.POST.get('message', '').lower()
        user = request.user if request.user.is_authenticated else None

        # Helper: get order by id or last order
        def get_last_order(user):
            return Order.objects.filter(user=user).order_by('-created_at').first()

        # --- NAVIGATION TO ANY PAGE ---
        if "login" in message and ("open" in message or "go to" in message or "show" in message or "page" in message):
            return JsonResponse({'reply': "Opening login page.", 'action': {'type': 'redirect', 'page': '/users/login/'}})
        if "signup" in message or ("sign up" in message and ("open" in message or "go to" in message or "show" in message or "page" in message)):
            return JsonResponse({'reply': "Opening signup page.", 'action': {'type': 'redirect', 'page': '/users/signup/'}})
        if ("cart" in message or "my cart" in message) and ("open" in message or "go to" in message or "show" in message):
            return JsonResponse({'reply': "Opening your cart.", 'action': {'type': 'redirect', 'page': '/cart/'}})
        if "wishlist" in message and ("open" in message or "show" in message):
            return JsonResponse({'reply': "Opening your wishlist.", 'action': {'type': 'redirect', 'page': '/wishlist/'}})
        if ("home" in message or "main page" in message or "homepage" in message) and ("go to" in message or "open" in message or "show" in message):
            return JsonResponse({'reply': "Opening homepage.", 'action': {'type': 'redirect', 'page': '/'}})
        if ("checkout" in message or "pay now" in message):
            return JsonResponse({'reply': "Opening checkout.", 'action': {'type': 'redirect', 'page': '/checkout/'}})
        if "profile" in message and ("open" in message or "show" in message):
            return JsonResponse({'reply': "Opening your profile page.", 'action': {'type': 'redirect', 'page': '/users/profile/'}})
        if "edit profile" in message or ("edit" in message and "profile" in message):
            return JsonResponse({'reply': "Opening profile editor.", 'action': {'type': 'redirect', 'page': '/users/profile/edit/'}})
        if "orders" in message and ("open" in message or "show" in message or "go to" in message):
            return JsonResponse({'reply': "Opening your orders.", 'action': {'type': 'redirect', 'page': '/orders/'}})
        if ("logout" in message or "log out" in message):
            return JsonResponse({'reply': "Logging you out.", 'action': {'type': 'redirect', 'page': '/users/logout/'}})
        # Scroll UI
        if "scroll down" in message:
            return JsonResponse({'reply': "Scrolling down.", 'action': {'type':'js_func','func':'scrollDown'}})
        if "scroll up" in message:
            return JsonResponse({'reply': "Scrolling up.", 'action': {'type':'js_func','func':'scrollUp'}})

        # --- SEARCH PRODUCTS ---
        # Examples: "show me t-shirts", "find mobiles under 30000", "search laptops"
        find_match = re.search(r"(show|find|search|list)( me)? ([\w\s\-]+)( under ?₹?(\d+))?", message)
        if find_match:
            prod = find_match.group(3).strip() if find_match.group(3) else ""
            maxprice = find_match.group(5) if find_match.group(5) else ""
            url = f"/products/?q={prod.replace(' ','+')}" + (f"&max_price={maxprice}" if maxprice else "")
            reply = f"Showing you {prod}"
            if maxprice:
                reply += f" under ₹{maxprice}"
            return JsonResponse({'reply': reply + ".", 'action': {'type':'redirect','page': url}})

        # --- Open specific product (by name or ID) ---
        prod_match = re.search(r"(open|show|view) (product|item) (\d+)", message)
        if prod_match:
            pid = prod_match.group(3)
            return JsonResponse({'reply': f"Opening product #{pid}.", 'action': {'type':'redirect','page': f'/products/{pid}/'}})
        # Or by keyword if exactly matches a product name
        if ("open" in message or "show" in message or "view" in message) and "product" in message:
            name_match = message.replace('open','').replace('show','').replace('view','').replace('product','').strip()
            if name_match:
                prod = Product.objects.filter(name__icontains=name_match).first()
                if prod:
                    return JsonResponse({'reply': f"Opening {prod.name}.", 'action': {'type':'redirect','page': f'/products/{prod.id}/'}})

        # --- Show Category ---
        for cat in ["mens", "womens", "kids", "appliances", "books", "sports", "groceries", "gadgets"]:
            if cat in message and ("show" in message or "open" in message or "find" in message):
                return JsonResponse({'reply': f"Showing products in {cat.title()}", 'action': {'type': 'redirect', 'page': f'/products/?category={cat}'}})

        # --- ORDER DETAILS & CANCELLATION ---
        if user and any(x in message for x in ["my orders", "order history", "placed order", "show my orders", "recent orders"]):
            orders = Order.objects.filter(user=user).order_by('-created_at')[:5]
            if orders:
                reply = "Here are your recent orders:\n"
                for o in orders:
                    reply += f"🧾 Order #{o.id} — {o.status} — ₹{o.total_amount} — {o.created_at.strftime('%b %d %Y')}\n"
                return JsonResponse({'reply': reply, 'action': {'type':'show_orders'}})
            else:
                return JsonResponse({'reply': "You have not placed any orders yet."})

        if ("cancel" in message or "return" in message) and "order" in message:
            if user:
                order_id = [int(s) for s in message.split() if s.isdigit()]
                if order_id:
                    oid = order_id[0]
                    found = Order.objects.filter(user=user, id=oid).first()
                else:
                    found = get_last_order(user)
                if found:
                    reply = f"{'Cancelled' if 'cancel' in message else 'Returned'} order {found.id}."
                    return JsonResponse({'reply': reply, 'action': {'type': 'update_order_status', 'order_id': found.id, 'new_status': 'cancelled' if 'cancel' in message else 'returned'}})
                return JsonResponse({'reply': "Sorry, I couldn't find your order to update."})
            return JsonResponse({'reply': "Please log in to manage your orders."})

        # Add to cart/wishlist (using product name)
        if "add" in message and ("cart" in message or "wishlist" in message):
            product_name = message.replace('add', '').replace('to cart', '').replace('to wishlist', '').strip()
            if "cart" in message:
                return JsonResponse({'reply': f"Adding {product_name} to your cart.", 'action': {'type': 'add_to_cart', 'product_name': product_name}})
            else:
                return JsonResponse({'reply': f"Adding {product_name} to your wishlist.", 'action': {'type': 'add_to_wishlist', 'product_name': product_name}})
        # Update user profile (phone, email, etc.)
        if "change my" in message or "update my" in message:
            attribute = None
            value = None
            for field in ["phone number", "address", "email", "name"]:
                if field in message:
                    attribute = field.replace(" ", "_")
                    value = message.split("to", 1)[-1].strip()
                    break
            if attribute and value and user:
                return JsonResponse({'reply': f"Profile {attribute.replace('_', ' ')} will be updated to {value}.", 'action': {'type': 'update_profile', 'field': attribute, 'value': value}})
            return JsonResponse({'reply': "Please specify what to update and log in!"})

        # Track shipment status
        if "track" in message and ("order" in message or "shipment" in message):
            order = get_last_order(user) if user else None
            if order:
                reply = f"Your order #{order.id} is currently '{order.status}'."
                return JsonResponse({'reply': reply, 'action': {'type': 'track_order', 'order_id': order.id}})
            return JsonResponse({'reply': "I couldn't find an order to track for you."})

        # Offers, Reminders & New Arrivals (notifications)
        if "offer" in message or "deal" in message or "discount" in message:
            return JsonResponse({'reply': 'A big offer is live: 10% off all electronics this week!', 'notify': {'type': 'special_offer', 'offer': '10% off all electronics this week'}})
        if "remind" in message or "notify" in message:
            return JsonResponse({'reply': "Your reminder has been set!", 'notify': {'type': 'reminder', 'text': message}})
        if "new arrival" in message:
            return JsonResponse({'reply': 'New arrivals: Check out the latest in fashion and gadgets!', 'notify': {'type': 'new_arrival'}})

        # Checkout, coupon, pincode/delivery
        if "checkout" in message or "pay" in message or "order now" in message:
            return JsonResponse({'reply': "Opening checkout. (Ensure your address & payment info is ready).", 'action': {'type':'redirect','page':'/checkout/'}})
        if "apply coupon" in message or "discount code" in message:
            coupon = message.split()[-1].upper()
            return JsonResponse({'reply': f"Applying coupon code {coupon}!", 'action': {'type':'apply_coupon','coupon':coupon}})
        if "deliver to" in message or "pincode" in message:
            pincode = "".join([c for c in message if c.isdigit()])
            return JsonResponse({'reply': f"Checking delivery availability for pincode {pincode}", 'action': {'type': 'check_pincode', 'pincode': pincode}})

        # -- FALLBACK -- (GPT+intent)
        def ai_response(prompt):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "You are Nova, a proactive, helpful robot shopping assistant for the Kartloop website. "
                        "If the user gives a customer service request (cart, order, cancel, tracking, checkout, wishlisting, profile update, reminders, notifications), reply kindly and add INTENT code as INTENT:[action_type][:extra_info]."
                        "If it's a navigation, reply with INTENT:redirect:/url."
                    )},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()

        fallback = ai_response(message)
        m = re.search(r'INTENT:([a-zA-Z_]+)(:?([^\s]+))?', fallback)
        if m:
            intent = m.group(1)
            arg = m.group(3)
            # Support INTENT:redirect:/url
            if intent == "redirect" and arg:
                return JsonResponse({'reply': fallback, 'action': {'type': 'redirect', 'page': arg}})
            if intent == "show_orders":
                return JsonResponse({'reply': fallback, 'action': {'type': 'show_orders'}})
            if intent == "add_to_cart":
                return JsonResponse({'reply': fallback, 'action': {'type': 'add_to_cart', 'product_name': arg}})
            if intent == "cancel_order":
                return JsonResponse({'reply': fallback, 'action': {'type': 'update_order_status', 'order_id': arg, 'new_status': 'cancelled'}})
            if intent == "place_order":
                return JsonResponse({'reply': fallback, 'action': {'type': 'place_order'}})
            if intent == "apply_coupon":
                return JsonResponse({'reply': fallback, 'action': {'type':'apply_coupon','coupon': arg}})
            if intent == "remind_offer":
                return JsonResponse({'reply': fallback, 'notify': {'type': 'special_offer', 'offer': arg}})
            if intent == "reminder":
                return JsonResponse({'reply': fallback, 'notify': {'type':'reminder','text': arg}})
        return JsonResponse({'reply': fallback})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
