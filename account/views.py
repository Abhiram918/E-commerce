import re
import json
from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Sum, Count, Q
import requests
import random
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegistrationForm, CustomAuthenticationForm, SellerRegistrationForm
from .models import SellerProfile, CustomerProfile, Wishlist, Address
from products.models import Product
from orders.models import Order, OrderItem
from reviews.models import Review
from payments.models import Payment
from django.contrib.auth import get_user_model

User = get_user_model()

def logout_view(request):
    logout(request)
    return redirect('account:login')

@login_required
def profile_view(request):
    if request.user.role == 'ADMIN':
        return redirect('account:admin_dashboard')

    if request.user.role == 'SELLER':
        seller = request.user

        # ── All seller order items (evaluate once) ────────────────────
        seller_items_qs = OrderItem.objects.filter(seller=seller).select_related('order', 'product')
        seller_items = list(seller_items_qs)

        # ── Summary stats ─────────────────────────────────────────────
        total_revenue = sum(i.quantity * i.price for i in seller_items)
        total_units = sum(i.quantity for i in seller_items)

        # Order-level stats for this seller
        seller_order_ids = list(seller_items_qs.values_list('order_id', flat=True).distinct())
        total_orders = len(set(seller_order_ids))

        from orders.models import Order as _Order
        unshipped = _Order.objects.filter(
            id__in=seller_order_ids,
            status__in=['PENDING', 'CONFIRMED']
        ).count()
        pending = _Order.objects.filter(
            id__in=seller_order_ids,
            status='PENDING'
        ).count()
        returns = _Order.objects.filter(
            id__in=seller_order_ids,
            status='RETURNED'
        ).count()
        delivered = _Order.objects.filter(
            id__in=seller_order_ids,
            status='DELIVERED'
        ).count()

        # ── Low-stock products (stock <= 10) ──────────────────────────
        from products.models import Product as _Product
        low_stock_products = _Product.objects.filter(
            seller=seller, is_active=True, stock__lte=10
        ).order_by('stock')[:5]

        critical_stock_count = _Product.objects.filter(
            seller=seller, is_active=True, stock__lte=5
        ).count()

        # ── Daily sales (last 7 days) for chart ───────────────────────
        today = date.today()
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        chart_labels = [d.strftime('%b %d') for d in days]

        daily_sales = []
        for d in days:
            day_revenue = float(sum(
                i.quantity * i.price
                for i in seller_items
                if i.order.created_at.date() == d
            ))
            daily_sales.append(day_revenue)

        # (top products not displayed on dashboard, skipped)

        # ── Recent orders ─────────────────────────────────────────────
        recent_orders = _Order.objects.filter(
            id__in=seller_order_ids
        ).order_by('-created_at')[:5]

        # Pack chart data as JSON for the template
        chart_data = {
            'labels': chart_labels,
            'sales': daily_sales,
        }

        context = {
            'total_revenue': total_revenue,
            'total_units': total_units,
            'total_orders': total_orders,
            'unshipped': unshipped,
            'pending': pending,
            'returns': returns,
            'delivered': delivered,
            'low_stock_products': low_stock_products,
            'critical_stock_count': critical_stock_count,
            'chart_data_json': json.dumps(chart_data),
            'recent_orders': recent_orders,
        }
        return render(request, 'account/seller_dashboard.html', context)

    profile = CustomerProfile.objects.filter(user=request.user).first()
    return render(request, 'account/profile.html', {'profile': profile})

