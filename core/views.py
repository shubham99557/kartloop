import re
from .forms import ProductForm, CheckoutForm, ReviewForm, ProductVariantFormSet
import requests
import json
from django.conf import settings
from django.utils.html import escape
from rapidfuzz import fuzz, process
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Max, Avg, Q, F
from django.db.models import Exists, OuterRef
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta
from django.db import IntegrityError
from .models import (
    Product, Vendor, CartItem, Order, OrderItem, HomeSection, ProductVariant,
    DeliveryMethod, Address, Review, ProductImage, Category, Shipment, Banner, RecentlyViewedProduct
)
from users.models import SellerProfile

from .shiprocket import create_shiprocket_order


# ------------------ Public Views ------------------
def home(request):
    # ------------------ CATEGORIES ------------------
    categories = Category.objects.filter(is_active=True)

    # ------------------ DEFAULT PRODUCTS (FALLBACK) ------------------
    products = (
        Product.objects
        .filter(variants__stock__gt=0)
        .distinct()
        .order_by('-id')[:12]
    )


    # ------------------ DYNAMIC BANNERS ------------------
    now = timezone.localtime()
    banners = Banner.objects.filter(
        is_active=True
    ).filter(
        Q(start_date__lte=now) | Q(start_date__isnull=True),
        Q(end_date__gte=now) | Q(end_date__isnull=True)
    ).order_by('priority')

    # ------------------ RECENTLY VIEWED ------------------
    recently_viewed_products = []
    if request.user.is_authenticated:
        recently_viewed_products = (
            RecentlyViewedProduct.objects
            .filter(user=request.user)
            .select_related('product')
            .order_by('-viewed_at')[:10]
        )

    # ================== 🔥 DYNAMIC HOME SECTIONS ==================
    raw_sections = HomeSection.objects.filter(is_active=True).order_by('position')

    home_sections = []

    for section in raw_sections:
        # 1️⃣ MANUAL PRODUCTS
        if section.section_type == 'products':
            items = section.products.filter(
                variants__stock__gt=0
            ).distinct()


        # 2️⃣ CATEGORY BASED
        elif section.section_type == 'category' and section.category:
            items = (
                Product.objects
                .filter(
                    category=section.category,
                    variants__stock__gt=0
                ).distinct()

                .order_by('-id')[:12]
            )

        # 3️⃣ DISCOUNT BASED
        elif section.section_type == 'discount' and section.min_discount:
            items = (
                Product.objects
                .filter(
                    discount_percent__gte=section.min_discount,
                    variants__stock__gt=0
                ).distinct()

                .order_by('-discount_percent')[:12]
            )

        # 4️⃣ LATEST PRODUCTS
        elif section.section_type == 'latest':
            items = (
                Product.objects
                .filter(variants__stock__gt=0).distinct()
                .order_by('-created_at')[:12]
            )

        else:
            items = []

        home_sections.append({
            'title': section.title,
            'slug': section.slug,
            'items': items
        })



    # ================== RENDER ==================
    return render(request, 'home.html', {
        'categories': categories,
        'products': products,
        'banners': banners,
        'recently_viewed_products': recently_viewed_products,
        'home_sections': home_sections,
    })




#def home_view(request):
#    query = request.GET.get('q', '').strip()
#    category = request.GET.get('category', '').strip()
#
#    products = Product.objects.all()
#
#    if category:
#        products = products.filter(category__name__iexact=category)
#
#
#    if query:
#        name_id = [(p.name, p.id) for p in products]
#        matches = process.extract(query, name_id, scorer=fuzz.token_sort_ratio, limit=25)
#        ids = [pid for (name, pid), score, _ in matches if score >= 60]
#        products = products.filter(id__in=ids)
#    else:
#        products = products.order_by('-id')
#
#    paginator = Paginator(products, 8)
#    page_number = request.GET.get('page')
#    page_obj = paginator.get_page(page_number)
#
#    return render(request, 'home.html', {'products': page_obj, 'page_obj': page_obj})


# ------------------ Search ------------------
def highlight_query(text, query):
    """
    Highlight all query words in a text.
    """
    text_escaped = escape(text)
    for word in query.split():
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        text_escaped = pattern.sub(lambda m: f'<mark>{m.group(0)}</mark>', text_escaped)
    return text_escaped


