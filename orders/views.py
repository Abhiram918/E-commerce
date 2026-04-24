from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Cart, CartItem, Order, OrderItem, ShippingAddress
from products.models import Product, Category


def cart_count(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        count = cart.items.count()
        return {'cart_count': count}
    return {'cart_count': 0}


def nav_categories(request):
    categories = Category.objects.prefetch_related('subcategories').all()
    return {'nav_categories': categories}

@login_required
def cart_view(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    items = cart.items.all()
    total = sum(item.product.selling_price * item.quantity for item in items)
    return render(request, 'orders/cart.html', {
        'cart': cart,
        'items': items,
        'total': total
    })

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_item, item_created = CartItem.objects.get_or_create(cart=cart, product=product)
    
    if not item_created:
        cart_item.quantity += 1
        cart_item.save()
        
    return redirect('orders:cart')

@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    return redirect('orders:cart')

@login_required
def update_cart(request, item_id):
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()
    return redirect('orders:cart')

from account.models import Address

@login_required
def checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    items = cart.items.all()
    if not items:
        return redirect('orders:cart')
    total = sum(item.product.selling_price * item.quantity for item in items)
    addresses = request.user.addresses.all()
    default_address = request.user.addresses.filter(is_default=True).first()
    return render(request, 'orders/checkout.html', {
        'cart': cart,
        'items': items,
        'total': total,
        'addresses': addresses,
        'default_address': default_address,
    })

@login_required
def place_order(request):
    if request.method == 'POST':
        cart = get_object_or_404(Cart, user=request.user)
        items = cart.items.all()
        if not items:
            return redirect('orders:cart')
        
        total = sum(item.product.selling_price * item.quantity for item in items)
        
        payment_method = request.POST.get('payment_method', 'COD')
        if payment_method not in ('COD', 'CARD'):
            payment_method = 'COD'
        
        order = Order.objects.create(
            user=request.user,
            total_amount=total,
            status='PENDING',
            payment_method=payment_method,
        )
        
        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                seller=item.product.seller,
                quantity=item.quantity,
                price=item.product.selling_price
            )
        
        address_id = request.POST.get('address_id')
        if address_id:
            user_address = get_object_or_404(Address, id=address_id, user=request.user)
            ShippingAddress.objects.create(
                order=order,
                full_name=user_address.full_name,
                address=f"{user_address.address_line}, {user_address.landmark}" if user_address.landmark else user_address.address_line,
                city=user_address.town_city,
                state=user_address.state,
                postal_code=user_address.pincode,
                country='India'  
            )
        else:
            ShippingAddress.objects.create(
                order=order,
                full_name=request.POST.get('full_name'),
                address=request.POST.get('address'),
                city=request.POST.get('city'),
                state=request.POST.get('state'),
                postal_code=request.POST.get('postal_code'),
                country=request.POST.get('country')
            )
        
        items.delete()
        
        return redirect('orders:order_success', order_id=order.id)
    return redirect('orders:checkout')

@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'orders/order_success.html', {'order': order})

@login_required
def track_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'orders/track_order.html', {'order': order})

@login_required
def update_order_status(request, order_id):
    if request.method == 'POST' and request.user.role == 'SELLER':
        order = get_object_or_404(Order, id=order_id, items__seller=request.user)
        status = request.POST.get('status')
        if status in dict(Order.STATUS_CHOICES):
            order.status = status
            order.save()
            messages.success(request, f"Order #{order.id} status updated to {dict(Order.STATUS_CHOICES)[status]}.")
        else:
            messages.error(request, "Invalid status selected.")
    return redirect(request.META.get('HTTP_REFERER', 'account:orders'))

@login_required
def cancel_order(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)
        if order.status in ['PENDING', 'CONFIRMED']:
            order.status = 'CANCELLED'
            order.save()
            messages.success(request, f"Order #{order.id} has been successfully cancelled.")
        else:
            messages.error(request, "This order cannot be cancelled as it has already been processed.")
    return redirect(request.META.get('HTTP_REFERER', 'account:orders'))

@login_required
def return_order(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)
        if order.status == 'DELIVERED':
            order.status = 'RETURNED'
            order.save()
            messages.success(request, f"Return request for Order #{order.id} has been submitted successfully.")
        else:
            messages.error(request, "This order cannot be returned.")
    return redirect(request.META.get('HTTP_REFERER', 'account:orders'))


@login_required
def invoice_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status not in ['DELIVERED', 'RETURNED']:
        messages.error(request, "Invoice is only available for delivered orders.")
        return redirect(request.META.get('HTTP_REFERER', 'account:orders'))
    return render(request, 'orders/invoice.html', {'order': order})
