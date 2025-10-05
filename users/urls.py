from django.urls import reverse_lazy
from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views



app_name = 'users'

urlpatterns = [
    path('signup/customer/', views.customer_signup, name='customer-signup'),
    path('signup/seller/', views.seller_signup, name='seller-signup'),
    path('login/', views.user_login, name='login'),
    path('logout/', LogoutView.as_view(next_page='core:home'), name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit-profile'),


    # ✅ Password Reset URLs with correct templates (registration/)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset.html',
        success_url=reverse_lazy('users:password_reset_done')  
    ), name='password_reset'),

    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),


    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url=reverse_lazy('users:password_reset_complete')
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
]