def advanced_search_view(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()

    products = Product.objects.annotate(
        has_stock=Exists(
            ProductVariant.objects.filter(product=OuterRef('pk'), stock__gt=0)
        )
    ).filter(has_stock=True)

    # Optional category filter
    if category_slug:
        products = products.filter(category__slug=category_slug)

    # Search filter
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query) |
            Q(vendor__user__username__icontains=query)
        ).distinct()

    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Highlight query in name & description
    for product in page_obj:
        product.highlighted_name = highlight_query(product.name, query)
        product.highlighted_description = highlight_query(product.description or '', query)

    return render(request, 'search_results.html', {
        'products': page_obj,
        'query': query,
        'page_obj': page_obj
    })





#----------------category--------------------

def category_products_view(request, category_slug):
    category = get_object_or_404(Category, slug=category_slug, is_active=True)

    products = Product.objects.annotate(
        has_stock=Exists(
            ProductVariant.objects.filter(product=OuterRef('pk'), stock__gt=0)
        )
    ).filter(category=category, has_stock=True).distinct().order_by('-id')

    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'search_results.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'category': category.name,
    })



def all_products(request):
    products = Product.objects.annotate(
        has_stock=Exists(
            ProductVariant.objects.filter(product=OuterRef('pk'), stock__gt=0)
        )
    ).filter(has_stock=True).distinct()

    # 🔥 DISCOUNT FILTER (FROM BANNER)
    discount = request.GET.get('discount')
    if discount:
        products = products.filter(discount_percent__gte=int(discount))

    # 🔹 OPTIONAL: category filter (future-ready)
    category_slug = request.GET.get('category')
    if category_slug:
        products = products.filter(category__slug=category_slug)

    context = {
        'products': products,
        'discount_filter': discount,
    }
    return render(request, 'core/all_products.html', context)



def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)

    # ================== RECENTLY VIEWED (DB BASED) ==================
    if request.user.is_authenticated:
        RecentlyViewedProduct.objects.update_or_create(
            user=request.user,
            product=product,
        )

        # Keep only last 10 viewed products
        qs = RecentlyViewedProduct.objects.filter(user=request.user)
        if qs.count() > 10:
            qs.last().delete()

    # ================== INCREASE VIEWS ==================
    product.views += 1
    product.save(update_fields=['views'])

    # ================== IMAGES ==================
    images = ProductImage.objects.filter(product=product)

    # ================== RELATED PRODUCTS ==================
    related_products = (
        Product.objects
        .filter(category=product.category)
        .exclude(id=product.id)[:4]
    )

    # ================== REVIEWS ==================
    reviews = (
        Review.objects
        .filter(product=product)
        .select_related('user')
        .order_by('-created_at')
    )

    user_review = None
    if request.user.is_authenticated:
        user_review = Review.objects.filter(
            product=product,
            user=request.user
        ).first()

    # ================== HANDLE REVIEW SUBMISSION ==================
    if request.method == 'POST':

        if not request.user.is_authenticated:
            messages.warning(request, "Please login to write a review.")
            return redirect('users:login')

        if user_review:
            messages.info(request, "You have already reviewed this product.")
            return redirect('core:product_detail', pk=product.pk)

        form = ReviewForm(request.POST, request.FILES)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()

            # Update average rating
            avg_rating = Review.objects.filter(product=product).aggregate(
                avg=Avg('rating')
            )['avg'] or 0

            product.average_rating = round(avg_rating, 1)
            product.save(update_fields=['average_rating'])

            messages.success(request, "Review submitted successfully.")
            return redirect('core:product_detail', pk=product.pk)
    else:
        form = ReviewForm()

    # ================== VARIANTS (JSON SERIALIZABLE) ==================
    # Only include id, size, stock for JS
    variants_qs = product.variants.filter(stock__gt=0)
    variants = list(variants_qs.values('id', 'size', 'stock'))

    # ================== RENDER ==================
    return render(request, 'core/product_detail.html', {
        'product': product,
        'images': images,
        'reviews': reviews,
        'user_review': user_review,
        'related_products': related_products,
        'expected_delivery': timezone.now() + timedelta(days=4),
        'form': form,
        'variants': variants,  # ✅ now JSON-serializable
    })




