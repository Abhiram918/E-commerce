from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.utils.text import slugify
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from account.models import User
from .models import Product, Category, SubCategory, ProductImage
from django.db.models import Q

def get_price_ranges(category=None):
    if category and category.name.lower() == 'furniture':
        return [
            {'label': 'Below $1000', 'min': '', 'max': '1000'},
            {'label': '$1000 - $4000', 'min': '1000', 'max': '4000'},
            {'label': '$4000 - $7000', 'min': '4000', 'max': '7000'},
            {'label': '$7000 - $10000', 'min': '7000', 'max': '10000'},
            {'label': 'Above $10000', 'min': '10000', 'max': ''},
        ]
    else:
        return [
            {'label': 'Below $100', 'min': '', 'max': '100'},
            {'label': '$100 - $200', 'min': '100', 'max': '200'},
            {'label': '$200 - $400', 'min': '200', 'max': '400'},
            {'label': '$400 - $600', 'min': '400', 'max': '600'},
            {'label': '$600 - $800', 'min': '600', 'max': '800'},
            {'label': '$800 - $1000', 'min': '800', 'max': '1000'},
            {'label': 'Above $1000', 'min': '1000', 'max': ''},
        ]

def product_list(request):
    products = Product.objects.filter(is_active=True)
    
    search_query = request.GET.get('q', '').strip()
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query)
        ).distinct()

    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')

    if min_price:
        try:
            products = products.filter(price__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            products = products.filter(price__lte=float(max_price))
        except ValueError:
            pass

    wishlist_product_ids = []
    if request.user.is_authenticated:
        from account.models import Wishlist
        wishlist_product_ids = list(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))
        
    categories = Category.objects.prefetch_related('subcategories').all()
    context = {
        'products': products,
        'categories': categories,
        'min_price': min_price,
        'max_price': max_price,
        'price_ranges': get_price_ranges(),
        'wishlist_product_ids': wishlist_product_ids,
        'search_query': search_query,
    }
    return render(request, 'products/product_list.html', context)

def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(category=category, is_active=True)
    
    search_query = request.GET.get('q', '').strip()
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        ).distinct()

    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')

    if min_price:
        try:
            products = products.filter(price__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            products = products.filter(price__lte=float(max_price))
        except ValueError:
            pass

    wishlist_product_ids = []
    if request.user.is_authenticated:
        from account.models import Wishlist
        wishlist_product_ids = list(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))

    categories = Category.objects.prefetch_related('subcategories').all()
    context = {
        'category': category,
        'products': products,
        'categories': categories,
        'min_price': min_price,
        'max_price': max_price,
        'price_ranges': get_price_ranges(category),
        'wishlist_product_ids': wishlist_product_ids,
        'search_query': search_query,
    }
    return render(request, 'products/product_list.html', context)

def subcategory_products(request, slug, sub_slug):
    category = get_object_or_404(Category, slug=slug)
    subcategory = get_object_or_404(SubCategory, slug=sub_slug, category=category)
    products = Product.objects.filter(subcategory=subcategory, is_active=True)
    
    search_query = request.GET.get('q', '').strip()
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        ).distinct()

    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')

    if min_price:
        try:
            products = products.filter(price__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            products = products.filter(price__lte=float(max_price))
        except ValueError:
            pass

    wishlist_product_ids = []
    if request.user.is_authenticated:
        from account.models import Wishlist
        wishlist_product_ids = list(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))

    categories = Category.objects.prefetch_related('subcategories').all()
    context = {
        'category': category,
        'subcategory': subcategory,
        'products': products,
        'categories': categories,
        'min_price': min_price,
        'max_price': max_price,
        'price_ranges': get_price_ranges(category),
        'wishlist_product_ids': wishlist_product_ids,
        'search_query': search_query,
    }
    return render(request, 'products/product_list.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    context = {
        'product': product,
    }
    return render(request, 'products/product_detail.html', context)

# ===========================
# SELLER: INVENTORY (list)
# ===========================
@login_required
def seller_products(request):
    if not hasattr(request.user, 'role') or request.user.role != 'SELLER':
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('core:home')

    products = Product.objects.filter(seller=request.user).order_by('-created_at')
    total = products.count()
    active = products.filter(is_active=True).count()
    hidden = products.filter(is_active=False).count()
    low_stock = products.filter(stock__lte=5).count()

    context = {
        'products': products,
        'total': total,
        'active': active,
        'hidden': hidden,
        'low_stock': low_stock,
    }
    return render(request, 'products/seller_inventory.html', context)


# ===========================
# SELLER: ADD PRODUCT
# ===========================
@login_required
def add_product(request):
    if not hasattr(request.user, 'role') or request.user.role != 'SELLER':
        messages.error(request, 'Access denied.')
        return redirect('core:home')

    categories = Category.objects.prefetch_related('subcategories').all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '').strip()
        discounted_price = request.POST.get('discounted_price', '').strip() or None
        stock = request.POST.get('stock', '0').strip()
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory') or None
        is_active = request.POST.get('is_active') == 'on'

        if not name or not price or not category_id:
            messages.error(request, 'Product name, price, and category are required.')
            return render(request, 'products/seller_add_product.html', {'categories': categories})

        category = get_object_or_404(Category, id=category_id)
        subcategory = None
        if subcategory_id:
            subcategory = get_object_or_404(SubCategory, id=subcategory_id, category=category)

        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while Product.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        product = Product.objects.create(
            seller=request.user,
            category=category,
            subcategory=subcategory,
            name=name,
            slug=slug,
            description=description,
            price=price,
            discounted_price=discounted_price,
            stock=int(stock) if stock.isdigit() else 0,
            is_active=is_active,
        )

        images = request.FILES.getlist('images')
        for img in images:
            ProductImage.objects.create(product=product, image=img)

        messages.success(request, f'Product "{name}" added successfully!')
        return redirect('products:seller_products')

    return render(request, 'products/seller_add_product.html', {'categories': categories})


