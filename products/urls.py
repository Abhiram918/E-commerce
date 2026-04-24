from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [

    path('', views.product_list, name='product_list'),
    path('category/<slug:slug>/', views.category_products, name='category_products'),
    path('category/<slug:slug>/<slug:sub_slug>/', views.subcategory_products, name='subcategory_products'),

    # Seller inventory management
    path('seller/my-products/', views.seller_products, name='seller_products'),
    path('seller/add/', views.add_product, name='add_product'),
    path('seller/edit/<int:id>/', views.edit_product, name='edit_product'),
    path('seller/delete/<int:id>/', views.delete_product, name='delete_product'),
    path('seller/toggle/<int:id>/', views.toggle_product_visibility, name='toggle_product_visibility'),
    path('seller/quantity/<int:id>/', views.update_product_quantity, name='update_product_quantity'),

    # Admin
    path("admin/add/", views.admin_add_product, name="admin_add_product"),

    # This must come LAST to avoid catching seller/* routes
    path('<slug:slug>/', views.product_detail, name='product_detail'),
]