@login_required
def orders_view(request):
    status_filter = request.GET.get('filter', 'all')
    sort_by = request.GET.get('sort', 'latest')

    if sort_by == 'oldest':
        order_by_param = 'created_at'
    else:
        order_by_param = '-created_at'

    if request.user.role == 'SELLER':
        orders = Order.objects.filter(items__seller=request.user).distinct()
    else:
        orders = Order.objects.filter(user=request.user)

    if status_filter == 'active':
        orders = orders.exclude(status__in=['CANCELLED', 'DELIVERED', 'RETURNED'])
    elif status_filter == 'cancelled':
        orders = orders.filter(status='CANCELLED')
    elif status_filter == 'returned':
        orders = orders.filter(status='RETURNED')

    orders = orders.order_by(order_by_param)

    context = {
        'orders': orders,
        'current_filter': status_filter,
        'current_sort': sort_by,
    }
    return render(request, 'account/orders.html', context)

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            role = form.cleaned_data.get('role')
            if role == 'SELLER':
                SellerProfile.objects.create(
                    user=user, 
                    store_name=f"{user.first_name}'s Store"
                )
                messages.info(request, "Registration successful! Your seller account is pending admin approval.")
            elif role == 'CUSTOMER':
                CustomerProfile.objects.create(user=user)
                messages.success(request, "Registration successful! You can now log in.")
            
            return redirect('account:login')
    else:
        form = UserRegistrationForm()
    return render(request, 'account/register.html', {'form': form})

@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    return render(request, 'account/wishlist.html', {'wishlist_items': wishlist_items})

@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    Wishlist.objects.get_or_create(user=request.user, product=product)
    messages.success(request, f"{product.name} has been added to your wishlist.")
    return redirect(request.META.get('HTTP_REFERER', 'core:home'))

@login_required
def remove_from_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    Wishlist.objects.filter(user=request.user, product=product).delete()
    messages.success(request, f"{product.name} has been removed from your wishlist.")
    return redirect(request.META.get('HTTP_REFERER', 'account:wishlist'))

@login_required
def address_book_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save':
            full_name = request.POST.get('full_name', '')
            mobile = request.POST.get('mobile_number', '')
            pincode = request.POST.get('pincode', '')
            state = request.POST.get('state', '')
            address_line = request.POST.get('address_line', '')
            landmark = request.POST.get('landmark', '')
            town_city = request.POST.get('town_city', '')
            address_type = request.POST.get('address_type', 'HOME').upper()
            is_default = request.POST.get('is_default') == 'on'
            
            Address.objects.create(
                user=request.user,
                full_name=full_name,
                mobile_number=mobile,
                pincode=pincode,
                state=state,
                address_line=address_line,
                landmark=landmark,
                town_city=town_city,
                address_type=address_type,
                is_default=is_default
            )
            messages.success(request, 'Address saved successfully.')
        elif action == 'remove':
            address_id = request.POST.get('address_id')
            if address_id:
                Address.objects.filter(id=address_id, user=request.user).delete()
                messages.success(request, 'Address removed.')
        elif action == 'set_default':
            address_id = request.POST.get('address_id')
            if address_id:
                address = Address.objects.filter(id=address_id, user=request.user).first()
                if address:
                    address.is_default = True
                    address.save()
                    messages.success(request, 'Default address updated.')
        return redirect('account:address_book')

    addresses = Address.objects.filter(user=request.user).order_by('-is_default', '-id')
    return render(request, 'account/address_book.html', {'addresses': addresses})


@login_required
def settings_view(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.phone = request.POST.get('phone', '')
        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('account:settings')

    return render(request, 'account/settings.html')

@login_required
def reviews_view(request):
    reviews = Review.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'account/reviews.html', {'reviews': reviews})

@login_required
def write_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        image = request.FILES.get('image')
        
        if not image:
            messages.error(request, "A photo of the product is mandatory to submit a review.")
            return redirect('account:write_review', product_id=product_id)
            
        if not rating:
            messages.error(request, "Please provide a rating.")
            return redirect('account:write_review', product_id=product_id)
            
        Review.objects.update_or_create(
            product=product,
            user=request.user,
            defaults={
                'rating': rating,
                'comment': comment,
                'image': image
            }
        )
        messages.success(request, 'Review submitted successfully!')
        return redirect('account:reviews')
        
    return render(request, 'account/write_review.html', {'product': product})

