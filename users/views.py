from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required

from .forms import (
    CustomerSignUpForm, SellerSignUpForm,
    EditCustomerForm, EditSellerForm, EditUserForm
)
from .models import CustomerProfile, SellerProfile, CustomUser
from core.models import Vendor

User = get_user_model()

# --------------------------
# Customer Signup View
# --------------------------
def customer_signup(request):
    if request.method == 'POST':
        form = CustomerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()  # ✅ This already sets is_customer = True
            # Create profile only if it doesn't exist
            CustomerProfile.objects.get_or_create(user=user)

            login(request, user)
            send_welcome_email(user.email)
            return redirect('core:home')
        else:
            print("Form errors:", form.errors)  # Optional debug log
    else:
        form = CustomerSignUpForm()
    return render(request, 'users/signup.html', {'form': form, 'type': 'Customer'})





# --------------------------
# Seller Signup View
# --------------------------
def seller_signup(request):
    if request.method == 'POST':
        form = SellerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_seller = True
            user.save()

            # Create associated Vendor and SellerProfile
            Vendor.objects.create(user=user, shop_name="My Shop")
            SellerProfile.objects.create(user=user, shop_name="My Shop")

            login(request, user)
            return redirect('core:vendor_dashboard')
        else:
            messages.error(request, "Form is invalid. Please fix the errors.")
    else:
        form = SellerSignUpForm()
    return render(request, 'users/seller_signup.html', {'form': form})




# --------------------------
# Login View
# --------------------------
def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)

            if not remember:
                request.session.set_expiry(0)

            if user.is_seller:
                return redirect('core:vendor_dashboard')
            elif user.is_customer:
                return redirect('core:home')
            else:
                return redirect('core:home')
        else:
            messages.error(request, 'Invalid credentials')
    return render(request, 'users/login.html')

# --------------------------
# Logout View
# --------------------------
def logout_view(request):
    logout(request)
    return redirect('core:home')

# --------------------------
# Send Welcome Email
# --------------------------
def send_welcome_email(user_email):
    send_mail(
        'Welcome to Kartloop!',
        'Thank you for registering at Kartloop!',
        'kartloop07@gmail.com',
        [user_email],
        fail_silently=False,
    )

# --------------------------
# Universal Profile View
# --------------------------
@login_required
def profile_view(request):
    user = request.user
    context = {
        'user': user,
        'is_seller': user.is_seller,
    }

    if user.is_seller:
        context['vendor'] = Vendor.objects.filter(user=user).first()
        context['profile'] = SellerProfile.objects.filter(user=user).first()
    elif user.is_customer:
        context['profile'] = CustomerProfile.objects.filter(user=user).first()

    return render(request, 'users/universal_profile.html', context)

# --------------------------
# Edit Profile View
# --------------------------
@login_required
def edit_profile(request):
    user = request.user

    if user.is_seller:
        profile, _ = SellerProfile.objects.get_or_create(user=user)
        UserFormClass = EditUserForm
        ProfileFormClass = EditSellerForm
    elif user.is_customer:
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        UserFormClass = EditUserForm
        ProfileFormClass = EditCustomerForm
    else:
        messages.error(request, "User type not recognized.")
        return redirect('core:home')

    if request.method == 'POST':
        user_form = UserFormClass(request.POST, instance=user)
        profile_form = ProfileFormClass(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('users:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        user_form = UserFormClass(instance=user)
        profile_form = ProfileFormClass(instance=profile)

    return render(request, 'users/edit_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })
