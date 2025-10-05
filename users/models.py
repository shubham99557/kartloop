from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    is_customer = models.BooleanField(default=False)
    is_seller = models.BooleanField(default=False)

    def __str__(self):
        return self.username


class SellerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    shop_name = models.CharField(max_length=100)
    shop_address = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='seller_profile_images/', blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return self.user.email



class CustomerProfile(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)

    def __str__(self):
        return self.user.email

