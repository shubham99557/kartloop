from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    path('products/', views.manage_products, name='manage_products'),
    path('products/edit/<int:pk>/', views.edit_product, name='edit_product'),
]
