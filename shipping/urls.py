from django.urls import path
from .views import create_shipment_view, track_shipment_view, test_nimbuspost_view
from . import views

urlpatterns = [
    path('create-shipment/', create_shipment_view, name='create_shipment'),
    path('track-shipment/<str:tracking_id>/', track_shipment_view, name='track_shipment'),
    path("test-nimbuspost/", views.test_nimbuspost_view, name="test_nimbuspost"),
]