# ------------------ Cart Views ------------------
@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # ✅ Get variant ID from POST
    variant_id = request.POST.get('variant_id')
    if not variant_id:
        messages.error(request, "Please select a size before adding to cart.")
        return redirect('core:product_detail', pk=product.id)

    variant = get_object_or_404(ProductVariant, id=variant_id, product=product)

    # ✅ Check variant stock
    if variant.stock <= 0:
        messages.error(request, f"{variant.size} size of {product.name} is out of stock.")
        return redirect('core:product_detail', pk=product.id)

    # ✅ Get or create cart item
    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product,
        variant=variant
    )

    if cart_item.quantity < variant.stock:
        cart_item.quantity += 1
        cart_item.save()
        messages.success(request, f"Added {variant.size} {product.name} to cart.")
    else:
        messages.warning(request, f"Only {variant.stock} units of {variant.size} {product.name} available.")

    return redirect('core:view_cart')




def view_cart(request):
    if request.user.is_authenticated:
        items = CartItem.objects.filter(user=request.user)
    else:
        items = CartItem.objects.filter(session_key=request.session.session_key)

    total = sum(item.unit_price * item.quantity for item in items)

    return render(request, 'core/cart.html', {'items': items, 'total': total})


def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id)
    cart_item.delete()
    messages.success(request, "Item removed from cart.")
    return redirect('core:view_cart')


@require_POST
def update_cart_quantity(request, item_id):
    try:
        data = json.loads(request.body)
        action = data.get('action')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    if request.user.is_authenticated:
        try:
            cart_item = CartItem.objects.get(id=item_id, user=request.user)
        except CartItem.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Cart item not found'}, status=404)

        variant_stock = cart_item.variant.stock


        if action == 'increment' and cart_item.quantity < variant_stock:
            cart_item.quantity += 1
        elif action == 'decrement' and cart_item.quantity > 1:
            cart_item.quantity -= 1

        cart_item.save()

        # 🔑 CALCULATIONS
        subtotal = cart_item.unit_price * cart_item.quantity
        cart_items = CartItem.objects.filter(user=request.user)
        cart_total = sum(item.unit_price * item.quantity for item in cart_items)

        return JsonResponse({
            'success': True,
            'quantity': cart_item.quantity,
            'subtotal': subtotal,
            'cart_total': cart_total,
        })

    return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)



# ------------------ Checkout Views ------------------
@login_required
def checkout_view(request):
    cart_items = CartItem.objects.filter(user=request.user)

    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('core:view_cart')

    cart_subtotal = sum(item.unit_price * item.quantity for item in cart_items)

    if request.method == 'POST':
        form = CheckoutForm(request.POST, user=request.user)
        if form.is_valid():

            # STOCK VALIDATION per variant
            for item in cart_items:
                available_stock = item.variant.stock if item.variant else item.product.stock
                if item.quantity > available_stock:
                    messages.error(
                        request,
                        f"Only {available_stock} units of {item.product.name} ({item.variant.size if item.variant else 'default'}) available."
                    )
                    return redirect('core:view_cart')

            # ADDRESS
            if form.cleaned_data.get('use_saved_address'):
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

            delivery_method = form.cleaned_data['delivery_method']
            total_price = cart_subtotal + delivery_method.cost

            # CREATE ORDER
            order = Order.objects.create(
                user=request.user,
                address=selected_address,
                delivery_method=delivery_method,
                payment_method=form.cleaned_data['payment_method'],
                total_price=total_price,
                status='placed',
                is_paid=(form.cleaned_data['payment_method'] != 'COD')
            )

            # CREATE ORDER ITEMS + UPDATE STOCK
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    variant=item.variant,
                    quantity=item.quantity,
                    price=item.unit_price
                )

                # Deduct variant stock
                if item.variant:
                    item.variant.stock -= item.quantity
                    item.variant.save(update_fields=['stock'])


            # SHIPMENT
            if settings.SHIPROCKET_ENABLED:
                create_shiprocket_order(order)
            else:
                Shipment.objects.get_or_create(order=order, defaults={"status": "pending_kyc"})

            # CLEAR CART
            cart_items.delete()

            messages.success(request, "Order placed successfully!")
            return redirect('core:order_summary', order_id=order.id)

    else:
        form = CheckoutForm(user=request.user)

    return render(request, 'core/checkout.html', {
        'cart_items': cart_items,
        'cart_subtotal': cart_subtotal,
        'form': form,
    })





