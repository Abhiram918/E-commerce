from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import CustomAuthenticationForm  # <-- Added this import

app_name = 'account'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(
        template_name='account/login.html', 
        authentication_form=CustomAuthenticationForm
    ), name='login'),
    
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('seller-register/', views.seller_register, name='seller_register'),
    path('profile/', views.profile_view, name='profile'),
    path('orders/', views.orders_view, name='orders'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('address-book/', views.address_book_view, name='address_book'),
    path('settings/', views.settings_view, name='settings'),
    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='account/password_change.html', success_url='/account/settings/'), name='password_change'),
    path('request-otp/', views.request_otp, name='request_otp'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('reviews/', views.reviews_view, name='reviews'),
    path('write-review/<int:product_id>/', views.write_review, name='write_review'),
    path('edit-review/<int:review_id>/', views.edit_review, name='edit_review'),
    path('get-bank-details/', views.get_bank_details, name='get_bank_details'),
    path('get-pincode-details/', views.get_pincode_details, name='get_pincode_details'),
    path('seller/payments/', views.seller_payments, name='seller_payments'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/approve-seller/<int:seller_id>/', views.approve_seller, name='approve_seller'),
    path('admin/update-order-status/<int:order_id>/', views.update_order_status, name='update_order_status'),
]