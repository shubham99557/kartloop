from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone
from django.utils.text import slugify
User = get_user_model()

class HomeSection(models.Model):
    SECTION_TYPE_CHOICES = (
        ('products', 'Selected Products'),
        ('category', 'Category Products'),
        ('discount', 'Discount Based'),
        ('latest', 'Latest Products'),
    )

    title = models.CharField(max_length=120)
    slug = models.SlugField(unique=True, blank=True)
    section_type = models.CharField(
        max_length=20,
        choices=SECTION_TYPE_CHOICES
    )

    category = models.ForeignKey(
        'Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    products = models.ManyToManyField(
        'Product',
        blank=True
    )

    min_discount = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Used only for discount based section"
    )

    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
class Vendor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    shop_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.shop_name

    def total_sales(self):
        from .models import OrderItem
        return OrderItem.objects.filter(product__vendor=self).aggregate(models.Sum('quantity'))['quantity__sum'] or 0


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name



class Product(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.CharField(max_length=100)

    mrp_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.PositiveIntegerField(default=0)
    description = models.TextField()
    image = models.ImageField(upload_to='products/')
    created_at = models.DateTimeField(auto_now_add=True)
    views = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Automatically calculate discount_percent on save"""
        if self.mrp_price and self.selling_price and self.mrp_price > self.selling_price:
            self.discount_percent = round(
                ((self.mrp_price - self.selling_price) / self.mrp_price) * 100
            )
        else:
            self.discount_percent = 0
        super().save(*args, **kwargs)

    def delivery_estimate(self):
        return "Delivery by 3-5 days"

    def expected_delivery_date(self):
        min_date = timezone.now() + timedelta(days=3)
        max_date = timezone.now() + timedelta(days=5)
        return f"{min_date.strftime('%d %b')} - {max_date.strftime('%d %b')}"

    def average_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            return round(sum(r.rating for r in reviews) / reviews.count(), 1)
        return 0

class ProductVariant(models.Model):
    SIZE_CHOICES = [
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
        ('XXL', 'Extra Extra Large'),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    size = models.CharField(max_length=5, choices=SIZE_CHOICES)
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('product', 'size')
        ordering = ['size']

    def __str__(self):
        return f"{self.product.name} - {self.size} ({self.stock})"





class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.name}"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField()
    review = models.TextField()
    image = models.ImageField(upload_to='review_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.rating}⭐"


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=100, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    @property
    def unit_price(self):
        return self.product.selling_price


    @property
    def subtotal(self):
        """Calculate subtotal based on unit price and quantity."""
        return self.quantity * self.unit_price



class DeliveryMethod(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=8, decimal_places=2)
    estimated_days = models.PositiveIntegerField(default=3)
    is_cod_available = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} (₹{self.cost})"


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default="India")
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name}, {self.address_line1}, {self.city}"


class Order(models.Model):
    PAYMENT_CHOICES = [
        ('COD', 'Cash on Delivery'),
        ('RAZORPAY', 'Razorpay'),
        ('STRIPE', 'Stripe'),
    ]

    STATUS_CHOICES = [
        ('placed', 'Placed'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    delivery_method = models.ForeignKey(
        DeliveryMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='placed'
    )

    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    is_paid = models.BooleanField(default=False)

    paid_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username} ({self.status})"

    def calculate_total(self):
        """
        Safely calculate total from OrderItems + delivery cost.
        This should be called AFTER all OrderItems are created.
        """
        items_total = sum(
            item.quantity * item.price for item in self.items.all()
        )
        delivery_cost = self.delivery_method.cost if self.delivery_method else 0
        self.total_price = items_total + delivery_cost
        self.save(update_fields=['total_price'])

    @property
    def estimated_delivery(self):
        if self.delivery_method:
            return f"{self.delivery_method.estimated_days} days"
        return "N/A"



class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price per unit at time of order

    @property
    def unit_price(self):
        """Return the effective unit price at time of order."""
        return self.price

    @property
    def subtotal(self):
        return self.quantity * self.price

class Shipment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="shipment")

    shiprocket_order_id = models.CharField(max_length=100, blank=True, null=True)
    awb_code = models.CharField(max_length=100, blank=True, null=True)

    courier_name = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=50, default="Created")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Shipment for Order #{self.order.id}"


class Banner(models.Model):
    layout = models.CharField(
        max_length=20,
        choices=[
            ('text_left', 'Text Left'),
            ('text_right', 'Text Right'),
            ('full_image', 'Full Image'),
        ],
        default='text_left'
    )

    THEME_CHOICES = [
        ('tech', 'Tech / Electronics'),
        ('fashion', 'Fashion / Lifestyle'),
        ('grocery', 'Grocery / Daily Needs'),
        ('dark', 'Flash Sale / Dark'),
        ('republic', 'Republic Day 🇮🇳'),
    ]
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to='banners/')
    redirect_url = models.URLField(blank=True, null=True)
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default='tech')
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=1)
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority']

    def __str__(self):
        return self.title

class RecentlyViewedProduct(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recently_viewed_products'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.user} viewed {self.product}"