@login_required
def edit_review(request, review_id):
    review = get_object_or_404(Review, id=review_id, user=request.user)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        image = request.FILES.get('image')
        
        if not rating:
            messages.error(request, "Please provide a rating.")
            return redirect('account:edit_review', review_id=review_id)
            
        review.rating = rating
        review.comment = comment
        if image:
            review.image = image
            
        review.save()
        messages.success(request, 'Review updated successfully!')
        return redirect('account:reviews')
        
    return render(request, 'account/edit_review.html', {'review': review, 'product': review.product})

def seller_register(request):
    if request.method == 'POST':
        form = SellerRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            # Create User
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                phone=form.cleaned_data.get('phone', ''),
                role='SELLER'
            )
            
            # Create SellerProfile
            SellerProfile.objects.create(
                user=user,
                store_name=form.cleaned_data['store_name'],
                store_slug=form.cleaned_data['store_slug'],
                store_logo=form.cleaned_data.get('store_logo'),
                gstin=form.cleaned_data['gstin'],
                pan=form.cleaned_data['pan'],
                bank_ifsc=form.cleaned_data['bank_ifsc'],
                account_no=form.cleaned_data['account_no'],
                office_address=form.cleaned_data['office_address'],
                is_approved=False
            )
            
            messages.info(request, "Registration successful! Your seller account is pending admin approval.")
            return redirect('account:login')
    else:
        form = SellerRegistrationForm()
        
    return render(request, 'account/seller_register.html', {'form': form})

def get_bank_details(request):
    ifsc = request.GET.get("ifsc", "").upper()

    if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc):
        return JsonResponse({"valid": False})

    try:
        res = requests.get(f"https://ifsc.razorpay.com/{ifsc}", timeout=3)
        if res.status_code == 200:
            data = res.json()
            return JsonResponse({
                "valid": True,
                "bank": data.get("BANK"),
                "branch": data.get("BRANCH"),
                "city": data.get("CITY"),
            })
    except requests.RequestException:
        pass

    return JsonResponse({"valid": False})

def get_pincode_details(request):
    pincode = request.GET.get("pincode", "")

    if not pincode.isdigit() or len(pincode) != 6:
        return JsonResponse({"valid": False})

    try:
        res = requests.get(
            f"https://api.postalpincode.in/pincode/{pincode}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=5
        )
        data = res.json()
        if data[0].get("Status") == "Success":
            post_office = data[0]["PostOffice"][0]
            return JsonResponse({
                "valid": True,
                "post_office": post_office.get("Name"),
                "district": post_office.get("District"),
                "state": post_office.get("State"),
            })
    except Exception:
        pass

    return JsonResponse({"valid": False})

