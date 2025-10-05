import re
import requests
from django.conf import settings
from django.utils.html import escape
from rapidfuzz import fuzz, process
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Max
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta
from django.db import IntegrityError
from .models import (
    Product, Vendor, CartItem, Order, OrderItem,
    DeliveryMethod, Address, Review, ProductImage
)
from .forms import ProductForm, CheckoutForm, ReviewForm
from users.models import SellerProfile
from shipping.utils import NimbusPostAPI
from core.models import Shipment


# ------------------ Public Views ------------------
def home(request):
    return render(request, 'home.html')


def home_view(request):
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    products = Product.objects.all()

    if category:
        products = products.filter(category__name__iexact=category)


    if query:
        name_id = [(p.name, p.id) for p in products]
        matches = process.extract(query, name_id, scorer=fuzz.token_sort_ratio, limit=25)
        ids = [pid for (name, pid), score, _ in matches if score >= 60]
        products = products.filter(id__in=ids)
    else:
        products = products.order_by('-id')

    paginator = Paginator(products, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'home.html', {'products': page_obj, 'page_obj': page_obj})


# ------------------ Search ------------------
def highlight_query_in_text(text, query):
    text_escaped = escape(text)
    query_escaped = escape(query)
    pattern = re.compile(re.escape(query_escaped), re.IGNORECASE)
    return pattern.sub(lambda m: f'<mark>{m.group(0)}</mark>', text_escaped)


def search_view(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.all()

    if query:
        name_to_id = {p.name: p.id for p in products}
        matches = process.extract(query, name_to_id.keys(), scorer=fuzz.partial_token_sort_ratio, limit=25)
        matched_names = [name for name, score, _ in matches if score >= 60]
        matched_ids = [name_to_id[name] for name in matched_names]

        if matched_ids:
            products = products.filter(id__in=matched_ids).order_by('name')
        else:
            products = Product.objects.none()
    else:
        products = Product.objects.none()

    paginator = Paginator(products, 12)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)

    for product in paged_products:
        product.highlighted_name = highlight_query_in_text(product.name, query) if query else escape(product.name)

    return render(request, 'search_results.html', {'products': paged_products, 'query': query})


CATEGORY_SLUG_MAPPING = {
    'men-s-wear': "men's wear",
    'womens': "women's wear",
    'kids': "kid's wear",
}


def category_products_view(request, category_slug):
    category_name = CATEGORY_SLUG_MAPPING.get(category_slug.lower())
    if not category_name:
        products = Product.objects.none()
    else:
        products = Product.objects.filter(category__name__iexact=category_name).order_by('-id')


    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'search_results.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'category': category_name.title(),
    })


def all_products(request):
    products = Product.objects.all()
    return render(request, 'core/all_products.html', {'products': products})


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.views += 1
    product.save()

    related = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]

    all_reviews = Review.objects.filter(product=product).order_by('-created_at')
    user_review = all_reviews.filter(user=request.user).first() if request.user.is_authenticated else None

    if request.user.is_authenticated:
        latest_reviews_ids = (
            all_reviews.exclude(user=request.user)
            .values('user')
            .annotate(latest_id=Max('id'))
            .values_list('latest_id', flat=True)
        )
    else:
        latest_reviews_ids = (
            all_reviews
            .values('user')
            .annotate(latest_id=Max('id'))
            .values_list('latest_id', flat=True)
        )

    reviews = Review.objects.filter(id__in=latest_reviews_ids).order_by('-created_at')

    if request.method == 'POST' and request.user.is_authenticated:
        form = ReviewForm(request.POST, request.FILES)
        if form.is_valid():
            if user_review:
                messages.info(request, "You have already submitted a review for this product.")
            else:
                try:
                    review = form.save(commit=False)
                    review.product = product
                    review.user = request.user
                    review.save()
                    messages.success(request, "Your review was submitted.")
                    return redirect('core:product_detail', pk=product.pk)
                except IntegrityError:
                    messages.error(request, "You have already submitted a review for this product.")
    else:
        form = ReviewForm()

    images = ProductImage.objects.filter(product=product)

    return render(request, 'core/product_detail.html', {
        'product': product,
        'images': images,
        'related_products': related,
        'reviews': reviews,
        'user_review': user_review,
        'expected_delivery': timezone.now() + timedelta(days=product.delivery_days if hasattr(product, 'delivery_days') else 4),
        'form': form,
    })


