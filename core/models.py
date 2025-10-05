from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone
User = get_user_model()


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

    def __str__(self):
        return self.name


class Product(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    offer_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    description = models.TextField()
    stock = models.PositiveIntegerField(default=10)
    image = models.ImageField(upload_to='products/')
    created_at = models.DateTimeField(auto_now_add=True)
    views = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

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

    @property
    def discount_percent(self):
        if self.offer_price and self.offer_price < self.price:
            discount = ((self.price - self.offer_price) / self.price) * 100
            return round(discount)
        return 0


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
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    @property
    def unit_price(self):
        """Return the effective unit price — offer_price if valid else regular price."""
        if self.product.offer_price and self.product.offer_price < self.product.price:
            return self.product.offer_price
        return self.product.price

    @property
    def subtotal(self):
        """Calculate subtotal based on effective unit price and quantity."""
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

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    delivery_method = models.ForeignKey(DeliveryMethod, on_delete=models.SET_NULL, null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"

    @property
    def estimated_delivery(self):
        if self.delivery_method:
            return f"{self.delivery_method.estimated_days} days"
        return "N/A"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price per unit at time of order

    @property
    def unit_price(self):
        """Return the effective unit price at time of order."""
        return self.price

    def subtotal(self):
        return self.quantity * self.price
    
class Shipment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="shipment")
    tracking_id = models.CharField(max_length=100)
    courier_name = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=50, default="Created")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Shipment for Order #{self.order.id} - {self.status}"