def request_otp(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No user found with this email.")
            return redirect('account:request_otp')
        
        otp = str(random.randint(100000, 999999))
        request.session['reset_otp'] = otp
        request.session['reset_email'] = email
        
        try:
            send_mail(
                'Your Password Reset OTP',
                f'Your OTP for password reset is {otp}. Please enter it carefully.',
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
            messages.success(request, "An OTP has been sent to your email.")
        except Exception as e:
            messages.error(request, f"Failed to send email. Please check your config. Error: {e}")
            
        return redirect('account:verify_otp')
    return render(request, 'account/request_otp.html')

def verify_otp(request):
    if request.method == 'POST':
        otp = request.POST.get('otp')
        if otp == request.session.get('reset_otp'):
            request.session['otp_verified'] = True
            messages.success(request, "OTP verified successfully. You can now reset your password.")
            return redirect('account:reset_password')
        else:
            messages.error(request, "Invalid OTP. Please try again.")
    return render(request, 'account/verify_otp.html')

def reset_password(request):
    if not request.session.get('otp_verified'):
        messages.error(request, "Please verify your OTP first.")
        return redirect('account:request_otp')
        
    if request.method == 'POST':
        # FIXED: Added .strip() to prevent invisible spaces from being saved as part of the password
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        if new_password and new_password == confirm_password:
            email = request.session.get('reset_email')
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()
            
            request.session.pop('reset_otp', None)
            request.session.pop('reset_email', None)
            request.session.pop('otp_verified', None)
            
            messages.success(request, "Password has been successfully changed! Please login.")
            return redirect('account:login')
        else:
            messages.error(request, "Passwords do not match or are empty.")
            
    return render(request, 'account/reset_password.html')


@login_required
def admin_dashboard(request):
    """Platform-wide Admin Dashboard – only accessible to ADMIN role users."""
    if request.user.role != 'ADMIN':
        return redirect('account:profile')

    from datetime import date, timedelta
    from django.db.models import Sum, Count, Q

    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    seven_days_ago = today - timedelta(days=7)

    # ── User Stats ──────────────────────────────────────────────────────────
    total_users = User.objects.count()
    total_customers = User.objects.filter(role='CUSTOMER').count()
    total_sellers = User.objects.filter(role='SELLER').count()
    pending_sellers = SellerProfile.objects.filter(is_approved=False).count()
    new_users_30d = User.objects.filter(date_joined__date__gte=thirty_days_ago).count()

    # ── Order Stats ─────────────────────────────────────────────────────────
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='PENDING').count()
    confirmed_orders = Order.objects.filter(status='CONFIRMED').count()
    shipped_orders = Order.objects.filter(status='SHIPPED').count()
    delivered_orders = Order.objects.filter(status='DELIVERED').count()
    cancelled_orders = Order.objects.filter(status='CANCELLED').count()
    returned_orders = Order.objects.filter(status='RETURNED').count()
    orders_30d = Order.objects.filter(created_at__date__gte=thirty_days_ago).count()

    # ── Revenue Stats ────────────────────────────────────────────────────────
    total_revenue_data = Order.objects.filter(status='DELIVERED').aggregate(total=Sum('total_amount'))
    total_revenue = total_revenue_data['total'] or 0
    revenue_30d_data = Order.objects.filter(
        status='DELIVERED', created_at__date__gte=thirty_days_ago
    ).aggregate(total=Sum('total_amount'))
    revenue_30d = revenue_30d_data['total'] or 0

    # ── Product Stats ────────────────────────────────────────────────────────
    from products.models import Product as _Product, Category
    total_products = _Product.objects.count()
    active_products = _Product.objects.filter(is_active=True).count()
    out_of_stock = _Product.objects.filter(stock=0, is_active=True).count()
    total_categories = Category.objects.count()

    # ── Review Stats ─────────────────────────────────────────────────────────
    from reviews.models import Review as _Review
    total_reviews = _Review.objects.count()
    recent_reviews = _Review.objects.select_related('user', 'product').order_by('-created_at')[:5]

    # ── Recent Orders ────────────────────────────────────────────────────────
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:8]

    # ── Recent Users ─────────────────────────────────────────────────────────
    recent_users = User.objects.order_by('-date_joined')[:5]

    # ── Pending Seller Approvals ─────────────────────────────────────────────
    pending_seller_profiles = SellerProfile.objects.filter(
        is_approved=False
    ).select_related('user').order_by('-id')[:5]

    # ── Daily Orders chart (last 7 days) ─────────────────────────────────────
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    chart_labels = [d.strftime('%b %d') for d in days]
    daily_orders = []
    daily_revenue = []
    for d in days:
        day_orders = Order.objects.filter(created_at__date=d).count()
        day_rev_data = Order.objects.filter(
            created_at__date=d, status='DELIVERED'
        ).aggregate(total=Sum('total_amount'))
        daily_orders.append(day_orders)
        daily_revenue.append(float(day_rev_data['total'] or 0))

    chart_data = {
        'labels': chart_labels,
        'orders': daily_orders,
        'revenue': daily_revenue,
    }

    # ── Top Sellers ─────────────────────────────────────────────────────────
    top_sellers = User.objects.filter(role='SELLER').annotate(
        order_count=Count('orderitem__order', distinct=True),
        revenue=Sum('orderitem__price')
    ).order_by('-revenue')[:5]

    context = {
        # User stats
        'total_users': total_users,
        'total_customers': total_customers,
        'total_sellers': total_sellers,
        'pending_sellers': pending_sellers,
        'new_users_30d': new_users_30d,
        # Order stats
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'cancelled_orders': cancelled_orders,
        'returned_orders': returned_orders,
        'orders_30d': orders_30d,
        # Revenue
        'total_revenue': total_revenue,
        'revenue_30d': revenue_30d,
        # Products
        'total_products': total_products,
        'active_products': active_products,
        'out_of_stock': out_of_stock,
        'total_categories': total_categories,
        # Reviews
        'total_reviews': total_reviews,
        'recent_reviews': recent_reviews,
        # Recent data
        'recent_orders': recent_orders,
        'recent_users': recent_users,
        'pending_seller_profiles': pending_seller_profiles,
        # Chart
        'chart_data_json': json.dumps(chart_data),
        # Top sellers
        'top_sellers': top_sellers,
    }
    return render(request, 'account/admin_dashboard.html', context)


