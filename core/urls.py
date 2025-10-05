from django.urls import path
from . import views
from .views import order_summary_view, checkout_view, buy_now_view

app_name = 'core'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('products/', views.all_products, name='all_products'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', checkout_view, name='checkout'),
    # vendor urls and product management
    path('core/dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('vendor/add-product/', views.add_product, name='add_product'),
    path('vendor/edit-product/<int:product_id>/', views.edit_product, name='edit_product'),
    path('vendor/delete-product/<int:product_id>/', views.delete_product, name='delete_product'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('update-cart/<int:item_id>/', views.update_cart_quantity, name='update_cart_quantity'),
    path('search/', views.search_view, name='search'),
    path('order/summary/<int:order_id>/', order_summary_view, name='order_summary'),
    path('buy-now/<int:product_id>/', buy_now_view, name='buy_now'),
    path('category/<str:category_slug>/', views.category_products_view, name='category_products'),




]
# This file defines the URL patterns for the core application of the Kartloop project.