# ===========================
# SELLER: EDIT PRODUCT
# ===========================
@login_required
def edit_product(request, id):
    if not hasattr(request.user, 'role') or request.user.role != 'SELLER':
        messages.error(request, 'Access denied.')
        return redirect('core:home')

    product = get_object_or_404(Product, id=id, seller=request.user)
    categories = Category.objects.prefetch_related('subcategories').all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '').strip()
        discounted_price = request.POST.get('discounted_price', '').strip() or None
        stock = request.POST.get('stock', '0').strip()
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory') or None
        is_active = request.POST.get('is_active') == 'on'

        if not name or not price or not category_id:
            messages.error(request, 'Product name, price, and category are required.')
        else:
            category = get_object_or_404(Category, id=category_id)
            subcategory = None
            if subcategory_id:
                subcategory = get_object_or_404(SubCategory, id=subcategory_id, category=category)

            # Regenerate slug only if name changed
            if product.name != name:
                base_slug = slugify(name)
                slug = base_slug
                counter = 1
                while Product.objects.filter(slug=slug).exclude(id=product.id).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                product.slug = slug

            product.name = name
            product.description = description
            product.price = price
            product.discounted_price = discounted_price
            product.stock = int(stock) if stock.isdigit() else 0
            product.category = category
            product.subcategory = subcategory
            product.is_active = is_active
            product.save()

            # Handle new images
            images = request.FILES.getlist('images')
            for img in images:
                ProductImage.objects.create(product=product, image=img)

            # Handle image deletions
            delete_image_ids = request.POST.getlist('delete_images')
            if delete_image_ids:
                ProductImage.objects.filter(id__in=delete_image_ids, product=product).delete()

            messages.success(request, f'Product "{name}" updated successfully!')
            return redirect('products:seller_products')

    context = {
        'product': product,
        'categories': categories,
    }
    return render(request, 'products/seller_add_product.html', context)


# ===========================
# SELLER: DELETE PRODUCT
# ===========================
@login_required
@require_POST
def delete_product(request, id):
    if not hasattr(request.user, 'role') or request.user.role != 'SELLER':
        messages.error(request, 'Access denied.')
        return redirect('core:home')

    product = get_object_or_404(Product, id=id, seller=request.user)
    name = product.name
    product.delete()
    messages.success(request, f'Product "{name}" has been deleted.')
    return redirect('products:seller_products')


# ===========================
# SELLER: TOGGLE VISIBILITY
# ===========================
@login_required
@require_POST
def toggle_product_visibility(request, id):
    if not hasattr(request.user, 'role') or request.user.role != 'SELLER':
        return JsonResponse({'error': 'Access denied.'}, status=403)

    product = get_object_or_404(Product, id=id, seller=request.user)
    product.is_active = not product.is_active
    product.save()
    status = 'visible' if product.is_active else 'hidden'
    messages.success(request, f'"{product.name}" is now {status}.')
    return redirect('products:seller_products')


# ===========================
# SELLER: UPDATE QUANTITY
# ===========================
@login_required
@require_POST
def update_product_quantity(request, id):
    if not hasattr(request.user, 'role') or request.user.role != 'SELLER':
        return JsonResponse({'error': 'Access denied.'}, status=403)

    product = get_object_or_404(Product, id=id, seller=request.user)
    action = request.POST.get('action')  # 'set', 'add', 'subtract'
    qty_str = request.POST.get('quantity', '0').strip()

    try:
        qty = int(qty_str)
    except ValueError:
        messages.error(request, 'Invalid quantity value.')
        return redirect('products:seller_products')

    if action == 'set':
        product.stock = max(0, qty)
    elif action == 'add':
        product.stock += qty
    elif action == 'subtract':
        product.stock = max(0, product.stock - qty)
    else:
        product.stock = max(0, qty)

    product.save()
    messages.success(request, f'Stock for "{product.name}" updated to {product.stock}.')
    return redirect('products:seller_products')

# ===========================
# ADMIN ADD PRODUCT
# ===========================
@staff_member_required
def admin_add_product(request):
    categories = Category.objects.all()
    sellers = User.objects.filter(role="SELLER")

    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        price = request.POST.get("price")
        stock = request.POST.get("stock")
        category_id = request.POST.get("category")
        seller_id = request.POST.get("seller")

        category = get_object_or_404(Category, id=category_id)
        seller = get_object_or_404(User, id=seller_id)

        product = Product.objects.create(
            seller=seller,
            category=category,
            name=name,
            slug=slugify(name),
            description=description,
            price=price,
            stock=stock,
            is_active=True
        )

        # Multiple image upload
        images = request.FILES.getlist("images")
        for image in images:
            ProductImage.objects.create(product=product, image=image)

        messages.success(request, "Product added successfully by admin.")
        return redirect("products:product_list")

    context = {
        "categories": categories,
        "sellers": sellers,
    }

    return render(request, "products/admin_add_product.html", context)