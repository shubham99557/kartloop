from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, CustomerProfile, SellerProfile

class CustomerSignUpForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_customer = True
        if commit:
            user.save()
            CustomerProfile.objects.create(user=user)  # ✅ Required!
        return user


class SellerSignUpForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_seller = True
        if commit:
            user.save()
            # ✅ create seller profile
            SellerProfile.objects.create(user=user, shop_name="My Shop")
        return user


class EditCustomerForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = ['phone', 'gender', 'profile_image']
        widgets = {
            'gender': forms.Select(attrs={'class': 'form-select'}),
        }


class EditSellerForm(forms.ModelForm):
    class Meta:
        model = SellerProfile
        fields = ['shop_name', 'shop_address', 'phone', 'profile_image']


class EditUserForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email']