# ------------------ Cart Views ------------------
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.user.is_authenticated:
        cart_item, _ = CartItem.objects.get_or_create(user=request.user, product=product)
        cart_item.quantity += 1
        cart_item.save()
    else:
        cart = request.session.get('cart', {})
        cart[str(product_id)] = cart.get(str(product_id), 0) + 1
        request.session['cart'] = cart
    return redirect('core:view_cart')


def view_cart(request):
    if request.user.is_authenticated:
        items = CartItem.objects.filter(user=request.user)
    else:
        items = CartItem.objects.filter(session_key=request.session.session_key)

    total = sum(item.subtotal for item in items)

    return render(request, 'core/cart.html', {'items': items, 'total': total})


def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id)
    cart_item.delete()
    messages.success(request, "Item removed from cart.")
    return redirect('core:view_cart')


@require_POST
def update_cart_quantity(request, item_id):
    action = request.POST.get('action')

    if request.user.is_authenticated:
        try:
            cart_item = CartItem.objects.get(id=item_id, user=request.user)
        except CartItem.DoesNotExist:
            return JsonResponse({'error': 'Cart item not found'}, status=404)

        if action == 'increment' and cart_item.quantity < cart_item.product.stock:
            cart_item.quantity += 1
        elif action == 'decrement' and cart_item.quantity > 1:
            cart_item.quantity -= 1
        cart_item.save()

        return JsonResponse({'success': True, 'new_quantity': cart_item.quantity, 'product_id': cart_item.product.id})

    else:
        cart = request.session.get('cart', {})
        product_id = str(item_id)

        if product_id not in cart:
            return JsonResponse({'error': 'Item not found in session cart'}, status=404)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)

        quantity = cart[product_id]

        if action == 'increment' and quantity < product.stock:
            quantity += 1
        elif action == 'decrement':
            quantity = max(1, quantity - 1)

        cart[product_id] = quantity
        request.session['cart'] = cart

        return JsonResponse({'success': True, 'new_quantity': quantity, 'product_id': product_id})


# ------------------ Checkout Views ------------------
@login_required
def checkout_view(request):
    cart_items = CartItem.objects.filter(user=request.user)
    delivery_methods = DeliveryMethod.objects.all()

    if request.method == 'POST':
        form = CheckoutForm(request.POST, user=request.user)
        if form.is_valid():
            # 1️⃣ Choose address (saved or new)
            if form.cleaned_data['use_saved_address']:
                selected_address = form.cleaned_data['saved_address']
            else:
                selected_address = Address.objects.create(
                    user=request.user,
                    full_name=form.cleaned_data['full_name'],
                    phone=form.cleaned_data['phone'],
                    address_line1=form.cleaned_data['address_line1'],
                    address_line2=form.cleaned_data['address_line2'],
                    city=form.cleaned_data['city'],
                    state=form.cleaned_data['state'],
                    postal_code=form.cleaned_data['postal_code'],
                    country=form.cleaned_data['country']
                )

            # 2️⃣ Calculate totals
            cart_total = sum(item.unit_price * item.quantity for item in cart_items)
            delivery_method = form.cleaned_data['delivery_method']
            total_price = cart_total + delivery_method.cost

            # 3️⃣ Create the order in your DB
            order = Order.objects.create(
                user=request.user,
                address=selected_address,
                delivery_method=delivery_method,
                payment_method=form.cleaned_data['payment_method'],
                total_price=total_price
            )

            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.unit_price
                )

            # 4️⃣ Create shipment in NimbusPost API
            try:
                nimbus_url = "https://app.nimbuspost.com/api/shipment/create"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.NIMBUS_API_KEY}"
                }

                shipment_payload = {
                    "order_number": str(order.id),
                    "payment_type": "prepaid" if form.cleaned_data['payment_method'] == 'prepaid' else "cod",
                    "shipping_charges": delivery_method.cost,
                    "cod_charges": 0 if form.cleaned_data['payment_method'] == 'prepaid' else delivery_method.cost,
                    "customer_name": selected_address.full_name,
                    "customer_phone": selected_address.phone,
                    "customer_email": request.user.email,
                    "customer_address": f"{selected_address.address_line1}, {selected_address.address_line2}",
                    "customer_city": selected_address.city,
                    "customer_state": selected_address.state,
                    "customer_pincode": selected_address.postal_code,
                    "customer_country": selected_address.country,
                    "products": [
                        {
                            "name": item.product.name,
                            "sku": str(item.product.id),
                            "quantity": item.quantity,
                            "price": float(item.unit_price)
                        }
                        for item in cart_items
                    ],
                    "total": float(total_price)
                }

                response = requests.post(nimbus_url, json=shipment_payload, headers=headers)

                if response.status_code != 200:
                    print("NimbusPost Error:", response.text)

            except Exception as e:
                print("Shipment creation failed:", e)

            # 5️⃣ Clear cart
            cart_items.delete()

            # 6️⃣ Redirect to order summary
            return redirect('core:order_summary', order_id=order.id)
    else:
        form = CheckoutForm(user=request.user)

    return render(request, 'core/checkout.html', {
        'cart_items': cart_items,
        'delivery_methods': delivery_methods,
        'form': form,
    })