@login_required
def buy_now_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # ✅ Get variant_id from POST
    variant_id = request.POST.get('variant_id')
    if not variant_id:
        messages.error(request, "Please select a size before buying.")
        return redirect('core:product_detail', pk=product.id)

    variant = get_object_or_404(ProductVariant, id=variant_id, product=product)

    # ✅ Check variant stock
    if variant.stock <= 0:
        messages.error(request, f"{variant.size} size of {product.name} is out of stock.")
        return redirect('core:product_detail', pk=product.id)

    # Clear existing cart and add this product
    CartItem.objects.filter(user=request.user).delete()
    CartItem.objects.create(user=request.user, product=product, variant=variant, quantity=1)

    return redirect('core:checkout')





@login_required
def order_summary_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Fetch order items
    order_items = OrderItem.objects.filter(order=order).select_related('product')

    # Calculate totals safely
    subtotal = 0
    for item in order_items:
        subtotal += item.subtotal

    delivery_cost = order.delivery_method.cost if order.delivery_method else 0
    grand_total = subtotal + delivery_cost

    # Attach shipment if exists (for future use)
    shipment = None
    try:
        shipment = order.shipment
    except:
        shipment = None

    return render(request, 'core/order_summary.html', {
        'order': order,
        'order_items': order_items,
        'subtotal': subtotal,
        'delivery_cost': delivery_cost,
        'grand_total': grand_total,
        'shipment': shipment,
    })




# ------------------ Vendor Views ------------------
@login_required
def vendor_dashboard(request):
    if not request.user.is_seller:
        return redirect('core:home')

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
        return redirect('core:home')

    vendor = Vendor.objects.get(user=request.user)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        variant_formset = ProductVariantFormSet(request.POST)

        if form.is_valid() and variant_formset.is_valid():
            product = form.save(commit=False)
            product.vendor = vendor
            product.save()

            # attach product to variants
            variant_formset.instance = product
            variant_formset.save()

            # 🔑 update total stock automatically
            product.stock = product.variants.aggregate(
                total=Sum('stock')
            )['total'] or 0
            product.save(update_fields=['stock'])

            # multiple images
            images = request.FILES.getlist('more_images')
            for img in images:
                ProductImage.objects.create(product=product, image=img)

            messages.success(request, "Product added successfully.")
            return redirect('core:vendor_dashboard')
    else:
        form = ProductForm()
        variant_formset = ProductVariantFormSet()

    return render(request, 'vendor/add_product.html', {
        'form': form,
        'variant_formset': variant_formset,
    })



@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, vendor=request.user.vendor)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        variant_formset = ProductVariantFormSet(request.POST, instance=product)

        if form.is_valid() and variant_formset.is_valid():
            form.save()
            variant_formset.save()

            # 🔑 recalculate stock
            product.stock = product.variants.aggregate(
                total=Sum('stock')
            )['total'] or 0
            product.save(update_fields=['stock'])

            # extra images
            images = request.FILES.getlist('more_images')
            for img in images:
                ProductImage.objects.create(product=product, image=img)

            messages.success(request, "Product updated successfully.")
            return redirect('core:vendor_dashboard')
    else:
        form = ProductForm(instance=product)
        variant_formset = ProductVariantFormSet(instance=product)

    return render(request, 'core/edit_product.html', {
        'form': form,
        'product': product,
        'variant_formset': variant_formset,
    })



@login_required
def my_orders_view(request):
    orders = (
        Order.objects
        .filter(user=request.user)
        .prefetch_related('items')
        .select_related('shipment', 'delivery_method')
        .order_by('-created_at')
    )

    for order in orders:
        order.items_list = order.items.all()
        order.num_items = sum(item.quantity for item in order.items_list)
        order.subtotal = sum(item.price * item.quantity for item in order.items_list)
        order.shipment_obj = getattr(order, 'shipment', None)

    return render(request, 'core/my_orders.html', {'orders': orders})





@login_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, vendor=request.user.vendor)
    if request.method == 'POST':
        product.delete()
        return redirect('core:vendor_dashboard')
    return render(request, 'core/confirm_delete.html', {'product': product})





