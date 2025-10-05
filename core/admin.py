from django.contrib import admin
from .models import Vendor, Product, CartItem, Order, OrderItem, DeliveryMethod
from .models import Category

admin.site.register(Vendor)
admin.site.register(Product)
admin.site.register(CartItem)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(DeliveryMethod)
admin.site.register(Category)
