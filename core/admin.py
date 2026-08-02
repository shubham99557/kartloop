from django.contrib import admin
from .models import (
    Vendor, Product, CartItem, Order, OrderItem,
    DeliveryMethod, Category, Shipment, Banner,
    HomeSection, ProductVariant
)

# ===================== PRODUCT VARIANT INLINE =====================
class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    min_num = 1


# ===================== PRODUCT ADMIN =====================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'vendor', 'selling_price', 'discount_percent')
    list_filter = ('category', 'vendor')
    search_fields = ('name', 'brand')
    inlines = [ProductVariantInline]


# ===================== OTHER ADMINS =====================
admin.site.register(Vendor)
admin.site.register(CartItem)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(DeliveryMethod)
admin.site.register(Category)
admin.site.register(Shipment)


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'priority', 'start_date', 'end_date')
    list_editable = ('is_active', 'priority')
    list_filter = ('is_active',)


@admin.register(HomeSection)
class HomeSectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'section_type', 'is_active', 'position')
    list_filter = ('section_type', 'is_active')
    search_fields = ('title',)
    filter_horizontal = ('products',)
    ordering = ('position',)