@login_required
def buy_now_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if product.stock <= 0:
        return redirect('core:product_detail', product_id=product.id)
    CartItem.objects.filter(user=request.user).delete()
    CartItem.objects.create(user=request.user, product=product, quantity=1)
    return redirect('core:checkout')


@login_required
def order_summary_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = OrderItem.objects.filter(order=order)
    return render(request, 'core/order_summary.html', {'order': order, 'order_items': order_items})


# ------------------ Vendor Views ------------------
@login_required
def vendor_dashboard(request):
    if not request.user.is_seller:
        return redirect('home')

    vendor = get_object_or_404(Vendor, user=request.user)
    profile = SellerProfile.objects.filter(user=request.user).first()
    products = Product.objects.filter(vendor=vendor)
    order_items = OrderItem.objects.filter(product__in=products).select_related('order', 'product')
    order_ids = order_items.values_list('order_id', flat=True).distinct()
    orders = Order.objects.filter(id__in=order_ids).order_by('-created_at')

    total_orders = order_items.count()
    total_sales = order_items.aggregate(total=Sum('price'))['total'] or 0

    sales_data = []
    for product in products:
        product_items = order_items.filter(product=product)
        product_total_sales = sum(item.quantity for item in product_items)
        sales_data.append({'name': product.name, 'sales': product_total_sales})

    return render(request, 'core/vendor_dashboard.html', {
        'vendor': vendor,
        'profile': profile,
        'products': products,
        'orders': orders,
        'sales_data': sales_data,
        'total_orders': total_orders,
        'total_sales': total_sales,
    })


@login_required
def add_product(request):
    if not request.user.is_seller:
        return redirect('home')

    vendor = Vendor.objects.get(user=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.vendor = vendor
            product.save()
            # Handle multiple image uploads from 'more_images' input field
            images = request.FILES.getlist('more_images')
            for img in images:
                ProductImage.objects.create(product=product, image=img)
            return redirect('core:vendor_dashboard')
    else:
        form = ProductForm()

    return render(request, 'vendor/add_product.html', {'form': form})


@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, vendor=request.user.vendor)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            # Handle multiple image uploads from 'more_images' input field
            images = request.FILES.getlist('more_images')
            for img in images:
                ProductImage.objects.create(product=product, image=img)
            return redirect('core:vendor_dashboard')
    else:
        form = ProductForm(instance=product)
    return render(request, 'core/edit_product.html', {'form': form, 'product': product})


@login_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, vendor=request.user.vendor)
    if request.method == 'POST':
        product.delete()
        return redirect('core:vendor_dashboard')
    return render(request, 'core/confirm_delete.html', {'product': product})
