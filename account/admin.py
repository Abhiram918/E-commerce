from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, SellerProfile, CustomerProfile

class SellerProfileInline(admin.StackedInline):
    model = SellerProfile
    can_delete = False
    verbose_name_plural = 'Seller Profile'
    fk_name = 'user'

class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    can_delete = False
    verbose_name_plural = 'Customer Profile'
    fk_name = 'user'

class CustomUserAdmin(UserAdmin):
    inlines = (SellerProfileInline, CustomerProfileInline)
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    
    # Customizing fieldsets to include 'role' and 'phone'
    fieldsets = UserAdmin.fieldsets + (
        ('Extra Fields', {'fields': ('role', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra Fields', {'fields': ('role', 'phone', 'email')}),
    )

class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'user', 'is_approved', 'commission_rate')
    list_filter = ('is_approved',)
    search_fields = ('store_name', 'user__username', 'user__email')

class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'default_address')
    search_fields = ('user__username', 'user__email', 'default_address')

admin.site.register(User, CustomUserAdmin)
admin.site.register(SellerProfile, SellerProfileAdmin)
admin.site.register(CustomerProfile, CustomerProfileAdmin)
