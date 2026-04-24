from django.shortcuts import render
from products.models import Category, Product

def home(request):
    categories = Category.objects.all()
    products = Product.objects.filter(is_active=True).order_by('-created_at')
    context = {
        'categories': categories,
        'products': products,
    }
    return render(request, 'core/home.html', context)