@login_required
def approve_seller(request, seller_id):
    """Approve a pending seller (admin only)."""
    if request.user.role != 'ADMIN':
        return redirect('account:profile')
    profile = get_object_or_404(SellerProfile, id=seller_id)
    profile.is_approved = True
    profile.save()
    messages.success(request, f"Seller '{profile.store_name}' has been approved.")
    return redirect('account:admin_dashboard')


@login_required
def update_order_status(request, order_id):
    """Update an order's status (admin only)."""
    if request.user.role != 'ADMIN':
        return redirect('account:profile')
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = [s[0] for s in Order.STATUS_CHOICES]
        if new_status in valid_statuses:
            order.status = new_status
            order.save()
            messages.success(request, f"Order {order.order_id} status updated to {new_status}.")
    return redirect('account:admin_dashboard')


@login_required
def seller_payments(request):
    """Seller Payment Dashboard – shows payment details for all sold products."""
    if request.user.role != 'SELLER':
        return redirect('account:profile')

    # All order items that belong to this seller
    seller_items = OrderItem.objects.filter(
        seller=request.user
    ).select_related('order', 'product', 'order__user').order_by('-order__created_at')

    # Payment records linked to those orders
    order_ids = seller_items.values_list('order_id', flat=True).distinct()
    payments = Payment.objects.filter(order_id__in=order_ids).select_related('order')
    payment_map = {p.order_id: p for p in payments}

    # Build per-order payment rows
    rows = []
    seen_orders = set()
    for item in seller_items:
        order = item.order
        if order.id in seen_orders:
            continue
        seen_orders.add(order.id)

        # Items for this seller in this order
        items_in_order = seller_items.filter(order=order)
        gross = sum(i.total_price for i in items_in_order)

        try:
            commission_rate = request.user.sellerprofile.commission_rate
        except Exception:
            commission_rate = 10

        commission = round(gross * commission_rate / 100, 2)
        net = round(gross - commission, 2)

        payment = payment_map.get(order.id)
        payment_status = payment.status if payment else ('SUCCESS' if order.payment_method == 'COD' else 'PENDING')
        transaction_id = payment.transaction_id if payment else '—'
        payment_method = payment.payment_method if payment else order.payment_method

        rows.append({
            'order': order,
            'items': list(items_in_order),
            'gross': gross,
            'commission': commission,
            'net': net,
            'payment_status': payment_status,
            'transaction_id': transaction_id,
            'payment_method': payment_method,
        })

    # Summary stats
    total_gross = sum(r['gross'] for r in rows)
    total_commission = sum(r['commission'] for r in rows)
    total_net = sum(r['net'] for r in rows)
    total_orders = len(rows)
    paid_count = sum(1 for r in rows if r['payment_status'] == 'SUCCESS')
    pending_count = total_orders - paid_count

    context = {
        'rows': rows,
        'total_gross': total_gross,
        'total_commission': total_commission,
        'total_net': total_net,
        'total_orders': total_orders,
        'paid_count': paid_count,
        'pending_count': pending_count,
    }
    return render(request, 'account/seller_payments.html', context)