from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Sum, Count, F, Q, DecimalField, Avg, DateField
from django.db.models.functions import Coalesce, TruncMonth, Cast
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import SensorReading, Product, Sale, ProductionBatch, Notification, EnvironmentSettings, UserProfile, Cart, CartItem, CustomerAdminMessage
from .email_service import send_verification_email, send_email_async, resend_verification_email
import json
from decimal import Decimal 
from django.utils import timezone
from datetime import timedelta, date
import time 
import pickle
import pandas as pd
import os
from django.conf import settings
from functools import wraps


# Helper function to merge session cart into user cart
def merge_session_cart_to_user(request, user):
    """Merge anonymous session cart into user's cart on login"""
    if not request.session.session_key:
        return
    
    try:
        # Get session cart
        session_cart = Cart.objects.get(session_key=request.session.session_key, user__isnull=True)
        
        # Get or create user cart
        user_cart, created = Cart.objects.get_or_create(
            user=user,
            defaults={'session_key': f'user_{user.id}_{user.username}'}
        )
        
        # Merge items
        for session_item in session_cart.items.all():
            user_item, created = CartItem.objects.get_or_create(
                cart=user_cart,
                product=session_item.product,
                defaults={'quantity_kg': session_item.quantity_kg}
            )
            
            if not created:
                # Update quantity if item already exists
                user_item.quantity_kg += session_item.quantity_kg
                user_item.save()
        
        # Delete session cart
        session_cart.delete()
    except Cart.DoesNotExist:
        pass


# Custom decorator for admin-only views
def admin_required(view_func):
    """Decorator to ensure only admin users can access certain views"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Check if user has admin role
        try:
            if not request.user.profile.is_admin:
                # Redirect customers to shop
                return redirect('shop')
        except UserProfile.DoesNotExist:
            # If no profile exists, redirect to shop
            return redirect('shop')
        
        return view_func(request, *args, **kwargs)
    return wrapper

# --- ML Prediction Function ---
def predict_yield(temperature=None, humidity=None, co2=None, growth_days=None):
    """
    Predicts mushroom yield using the trained ML model.
    If parameters are None, uses current sensor averages and estimates growth days.
    """
    try:
        # Get default values from current conditions if not provided
        if any(param is None for param in [temperature, humidity, co2]):
            latest = SensorReading.objects.order_by('-timestamp').first()

            if latest:
                latest_co2 = latest.co2_ppm if latest.co2_ppm is not None else latest.air_quality_ppm
                if temperature is None and latest.temperature is not None:
                    temperature = float(latest.temperature)
                if humidity is None and latest.humidity is not None:
                    humidity = float(latest.humidity)
                if co2 is None and latest_co2 is not None:
                    co2 = float(latest_co2)

            # Fill any still-missing fields from recent averages.
            if any(param is None for param in [temperature, humidity, co2]):
                recent_readings = list(SensorReading.objects.order_by('-timestamp')[:20])
                if recent_readings:
                    temperature_values = [float(r.temperature) for r in recent_readings if r.temperature is not None]
                    humidity_values = [float(r.humidity) for r in recent_readings if r.humidity is not None]
                    co2_values = [
                        float(r.co2_ppm if r.co2_ppm is not None else r.air_quality_ppm)
                        for r in recent_readings
                        if (r.co2_ppm is not None or r.air_quality_ppm is not None)
                    ]

                    if temperature is None:
                        temperature = (sum(temperature_values) / len(temperature_values)) if temperature_values else 23.0
                    if humidity is None:
                        humidity = (sum(humidity_values) / len(humidity_values)) if humidity_values else 85.0
                    if co2 is None:
                        co2 = (sum(co2_values) / len(co2_values)) if co2_values else 900
                else:
                    # Fallback to defaults if no sensor data exists.
                    temperature = temperature if temperature is not None else 23.0
                    humidity = humidity if humidity is not None else 85.0
                    co2 = co2 if co2 is not None else 900
        
        # Default growth days to optimal if not provided
        growth_days = growth_days or 33
        
        # Load the ML model
        model_path = os.path.join(settings.BASE_DIR, 'mushroom_yield_model.pkl')
        
        if not os.path.exists(model_path):
            return None  # Model not found
        
        with open(model_path, 'rb') as file:
            model = pickle.load(file)
        
        # Prepare input data
        input_data = pd.DataFrame({
            'temperature': [float(temperature)],
            'humidity': [float(humidity)],
            'co2_ppm': [int(co2)],
            'growth_days': [int(growth_days)]
        })
        
        # Make prediction
        prediction = model.predict(input_data)
        return round(float(prediction[0]), 2)
        
    except Exception as e:
        print(f"Prediction error: {e}")
        return None


def calculate_predicted_yield(start_date=None):
    """Calculate predicted yield using ML prediction."""
    parsed_start_date = None
    if isinstance(start_date, str) and start_date:
        parsed_start_date = date.fromisoformat(start_date)
    elif isinstance(start_date, date):
        parsed_start_date = start_date

    growth_days = None
    if parsed_start_date:
        elapsed_days = max((timezone.now().date() - parsed_start_date).days + 1, 1)
        # For newly-created batches, estimate yield at typical harvest maturity.
        growth_days = elapsed_days if elapsed_days > 1 else 33

    predicted = predict_yield(growth_days=growth_days)
    if predicted is None:
        return None

    return round(float(predicted), 2)


# --- NEW: Predictive Maintenance Function ---
def predict_preventive_action():
    """
    Uses ML to predict if preventive action should be taken.
    Returns dict with actions and confidence levels.
    """
    try:
        model_path = os.path.join(settings.BASE_DIR, 'predictive_maintenance_models.pkl')
        
        if not os.path.exists(model_path):
            return None  # Model not trained yet
        
        # Load models
        with open(model_path, 'rb') as f:
            models = pickle.load(f)
        
        # Get current sensor readings
        latest = SensorReading.objects.order_by('-timestamp').first()
        
        if not latest:
            return None
        
        # Prepare input
        input_data = pd.DataFrame({
            'hour_of_day': [latest.timestamp.hour],
            'temperature': [float(latest.temperature)],
            'humidity': [float(latest.humidity)],
            'co2': [latest.co2_ppm or 0]
        })
        
        # Get predictions and confidence
        pred_hum = models['humidifier'].predict(input_data)[0]
        conf_hum = max(models['humidifier'].predict_proba(input_data)[0]) * 100
        
        pred_vent = models['ventilation'].predict(input_data)[0]
        conf_vent = max(models['ventilation'].predict_proba(input_data)[0]) * 100
        
        pred_heat = models['heater'].predict(input_data)[0]
        conf_heat = max(models['heater'].predict_proba(input_data)[0]) * 100
        
        return {
            'activate_humidifier': bool(pred_hum),
            'activate_ventilation': bool(pred_vent),
            'activate_heater': bool(pred_heat),
            'confidence_humidifier': round(conf_hum, 1),
            'confidence_ventilation': round(conf_vent, 1),
            'confidence_heater': round(conf_heat, 1),
            'current_conditions': {
                'temperature': float(latest.temperature),
                'humidity': float(latest.humidity),
                'co2': latest.co2_ppm or 0
            }
        }
        
    except Exception as e:
        print(f"Predictive maintenance error: {e}")
        return None

# --- Page Views ---
@admin_required
def dashboard_view(request):
    return render(request, 'dashboard.html')

@admin_required
def environment_view(request):
    return render(request, 'environment.html')

@admin_required
def production_view(request):
    return render(request, 'production.html')

@admin_required
def inventory_view(request):
    return render(request, 'inventory.html')

@admin_required
def cooked_products_view(request):
    """Admin page for managing cooked/ready-to-eat mushroom products"""
    return render(request, 'cooked_products.html')

@admin_required
def analytics_view(request):
    return render(request, 'analytics.html')

@admin_required
def sales_report_view(request):
    """Comprehensive sales report for admin"""
    from .models import Order, StoreSettings
    from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, TruncYear
    from datetime import datetime, timedelta
    import json
    
    # Get filter parameters
    period = request.GET.get('period', 'daily')  # daily, weekly, monthly, annual
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Default date range (last 30 days for daily/weekly, 1 year for monthly/annual)
    today = timezone.now().date()
    if not end_date:
        end_date = today
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    if not start_date:
        if period in ['monthly', 'annual']:
            start_date = today - timedelta(days=365)
        else:
            start_date = today - timedelta(days=30)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    # Get all completed/delivered orders in date range
    orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        status__in=['DELIVERED', 'PROCESSING', 'SHIPPED', 'PAID']
    )
    
    # Total sales
    total_sales = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_orders = orders.count()
    
    # Average order value
    avg_order_value = total_sales / total_orders if total_orders > 0 else Decimal('0.00')
    
    # Sales by period
    if period == 'daily':
        sales_by_period = orders.annotate(
            period=TruncDate('created_at')
        ).values('period').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('period')
    elif period == 'weekly':
        sales_by_period = orders.annotate(
            period=TruncWeek('created_at')
        ).values('period').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('period')
    elif period == 'annual':
        sales_by_period = orders.annotate(
            period=TruncYear('created_at')
        ).values('period').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('period')
    else:  # monthly
        sales_by_period = orders.annotate(
            period=TruncMonth('created_at')
        ).values('period').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('period')
    
    # Convert to serializable format with proper date strings
    sales_by_period_list = []
    for item in sales_by_period:
        sales_by_period_list.append({
            'period': item['period'].strftime('%Y-%m-%d') if item['period'] else None,
            'total': str(item['total'] or 0),
            'count': item['count']
        })
    
    # Best selling products
    from .ecommerce_views import OrderItem
    best_sellers = OrderItem.objects.filter(
        order__created_at__date__gte=start_date,
        order__created_at__date__lte=end_date,
        order__status__in=['DELIVERED', 'PROCESSING', 'SHIPPED', 'PAID']
    ).values('product__name').annotate(
        total_qty=Sum('quantity_kg'),
        total_revenue=Sum('subtotal')
    ).order_by('-total_revenue')[:10]
    
    # Sales by payment method - normalize values first
    from django.db.models import Case, When, Value
    sales_by_payment = orders.annotate(
        normalized_payment=Case(
            When(payment_method='GCASH', then=Value('GCASH')),
            default=Value('COD'),  # Treat everything else as COD
            output_field=models.CharField()
        )
    ).values('normalized_payment').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Sales by payment method - serialize properly
    sales_by_payment_list = []
    for item in sales_by_payment:
        sales_by_payment_list.append({
            'payment_method': item['normalized_payment'],
            'total': str(item['total'] or 0),
            'count': item['count']
        })
    
    # Recent orders
    recent_orders = orders.order_by('-created_at')[:10]
    
    # Store settings for min order display
    store_settings = StoreSettings.load()
    
    context = {
        'total_sales': total_sales,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value,
        'sales_by_period': json.dumps(sales_by_period_list),
        'best_sellers': list(best_sellers),
        'sales_by_payment': json.dumps(sales_by_payment_list),
        'recent_orders': recent_orders,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'store_settings': store_settings,
    }
    return render(request, 'sales_report.html', context)

@admin_required
def sales_report_export(request):
    """Export sales report as CSV"""
    import csv
    from django.http import HttpResponse
    from .models import Order
    from datetime import datetime, timedelta
    
    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    today = timezone.now().date()
    if not end_date:
        end_date = today
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    if not start_date:
        start_date = today - timedelta(days=30)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        status__in=['DELIVERED', 'PROCESSING', 'SHIPPED', 'PAID']
    ).order_by('-created_at')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{start_date}_to_{end_date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Order Number', 'Date', 'Customer', 'Total Amount', 'Payment Method', 'Status'])
    
    for order in orders:
        writer.writerow([
            order.order_number,
            order.created_at.strftime('%Y-%m-%d %H:%M'),
            order.customer_name,
            float(order.total_amount),
            order.payment_method,
            order.status
        ])
    
    return response

@admin_required
def weather_view(request):
    return render(request, 'weather.html')

@admin_required
def notifications_view(request):
    return render(request, 'notifications.html')

@login_required(login_url='login')
def profile_view(request):
    # Check if user is admin or customer and render appropriate template
    try:
        if request.user.profile.is_admin:
            # Admin gets the dashboard profile page
            return render(request, 'profile.html')
        else:
            # Customer gets a simplified customer profile page
            from .models import Order, ProductReview
            orders = Order.objects.filter(
                customer_email=request.user.email
            ).prefetch_related('items__product').order_by('-created_at')
            
            # Get user's reviews with order IDs - track which (product, order) combinations have been reviewed
            user_reviews = ProductReview.objects.filter(user=request.user).values_list('product_id', 'order_id')
            # Create a set of "product_id-order_id" strings for easy lookup in template
            reviewed_items = set()
            for product_id, order_id in user_reviews:
                if order_id:
                    reviewed_items.add(f"{product_id}-{order_id}")

            pending_review_order_ids = set()
            for order in orders:
                if order.status != 'DELIVERED':
                    continue

                has_pending_review = False
                for item in order.items.all():
                    review_key = f"{item.product_id}-{order.id}"
                    if review_key not in reviewed_items:
                        has_pending_review = True
                        break

                if has_pending_review:
                    pending_review_order_ids.add(order.id)
            
            context = {
                'orders': orders,
                'reviewed_items': reviewed_items,
                'pending_review_order_ids': pending_review_order_ids,
            }
            return render(request, 'customer_profile.html', context)
    except UserProfile.DoesNotExist:
        # Default to customer profile
        from .models import Order
        orders = Order.objects.filter(customer_email=request.user.email).order_by('-created_at')
        context = {
            'orders': orders,
            'reviewed_items': set(),
            'pending_review_order_ids': set(),
        }
        return render(request, 'customer_profile.html', context)


@login_required(login_url='login')
def customer_order_tracking_api(request):
    from .models import Order, StoreSettings

    orders = Order.objects.filter(customer_email=request.user.email).order_by('-created_at')
    order_locations = []
    store_settings = StoreSettings.load()

    store_location = {
        'latitude': float(store_settings.store_latitude) if store_settings.store_latitude is not None else None,
        'longitude': float(store_settings.store_longitude) if store_settings.store_longitude is not None else None,
        'name': store_settings.store_name,
        'address': store_settings.store_address,
    }

    for order in orders:
        order_locations.append({
            'order_id': order.id,
            'order_number': order.order_number,
            'status': order.status,
            'current_location_status': order.current_location_status or '',
            'current_location_address': order.current_location_address or '',
            'current_latitude': float(order.current_latitude) if order.current_latitude is not None else None,
            'current_longitude': float(order.current_longitude) if order.current_longitude is not None else None,
            'customer_latitude': float(order.customer_latitude) if order.customer_latitude is not None else None,
            'customer_longitude': float(order.customer_longitude) if order.customer_longitude is not None else None,
            'location_updated_at': order.location_updated_at.strftime('%Y-%m-%d %H:%M:%S') if order.location_updated_at else None,
            'updated_at': order.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        })

    return JsonResponse({'orders': order_locations, 'store': store_location})


@login_required(login_url='login')
def customer_chat_api(request):
    """Customer chat endpoint for listing and sending messages to admins."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message_text = (data.get('message') or '').strip()
            if not message_text:
                return JsonResponse({'success': False, 'error': 'Message is required'}, status=400)

            CustomerAdminMessage.objects.create(
                customer=request.user,
                sender=request.user,
                message=message_text,
                is_read=False
            )
            return JsonResponse({'success': True, 'message': 'Message sent'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    messages_qs = CustomerAdminMessage.objects.filter(customer=request.user).select_related('sender').order_by('created_at')

    # Mark admin messages as read once customer fetches thread.
    CustomerAdminMessage.objects.filter(
        customer=request.user,
        sender__profile__role='ADMIN',
        is_read=False
    ).update(is_read=True)

    messages_list = []
    for msg in messages_qs:
        try:
            is_admin_sender = msg.sender.profile.is_admin
        except UserProfile.DoesNotExist:
            is_admin_sender = False

        messages_list.append({
            'id': msg.id,
            'message': msg.message,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M'),
            'sender_name': msg.sender.get_full_name() or msg.sender.username,
            'sender_role': 'ADMIN' if is_admin_sender else 'CUSTOMER',
            'is_mine': msg.sender_id == request.user.id,
        })
    return JsonResponse({'messages': messages_list})


@admin_required
def admin_chat_api(request):
    """Admin chat inbox endpoint for conversation list, thread fetch, and replies."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            message_text = (data.get('message') or '').strip()

            if not customer_id or not message_text:
                return JsonResponse({'success': False, 'error': 'customer_id and message are required'}, status=400)

            customer = User.objects.get(id=customer_id)
            CustomerAdminMessage.objects.create(
                customer=customer,
                sender=request.user,
                message=message_text,
                is_read=False
            )
            return JsonResponse({'success': True, 'message': 'Reply sent'})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Customer not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    customer_id = request.GET.get('customer_id')
    if customer_id:
        try:
            customer = User.objects.get(id=customer_id)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Customer not found'}, status=404)

        thread = CustomerAdminMessage.objects.filter(customer=customer).select_related('sender').order_by('created_at')

        # Mark unread customer messages as read when admin opens thread.
        CustomerAdminMessage.objects.filter(
            customer=customer,
            sender=customer,
            is_read=False
        ).update(is_read=True)

        messages_list = []
        for msg in thread:
            try:
                is_admin_sender = msg.sender.profile.is_admin
            except UserProfile.DoesNotExist:
                is_admin_sender = False

            messages_list.append({
                'id': msg.id,
                'message': msg.message,
                'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M'),
                'sender_name': msg.sender.get_full_name() or msg.sender.username,
                'is_admin': is_admin_sender,
            })
        return JsonResponse({
            'customer': {
                'id': customer.id,
                'name': customer.get_full_name() or customer.username,
                'email': customer.email,
            },
            'messages': messages_list,
        })

    # Conversation list grouped by customer
    customer_ids = CustomerAdminMessage.objects.values_list('customer_id', flat=True).distinct()
    conversations = []
    for cid in customer_ids:
        customer = User.objects.filter(id=cid).first()
        if not customer:
            continue

        latest = CustomerAdminMessage.objects.filter(customer_id=cid).order_by('-created_at').first()
        unread_count = CustomerAdminMessage.objects.filter(customer_id=cid, sender=customer, is_read=False).count()

        conversations.append({
            'customer_id': cid,
            'customer_name': customer.get_full_name() or customer.username,
            'customer_email': customer.email,
            'last_message': latest.message if latest else '',
            'last_time': latest.created_at.strftime('%Y-%m-%d %H:%M') if latest else '',
            'unread_count': unread_count,
        })

    conversations.sort(key=lambda c: c['last_time'], reverse=True)
    return JsonResponse({'conversations': conversations})

# --- Login / Logout Views ---
@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Check email verification for customers
            try:
                profile = user.profile
                if profile.is_customer and not profile.is_email_verified:
                    return JsonResponse({
                        'success': False, 
                        'error': 'Please verify your email address before logging in. Check your inbox for the verification link.',
                        'needs_verification': True,
                        'email': user.email
                    }, status=403)
            except UserProfile.DoesNotExist:
                pass
            
            login(request, user)
            
            # Merge session cart into user cart
            try:
                merge_session_cart_to_user(request, user)
            except Exception as e:
                # Don't fail login if cart merge fails
                print(f"Cart merge error: {e}")
            
            # Role-based redirect
            try:
                if user.profile.is_admin:
                    redirect_url = '/'  # Dashboard for admin
                else:
                    redirect_url = '/shop/'  # Shop for customers
            except UserProfile.DoesNotExist:
                # Default to shop if no profile
                redirect_url = '/shop/'
            
            return JsonResponse({'success': True, 'redirect_url': redirect_url})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid username or password'}, status=401)
    return render(request, 'login.html')


def register_view(request):
    """Customer registration view"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            confirm_password = data.get('confirm_password')
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            phone = data.get('phone', '')
            address = data.get('address', '')
            city = data.get('city', '')
            postal_code = data.get('postal_code', '')
            
            # Validation
            if not username or not email or not password:
                return JsonResponse({'success': False, 'error': 'Please fill in all required fields'}, status=400)
            
            if password != confirm_password:
                return JsonResponse({'success': False, 'error': 'Passwords do not match'}, status=400)
            
            if len(password) < 6:
                return JsonResponse({'success': False, 'error': 'Password must be at least 6 characters'}, status=400)
            
            # Check if username already exists
            if User.objects.filter(username=username).exists():
                return JsonResponse({'success': False, 'error': 'Username already exists'}, status=400)
            
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                return JsonResponse({'success': False, 'error': 'Email already exists'}, status=400)
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Update profile with additional info
            profile = user.profile
            profile.role = 'CUSTOMER'  # All registrations are customers
            profile.phone = phone
            profile.address = address
            profile.city = city
            profile.postal_code = postal_code
            profile.is_email_verified = False  # Require email verification
            profile.save()
            
            # Send verification email asynchronously (don't slow down registration)
            send_email_async(send_verification_email, user, request)
            
            # DO NOT auto-login - require email verification first
            return JsonResponse({
                'success': True, 
                'message': 'Registration successful! Please check your email to verify your account before logging in.',
                'redirect_url': '/login/',
                'requires_verification': True
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return render(request, 'register.html')


def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return JsonResponse({'success': True, 'redirect_url': '/login/'})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


def verify_email(request, token):
    """
    Email verification view - activates user account when they click the verification link.
    """
    try:
        profile = get_object_or_404(UserProfile, email_verification_token=token)
        
        # Check if token is expired (24 hours)
        if profile.email_verification_sent_at:
            token_age = timezone.now() - profile.email_verification_sent_at
            if token_age > timedelta(hours=24):
                return render(request, 'email_verification.html', {
                    'success': False,
                    'error': 'This verification link has expired. Please request a new one.',
                    'expired': True,
                    'email': profile.user.email
                })
        
        # Verify the email
        profile.is_email_verified = True
        profile.email_verification_token = None  # Clear the token
        profile.save()
        
        return render(request, 'email_verification.html', {
            'success': True,
            'message': 'Your email has been verified successfully! You can now log in.',
            'user': profile.user
        })
        
    except Exception as e:
        return render(request, 'email_verification.html', {
            'success': False,
            'error': 'Invalid verification link. Please try again or request a new verification email.'
        })


@csrf_exempt
def resend_verification(request):
    """
    Resend verification email to user.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            
            if not email:
                return JsonResponse({'success': False, 'error': 'Email is required'}, status=400)
            
            try:
                user = User.objects.get(email=email)
                profile = user.profile
                
                if profile.is_email_verified:
                    return JsonResponse({
                        'success': False, 
                        'error': 'This email is already verified. You can log in.'
                    }, status=400)
                
                # Check rate limiting (max 1 email per 2 minutes)
                if profile.email_verification_sent_at:
                    time_since_last = timezone.now() - profile.email_verification_sent_at
                    if time_since_last < timedelta(minutes=2):
                        remaining = 120 - time_since_last.seconds
                        return JsonResponse({
                            'success': False,
                            'error': f'Please wait {remaining} seconds before requesting another verification email.'
                        }, status=429)
                
                # Send verification email
                send_email_async(send_verification_email, user, request)
                
                return JsonResponse({
                    'success': True,
                    'message': 'Verification email sent! Please check your inbox.'
                })
                
            except User.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'No account found with this email address.'
                }, status=404)
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


# --- Store Settings Views ---
@admin_required
def store_settings_view(request):
    """Admin page for store settings including map location"""
    from .models import StoreSettings
    store_settings = StoreSettings.load()
    
    context = {
        'store_settings': store_settings,
    }
    return render(request, 'store_settings.html', context)


@admin_required
@require_http_methods(["GET", "POST", "PUT"])
def store_settings_api(request):
    """API endpoint for store settings"""
    from .models import StoreSettings
    
    store_settings = StoreSettings.load()
    
    if request.method == 'GET':
        return JsonResponse({
            'success': True,
            'store_name': store_settings.store_name,
            'store_address': store_settings.store_address,
            'store_latitude': float(store_settings.store_latitude) if store_settings.store_latitude else None,
            'store_longitude': float(store_settings.store_longitude) if store_settings.store_longitude else None,
            'minimum_base_fee': float(store_settings.minimum_base_fee),
            'minimum_base_distance_km': float(store_settings.minimum_base_distance_km),
            'fee_per_km': float(store_settings.fee_per_km),
            'free_shipping_threshold': float(store_settings.free_shipping_threshold),
            'max_delivery_distance_km': float(store_settings.max_delivery_distance_km),
            'minimum_order_amount': float(store_settings.minimum_order_amount),
        })
    
    elif request.method in ['POST', 'PUT']:
        try:
            data = json.loads(request.body)
            
            if 'store_name' in data:
                store_settings.store_name = data['store_name']
            if 'store_address' in data:
                store_settings.store_address = data['store_address']
            if 'store_latitude' in data and data['store_latitude'] is not None:
                store_settings.store_latitude = Decimal(str(data['store_latitude']))
            if 'store_longitude' in data and data['store_longitude'] is not None:
                store_settings.store_longitude = Decimal(str(data['store_longitude']))
            if 'minimum_base_fee' in data:
                store_settings.minimum_base_fee = Decimal(str(data['minimum_base_fee']))
            if 'minimum_base_distance_km' in data:
                store_settings.minimum_base_distance_km = Decimal(str(data['minimum_base_distance_km']))
            if 'fee_per_km' in data:
                store_settings.fee_per_km = Decimal(str(data['fee_per_km']))
            if 'free_shipping_threshold' in data:
                store_settings.free_shipping_threshold = Decimal(str(data['free_shipping_threshold']))
            if 'max_delivery_distance_km' in data:
                store_settings.max_delivery_distance_km = Decimal(str(data['max_delivery_distance_km']))
            if 'minimum_order_amount' in data:
                store_settings.minimum_order_amount = Decimal(str(data['minimum_order_amount']))
            
            store_settings.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Store settings saved successfully!'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


# --- API Views ---

@login_required(login_url='login')
def sensor_data_api(request):
    readings = SensorReading.objects.order_by('-timestamp')[:20]
    data = {
        'labels': [r.timestamp.strftime('%H:%M:%S') for r in reversed(readings)], 
        'humidity': [float(r.humidity) for r in reversed(readings)], 
        'temp': [float(r.temperature) for r in reversed(readings)], 
        'co2': [r.co2_ppm if r.co2_ppm else 0 for r in reversed(readings)],
        'air_quality': [r.air_quality_ppm if r.air_quality_ppm else 0 for r in reversed(readings)],
    }
    return JsonResponse(data)

@login_required(login_url='login')
def dashboard_summary_api(request):
    today = timezone.now()
    prod_summary = ProductionBatch.objects.aggregate(
        active_batches=Coalesce(Count('id', filter=Q(status__in=['GROWING', 'READY'])), 0)
    )
    month_yield = ProductionBatch.objects.filter(
        harvest_date__year=today.year,
        harvest_date__month=today.month
    ).aggregate(
        total_yield=Coalesce(Sum('yield_kg'), Decimal('0.0'), output_field=DecimalField())
    )
    notifications = Notification.objects.filter(is_read=False).order_by('-created_at')[:2]
    alert_list = []
    for n in notifications:
        alert_list.append({
            'level': n.level,
            'description': n.description
        })
    
    # Get latest sensor reading from DHT22 + MQ-135
    latest_sensor = SensorReading.objects.first()  # Already ordered by -timestamp
    
    if latest_sensor:
        temperature = float(latest_sensor.temperature)
        humidity = float(latest_sensor.humidity)
        # Use air quality as CO2 for display purposes (MQ-135 doesn't measure true CO2)
        air_quality_ppm = latest_sensor.air_quality_ppm if latest_sensor.air_quality_ppm else 0
        co2_ppm = air_quality_ppm  # Display air quality in CO2 card
    else:
        # Default values if no sensor data
        temperature = 0
        humidity = 0
        co2_ppm = 0
        air_quality_ppm = 0
    
    # --- DYNAMIC DEVICES ONLINE CALCULATION ---
    devices_online = 0
    total_devices = 8
    
    # Check if sensors are active (recent reading within last 5 minutes)
    recent_sensor = SensorReading.objects.filter(
        timestamp__gte=timezone.now() - timedelta(minutes=5)
    ).exists()
    sensors_online = recent_sensor
    if recent_sensor:
        devices_online += 3  # Temperature, Humidity, CO2 sensors
    
    # Check environment control systems
    env_settings = EnvironmentSettings.load()
    if env_settings.fan_on:
        devices_online += 1  # Fan/Ventilation
    if env_settings.humidifier_on:
        devices_online += 1  # Humidifier
    if env_settings.heater_on:
        devices_online += 1  # Heater
    if env_settings.co2_on:
        devices_online += 1  # CO2 system
    if env_settings.lights_on:
        devices_online += 1  # Lights
    
    # Determine system status
    if devices_online == total_devices:
        system_status = "active"
        status_message = "All sensors online"
    elif devices_online >= total_devices * 0.75:
        system_status = "warning"
        status_message = f"{devices_online}/{total_devices} devices active"
    else:
        system_status = "error"
        status_message = f"Only {devices_online}/{total_devices} devices online"
    
    # Individual device statuses for dashboard
    device_statuses = {
        'fan': env_settings.fan_on,
        'humidifier': env_settings.humidifier_on,
        'watering': False,  # Set to False by default, will be True only during watering cycle
        'sensors': sensors_online
    }
    
    data = {
        'active_batches': prod_summary['active_batches'],
        'this_month_yield': month_yield['total_yield'],
        'system_uptime': 99.8, # Simulated (could calculate from sensor uptime)
        'devices_online': f"{devices_online}/{total_devices}",
        'system_status': system_status,
        'status_message': status_message,
        'device_statuses': device_statuses,
        'alerts': alert_list,
        # Real sensor data from DHT22 + MQ-135
        'temperature': temperature,
        'humidity': humidity,
        'co2_ppm': co2_ppm,
        'air_quality_ppm': air_quality_ppm
    }
    return JsonResponse(data)


@login_required(login_url='login')
def inventory_api(request):
    if request.method == 'POST':
        try:
            # Handle multipart form data for file upload
            name = request.POST.get('name')
            batch_id = request.POST.get('batch_id', '')
            stock_kg = request.POST.get('stock_kg')
            price_per_kg = request.POST.get('price_per_kg', 0)
            description = request.POST.get('description', '')
            product_image = request.FILES.get('product_image')
            product_type = request.POST.get('product_type', 'fresh')
            is_active = request.POST.get('is_active', 'true').lower() == 'true'
            
            # Nutrition fields
            serving_size = request.POST.get('serving_size', '')
            calories = request.POST.get('calories') or None
            protein = request.POST.get('protein') or None
            carbohydrates = request.POST.get('carbohydrates') or None
            fat = request.POST.get('fat') or None
            fiber = request.POST.get('fiber') or None
            sodium = request.POST.get('sodium') or None
            
            # Create the product
            product = Product.objects.create(
                name=name,
                batch_id=batch_id,
                stock_kg=stock_kg,
                price_per_kg=price_per_kg,
                description=description,
                product_type=product_type,
                is_active=is_active,
                serving_size=serving_size,
                calories=calories,
                protein=protein,
                carbohydrates=carbohydrates,
                fat=fat,
                fiber=fiber,
                sodium=sodium
            )
            
            # If image is provided, create ProductImage
            if product_image:
                from .models import ProductImage
                ProductImage.objects.create(
                    product=product,
                    image=product_image,
                    is_primary=True
                )
            
            return JsonResponse({'success': True, 'message': 'Product added'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    # Filter by product_type if provided
    product_type_filter = request.GET.get('product_type')
    products = Product.objects.prefetch_related('images').all()
    if product_type_filter:
        products = products.filter(product_type=product_type_filter)
    
    def get_product_image_url(product):
        """Get primary image URL or first available image"""
        primary = product.images.filter(is_primary=True).first()
        if primary:
            return primary.image.url
        first_image = product.images.first()
        if first_image:
            return first_image.image.url
        return None
    
    product_list = [{'id': p.id, 'name': p.name, 'batch_id': p.batch_id, 'stock_kg': p.stock_kg, 
                     'price_per_kg': str(p.price_per_kg), 'description': p.description, 
                     'is_active': p.is_active, 'product_type': p.product_type,
                     'image_url': get_product_image_url(p),
                     'serving_size': p.serving_size or '',
                     'calories': str(p.calories) if p.calories else '',
                     'protein': str(p.protein) if p.protein else '',
                     'carbohydrates': str(p.carbohydrates) if p.carbohydrates else '',
                     'fat': str(p.fat) if p.fat else '',
                     'fiber': str(p.fiber) if p.fiber else '',
                     'sodium': str(p.sodium) if p.sodium else ''} for p in products]
    return JsonResponse(product_list, safe=False)

@login_required(login_url='login')
def inventory_api_detail(request, pk):
    try:
        product = Product.objects.get(pk=pk)
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Product not found'}, status=404)
    
    if request.method == 'GET':
        return JsonResponse({'id': product.id, 'name': product.name, 'batch_id': product.batch_id, 'stock_kg': product.stock_kg})
    
    elif request.method == 'POST':
        # Handle UPDATE with multipart form data for file upload
        try:
            product.name = request.POST.get('name', product.name)
            product.batch_id = request.POST.get('batch_id', product.batch_id)
            product.stock_kg = request.POST.get('stock_kg', product.stock_kg)
            product.price_per_kg = request.POST.get('price_per_kg', product.price_per_kg)
            product.description = request.POST.get('description', product.description)
            product.product_type = request.POST.get('product_type', product.product_type)
            
            is_active_str = request.POST.get('is_active')
            if is_active_str is not None:
                product.is_active = is_active_str.lower() == 'true'
            
            # Update nutrition fields
            if 'serving_size' in request.POST:
                product.serving_size = request.POST.get('serving_size') or ''
            if 'calories' in request.POST:
                product.calories = request.POST.get('calories') or None
            if 'protein' in request.POST:
                product.protein = request.POST.get('protein') or None
            if 'carbohydrates' in request.POST:
                product.carbohydrates = request.POST.get('carbohydrates') or None
            if 'fat' in request.POST:
                product.fat = request.POST.get('fat') or None
            if 'fiber' in request.POST:
                product.fiber = request.POST.get('fiber') or None
            if 'sodium' in request.POST:
                product.sodium = request.POST.get('sodium') or None
            
            product.save()
            
            # Handle image update if provided
            product_image = request.FILES.get('product_image')
            if product_image:
                from .models import ProductImage
                # Delete old primary image if exists
                ProductImage.objects.filter(product=product, is_primary=True).delete()
                # Create new primary image
                ProductImage.objects.create(
                    product=product,
                    image=product_image,
                    is_primary=True
                )
            
            return JsonResponse({'success': True, 'message': 'Product updated'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    elif request.method == 'DELETE':
        product.delete()
        return JsonResponse({'success': True, 'message': 'Product deleted'})

@admin_required
def toggle_product_publish(request, pk):
    """Toggle product publish status (is_active field)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)
    
    try:
        product = Product.objects.get(pk=pk)
        data = json.loads(request.body)
        is_active = data.get('is_active')
        
        if is_active is None:
            return JsonResponse({'success': False, 'error': 'is_active field required'}, status=400)
        
        product.is_active = is_active
        product.save()
        
        status_text = "published to shop" if is_active else "unpublished from shop"
        return JsonResponse({
            'success': True, 
            'message': f'{product.name} has been {status_text}',
            'is_active': product.is_active
        })
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required(login_url='login')
def sales_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_id = data.get('product_id')
            quantity_kg = Decimal(data.get('quantity_kg'))
            total_price = Decimal(data.get('total_price'))
            product = Product.objects.get(id=product_id)
            if product.stock_kg < quantity_kg:
                return JsonResponse({'success': False, 'error': 'Not enough stock to complete sale.'}, status=400)
            stock_before_sale = product.stock_kg
            stock_after_sale = stock_before_sale - quantity_kg
            if stock_after_sale < 10 and stock_before_sale >= 10:
                Notification.objects.create(title="Low Stock Alert", description=f"{product.name} inventory below minimum threshold ({stock_after_sale} kg).", category="production", level="warning")
            product.stock_kg = F('stock_kg') - quantity_kg
            product.save()
            Sale.objects.create(product=product, quantity_kg=quantity_kg, total_price=total_price, sale_date=timezone.now())
            return JsonResponse({'success': True, 'message': 'Sale recorded'})
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Product not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    sales = Sale.objects.order_by('-sale_date')
    sales_list = [
        {
            'id': s.id,
            'sale_date': s.sale_date.strftime('%Y-%m-%d %H:%M'),
            'product_name': s.product.name,
            'quantity_kg': s.quantity_kg,
            'total_price': s.total_price,
            'sale_type': s.sale_type,
        }
        for s in sales
    ]
    return JsonResponse(sales_list, safe=False)

@login_required(login_url='login')
def summary_api(request):
    inventory_summary = Product.objects.aggregate(total_stock=Coalesce(Sum('stock_kg'), Decimal('0.0'), output_field=DecimalField()), low_stock_items=Coalesce(Count('id', filter=Q(stock_kg__lt=10)), 0))
    sales_summary = Sale.objects.aggregate(total_revenue=Coalesce(Sum('total_price'), Decimal('0.0'), output_field=DecimalField()), total_sales=Coalesce(Count('id'), 0))
    return JsonResponse({'total_stock': inventory_summary['total_stock'], 'low_stock_items': inventory_summary['low_stock_items'], 'total_revenue': sales_summary['total_revenue'], 'total_sales': sales_summary['total_sales'],})

@login_required(login_url='login')
def production_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            product_id = data.get('product_id')
            if not product_id:
                return JsonResponse({'success': False, 'error': 'Product is required.'}, status=400)

            product = Product.objects.filter(id=product_id).first()
            if not product:
                return JsonResponse({'success': False, 'error': 'Selected product does not exist.'}, status=400)

            if product.product_type != 'fresh':
                return JsonResponse({'success': False, 'error': 'Only fresh products can be used for production batches.'}, status=400)

            predicted = calculate_predicted_yield(
                start_date=data.get('start_date')
            )

            ProductionBatch.objects.create(
                product=product,
                batch_number='',
                start_date=data.get('start_date'),
                status=data.get('status'),
                cost=data.get('cost') or None,
                predicted_yield_kg=predicted
            )
            return JsonResponse({'success': True, 'message': 'Batch added', 'predicted_yield': predicted})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    batches = ProductionBatch.objects.order_by('-start_date')
    batch_list = [
        {
            'id': batch.id,
            'batch_number': batch.batch_number,
            'product_name': batch.product.name if batch.product else 'N/A',
            'start_date': batch.start_date.strftime('%Y-%m-%d'),
            'harvest_date': batch.harvest_date.strftime('%Y-%m-%d') if batch.harvest_date else '-',
            'yield_kg': batch.yield_kg if batch.yield_kg is not None else '-',
            'predicted_yield_kg': batch.predicted_yield_kg if batch.predicted_yield_kg is not None else '-',
            'status': batch.get_status_display()
        }
        for batch in batches
    ]
    products = Product.objects.filter(product_type='fresh')
    product_list = [{'id': p.id, 'name': p.name} for p in products]
    
    return JsonResponse({
        'batches': batch_list,
        'products': product_list
    })


@login_required(login_url='login')
@require_http_methods(["POST"])
def production_predict_api(request):
    try:
        data = json.loads(request.body)
        predicted = calculate_predicted_yield(
            start_date=data.get('start_date')
        )
        return JsonResponse({'success': True, 'predicted_yield': predicted})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required(login_url='login')
def production_next_batch_number_api(request):
    try:
        start_date_raw = request.GET.get('start_date')
        parsed_start_date = date.fromisoformat(start_date_raw) if start_date_raw else timezone.now().date()
        batch_number = ProductionBatch.generate_batch_number(parsed_start_date)
        return JsonResponse({'success': True, 'batch_number': batch_number})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required(login_url='login')
@require_http_methods(["GET", "PUT", "DELETE"])
def production_api_detail(request, pk):
    try:
        batch = ProductionBatch.objects.get(pk=pk)
    except ProductionBatch.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Batch not found'}, status=404)
    
    if request.method == 'GET':
        return JsonResponse({
            'id': batch.id,
            'product_id': batch.product_id,
            'batch_number': batch.batch_number,
            'start_date': batch.start_date,
            'harvest_date': batch.harvest_date,
            'yield_kg': batch.yield_kg,
            'predicted_yield_kg': batch.predicted_yield_kg,
            'status': batch.status,
            'cost': batch.cost
        })
    
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            status_before = batch.status
            status_after = data.get('status', batch.status)
            
            # Check if status is changing to READY
            if status_after == 'READY' and status_before != 'READY':
                Notification.objects.create(
                    title="Batch Ready for Harvest", 
                    description=f"Batch {data.get('batch_number')} is ready for harvest.", 
                    category="production", 
                    level="info"
                )
            
            # Update basic fields
            product_id = data.get('product_id', batch.product_id)
            selected_product = Product.objects.filter(id=product_id).first()
            if not selected_product:
                return JsonResponse({'success': False, 'error': 'Selected product does not exist.'}, status=400)
            if selected_product.product_type != 'fresh':
                return JsonResponse({'success': False, 'error': 'Only fresh products can be used for production batches.'}, status=400)

            batch.product = selected_product
            batch.start_date = data.get('start_date', batch.start_date)
            batch.status = status_after
            batch.cost = data.get('cost') or None
            
            # Handle harvest date
            harvest_date_input = data.get('harvest_date')
            if harvest_date_input:
                batch.harvest_date = harvest_date_input
            
            # Handle yield
            yield_input = data.get('yield_kg')
            if yield_input:
                batch.yield_kg = yield_input
            
            # AUTO-HARVEST FUNCTIONALITY: When status changes to HARVESTED
            if status_after == 'HARVESTED' and status_before != 'HARVESTED':
                # Set harvest date to today if not already set
                if not batch.harvest_date:
                    batch.harvest_date = timezone.now().date()
                
                # If yield is provided and product exists, add to inventory
                if batch.yield_kg and batch.product:
                    # Add yield to product stock
                    batch.product.stock_kg = F('stock_kg') + batch.yield_kg
                    batch.product.save()
                    
                    # Refresh the product instance to get actual value
                    batch.product.refresh_from_db()
                    
                    # Create notification
                    Notification.objects.create(
                        title="Batch Harvested",
                        description=f"Batch {batch.batch_number} harvested! {batch.yield_kg}kg added to {batch.product.name} inventory. New stock: {batch.product.stock_kg}kg",
                        category="production",
                        level="success"
                    )
            
            batch.save()
            return JsonResponse({'success': True, 'message': 'Batch updated'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        batch.delete()
        return JsonResponse({'success': True, 'message': 'Batch deleted'})

@login_required(login_url='login')
def production_summary_api(request):
    summary = ProductionBatch.objects.aggregate(
        active_batches=Coalesce(Count('id', filter=Q(status__in=['GROWING', 'READY'])), 0),
        total_records=Coalesce(Count('id'), 0),
        total_yield=Coalesce(Sum('yield_kg'), Decimal('0.0'), output_field=DecimalField())
    )
    return JsonResponse(summary)


# --- Analytics API Helper Function ---
def get_chart_colors(index):
    colors = [
        {'border': '#22c55e', 'bg': 'rgba(34, 197, 94, 0.3)'},  # Green
        {'border': '#3b82f6', 'bg': 'rgba(59, 130, 246, 0.3)'}, # Blue
        {'border': '#8b5cf6', 'bg': 'rgba(139, 92, 246, 0.3)'}, # Purple
        {'border': '#f97316', 'bg': 'rgba(249, 115, 22, 0.3)'}, # Orange
        {'border': '#ec4899', 'bg': 'rgba(236, 72, 153, 0.3)'}, # Pink
    ]
    return colors[index % len(colors)]

@login_required(login_url='login')
def analytics_api(request):
    
    # --- 1. DYNAMIC SUMMARY CARDS ---
    yield_data = ProductionBatch.objects.filter(yield_kg__isnull=False).annotate(
        month=TruncMonth('harvest_date')
    ).values('month').annotate(
        monthly_yield=Sum('yield_kg')
    ).aggregate(
        avg_yield=Avg('monthly_yield')
    )
    revenue_data = Sale.objects.annotate(
        month=TruncMonth('sale_date')
    ).values('month').annotate(
        monthly_revenue=Sum('total_price')
    ).aggregate(
        avg_revenue=Avg('monthly_revenue')
    )
    total_batches = ProductionBatch.objects.count()
    harvested_batches = ProductionBatch.objects.filter(status='HARVESTED').count()
    success_rate = (harvested_batches / total_batches * 100) if total_batches > 0 else 0
    env_stability = 98.7 # This remains simulated

    # --- 2. DYNAMIC CHART DATA ---
    today = timezone.now()
    six_months_ago = today - timedelta(days=180)
    
    yield_by_month_product = ProductionBatch.objects.filter(
        harvest_date__gte=six_months_ago, 
        yield_kg__isnull=False,
        product__isnull=False
    ).annotate(
        month=TruncMonth('harvest_date')
    ).values('month', 'product__name').annotate(
        total_yield=Sum('yield_kg')
    ).order_by('month')
    
    months = sorted(list(set([item['month'] for item in yield_by_month_product])))
    products = sorted(list(set([item['product__name'] for item in yield_by_month_product])))
    month_labels = [m.strftime('%b %Y') for m in months]
    
    # Create a consistent product-to-color mapping
    product_color_map = {product: i for i, product in enumerate(products)}
    
    datasets_production = []
    for product_name in products:
        color_index = product_color_map[product_name]
        colors = get_chart_colors(color_index)
        dataset = {
            'label': product_name,
            'data': [],
            'borderColor': colors['border'],
            'backgroundColor': colors['bg'],
            'fill': True,
            'tension': 0.4
        }
        for month in months:
            yield_val = 0
            for item in yield_by_month_product:
                if item['month'] == month and item['product__name'] == product_name:
                    yield_val = float(item['total_yield'])
                    break
            dataset['data'].append(yield_val)
        datasets_production.append(dataset)

    production_over_time_data = {
        'labels': month_labels,
        'datasets': datasets_production
    }
    
    pie_chart_data = ProductionBatch.objects.filter(
        yield_kg__isnull=False, product__isnull=False
    ).values('product__name').annotate(
        total_yield=Sum('yield_kg')
    ).order_by('-total_yield')
    
    total_yield_all = pie_chart_data.aggregate(total=Sum('total_yield'))['total'] or 0
    pie_chart_labels = [item['product__name'] for item in pie_chart_data]
    pie_chart_values = [(float(item['total_yield']) / float(total_yield_all) * 100) if total_yield_all > 0 else 0 for item in pie_chart_data]
    # Use the same color mapping as bar chart
    pie_chart_colors = [get_chart_colors(product_color_map.get(label, 0))['border'] for label in pie_chart_labels]

    production_pie_chart = {
        'labels': pie_chart_labels,
        'data': pie_chart_values,
        'colors': pie_chart_colors
    }
    
    # --- Financial Chart (Revenue vs. Cost) ---
    revenue_by_month = Sale.objects.filter(
        sale_date__gte=six_months_ago
    ).annotate(
        month=TruncMonth(Cast('sale_date', DateField()))
    ).values('month').annotate(
        total_revenue=Sum('total_price')
    ).order_by('month')
    
    costs_by_month = ProductionBatch.objects.filter(
        harvest_date__gte=six_months_ago, cost__isnull=False
    ).annotate(
        month=TruncMonth('harvest_date')
    ).values('month').annotate(
        total_cost=Sum('cost')
    ).order_by('month')

    financials = {}
    all_months_set = set()
    
    for item in revenue_by_month:
        month_key = item['month']
        all_months_set.add(month_key)
        month_str = month_key.strftime('%Y-%m')
        if month_str not in financials:
            financials[month_str] = {'revenue': 0, 'cost': 0}
        financials[month_str]['revenue'] = item['total_revenue']

    for item in costs_by_month:
        month_key = item['month']
        all_months_set.add(month_key)
        month_str = month_key.strftime('%Y-%m')
        if month_str not in financials:
            financials[month_str] = {'revenue': 0, 'cost': 0}
        financials[month_str]['cost'] = item['total_cost']
        
    sorted_months = sorted(list(all_months_set))
    financial_labels = [m.strftime('%b %Y') for m in sorted_months]
    revenue_data_list = []
    cost_data_list = []
    profit_data_list = []
    
    total_revenue = 0
    total_cost = 0
    
    for month in sorted_months:
        month_str = month.strftime('%Y-%m')
        revenue = financials.get(month_str, {}).get('revenue', 0)
        cost = financials.get(month_str, {}).get('cost', 0)
        revenue = float(revenue)
        cost = float(cost)
        profit = revenue - cost
        
        revenue_data_list.append(revenue)
        cost_data_list.append(cost)
        profit_data_list.append(profit)
        
        total_revenue += revenue
        total_cost += cost

    financial_chart = {
        'labels': financial_labels,
        'datasets': [
            {'label': 'Revenue', 'data': revenue_data_list, 'borderColor': '#16a34a'},
            {'label': 'Costs', 'data': cost_data_list, 'borderColor': '#ef4444'},
            {'label': 'Net Profit', 'data': profit_data_list, 'borderColor': '#7c3aed', 'borderWidth': 3}
        ]
    }
    
    financial_summary = {
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'net_profit': total_revenue - total_cost
    }
    
    data = {
        'summary_cards': {
            'avg_yield': float(yield_data['avg_yield']) if yield_data['avg_yield'] is not None else 0.0,
            'avg_revenue': float(revenue_data['avg_revenue']) if revenue_data['avg_revenue'] is not None else 0.0,
            'success_rate': success_rate,
            'env_stability': env_stability
        },
        'charts': {
            'production_bar': production_over_time_data,
            'production_pie': production_pie_chart,
            'total_production': production_over_time_data,
            'financial': financial_chart,
            'financial_summary': financial_summary
        }
    }
    return JsonResponse(data)


@login_required(login_url='login')
@require_http_methods(["GET", "PUT"])
def profile_api(request):
    user = request.user
    if request.method == 'GET':
        return JsonResponse({'full_name': user.get_full_name(), 'email': user.email, 'username': user.username})
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            full_name = data.get('full_name', '').split(' ', 1)
            user.first_name = full_name[0]
            user.last_name = full_name[1] if len(full_name) > 1 else ''
            user.email = data.get('email', user.email)
            user.save()
            return JsonResponse({'success': True, 'message': 'Profile updated successfully'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required(login_url='login')
@require_http_methods(["POST"])
def change_password_api(request):
    try:
        data = json.loads(request.body)
        form = PasswordChangeForm(user=request.user, data=data)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            return JsonResponse({'success': True, 'message': 'Password updated successfully'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required(login_url='login')
@require_http_methods(["POST"])
def update_customer_profile(request):
    """Update customer profile information"""
    try:
        data = json.loads(request.body)
        user = request.user
        
        # Update User model fields
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = data.get('email', user.email)
        user.save()
        
        # Update UserProfile model fields
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.phone = data.get('phone', profile.phone)
        profile.address = data.get('address', profile.address)
        profile.city = data.get('city', profile.city)
        profile.postal_code = data.get('postal_code', profile.postal_code)
        
        # Update location coordinates if provided
        if 'latitude' in data and 'longitude' in data:
            profile.latitude = data.get('latitude')
            profile.longitude = data.get('longitude')
        
        profile.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully',
            'data': {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': profile.phone,
                'address': profile.address,
                'city': profile.city,
                'postal_code': profile.postal_code,
                'latitude': str(profile.latitude) if profile.latitude else None,
                'longitude': str(profile.longitude) if profile.longitude else None
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required(login_url='login')
def notifications_api(request, pk=None):
    if request.method == 'GET':
        notifications = Notification.objects.filter(is_read=False).order_by('-created_at')
        now = timezone.now()
        data = []
        for n in notifications:
            diff = now - n.created_at
            if diff.days > 0: time_ago = f"{diff.days} days ago"
            elif diff.seconds // 3600 > 0: time_ago = f"{diff.seconds // 3600} hours ago"
            elif diff.seconds // 60 > 0: time_ago = f"{diff.seconds // 60} minutes ago"
            else: time_ago = "Just now"
            data.append({'id': n.id, 'title': n.title, 'description': n.description, 'category': n.category, 'level': n.level, 'time_ago': time_ago,})
        return JsonResponse(data, safe=False)
    
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(pk=pk)
            notification.is_read = True
            notification.save()
            return JsonResponse({'success': True, 'message': 'Notification marked as read'})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required(login_url='login')
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    if request.method == 'POST':
        try:
            updated_count = Notification.objects.filter(is_read=False).update(is_read=True)
            return JsonResponse({
                'success': True, 
                'message': f'{updated_count} notifications marked as read'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
            
@login_required(login_url='login')
def environment_api(request):
    settings_obj = EnvironmentSettings.load()
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Control settings
            settings_obj.fan_on = data.get('fan_on', settings_obj.fan_on)
            settings_obj.fan_auto = data.get('fan_auto', settings_obj.fan_auto)
            settings_obj.fan_value = data.get('fan_value', settings_obj.fan_value)
            settings_obj.humidifier_on = data.get('humidifier_on', settings_obj.humidifier_on)
            settings_obj.humidifier_auto = data.get('humidifier_auto', settings_obj.humidifier_auto)
            settings_obj.humidifier_value = data.get('humidifier_value', settings_obj.humidifier_value)
            settings_obj.heater_on = data.get('heater_on', settings_obj.heater_on)
            settings_obj.heater_auto = data.get('heater_auto', settings_obj.heater_auto)
            settings_obj.heater_value = data.get('heater_value', settings_obj.heater_value)
            settings_obj.co2_on = data.get('co2_on', settings_obj.co2_on)
            settings_obj.co2_auto = data.get('co2_auto', settings_obj.co2_auto)
            settings_obj.co2_value = data.get('co2_value', settings_obj.co2_value)
            settings_obj.lights_on = data.get('lights_on', settings_obj.lights_on)
            settings_obj.lights_auto = data.get('lights_auto', settings_obj.lights_auto)
            settings_obj.lights_value = data.get('lights_value', settings_obj.lights_value)
            
            # Automation threshold settings (if provided)
            if 'fan_temp_threshold' in data:
                settings_obj.fan_temp_threshold = data['fan_temp_threshold']
            if 'fan_humidity_threshold' in data:
                settings_obj.fan_humidity_threshold = data['fan_humidity_threshold']
            if 'fan_air_quality_threshold' in data:
                settings_obj.fan_air_quality_threshold = data['fan_air_quality_threshold']
            if 'humidifier_low_threshold' in data:
                settings_obj.humidifier_low_threshold = data['humidifier_low_threshold']
            if 'humidifier_high_threshold' in data:
                settings_obj.humidifier_high_threshold = data['humidifier_high_threshold']
            if 'heater_low_threshold' in data:
                settings_obj.heater_low_threshold = data['heater_low_threshold']
            if 'heater_high_threshold' in data:
                settings_obj.heater_high_threshold = data['heater_high_threshold']
            if 'hysteresis_margin' in data:
                settings_obj.hysteresis_margin = data['hysteresis_margin']
            
            settings_obj.save()
            return JsonResponse({'success': True, 'message': 'Settings updated'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
    # --- GET Request with Predictive Maintenance ---
    latest_reading = SensorReading.objects.order_by('-timestamp').first()
    recommendations = []
    
    # Get ML predictions
    predictions = predict_preventive_action()
    
    if predictions and latest_reading:
        # Check if predictive actions are recommended
        if predictions['activate_humidifier']:
            recommendations.append(
                f"🤖 ML Alert: Humidity predicted to drop soon (currently {predictions['current_conditions']['humidity']}%). "
                f"Activating humidifier preventively. (Confidence: {predictions['confidence_humidifier']}%)"
            )
            
            # Auto-activate humidifier if in auto mode
            if settings_obj.humidifier_auto:
                settings_obj.humidifier_on = True
                settings_obj.save()
                
                # Log the action
                from core.models import AutomationLog
                AutomationLog.objects.create(
                    action='HUMIDIFIER_ON',
                    reason='Predictive ML model detected humidity will drop below threshold',
                    temperature_before=predictions['current_conditions']['temperature'],
                    humidity_before=predictions['current_conditions']['humidity'],
                    co2_before=predictions['current_conditions']['co2'] or 0,
                    confidence=predictions['confidence_humidifier']
                )
        
        if predictions['activate_ventilation']:
            recommendations.append(
                f"🤖 ML Alert: CO₂ predicted to spike soon (currently {predictions['current_conditions']['co2']} ppm). "
                f"Activating ventilation preventively. (Confidence: {predictions['confidence_ventilation']}%)"
            )
            
            # Auto-activate fan if in auto mode
            if settings_obj.fan_auto:
                settings_obj.fan_on = True
                settings_obj.save()
                
                from core.models import AutomationLog
                AutomationLog.objects.create(
                    action='VENTILATION_ON',
                    reason='Predictive ML model detected CO2 will exceed threshold',
                    temperature_before=predictions['current_conditions']['temperature'],
                    humidity_before=predictions['current_conditions']['humidity'],
                    co2_before=predictions['current_conditions']['co2'] or 0,
                    confidence=predictions['confidence_ventilation']
                )
        
        if predictions['activate_heater']:
            recommendations.append(
                f"🤖 ML Alert: Temperature predicted to drop soon (currently {predictions['current_conditions']['temperature']}°C). "
                f"Activating heater preventively. (Confidence: {predictions['confidence_heater']}%)"
            )
            
            # Auto-activate heater if in auto mode
            if settings_obj.heater_auto:
                settings_obj.heater_on = True
                settings_obj.save()
                
                from core.models import AutomationLog
                AutomationLog.objects.create(
                    action='HEATER_ON',
                    reason='Predictive ML model detected temperature will drop below threshold',
                    temperature_before=predictions['current_conditions']['temperature'],
                    humidity_before=predictions['current_conditions']['humidity'],
                    co2_before=predictions['current_conditions']['co2'] or 0,
                    confidence=predictions['confidence_heater']
                )
    
    # Traditional reactive recommendations (still included as fallback)
    if latest_reading:
        # Check CO2 only if sensor provides CO2 data (DHT22 doesn't measure CO2)
        if latest_reading.co2_ppm is not None and latest_reading.co2_ppm > (settings_obj.co2_value + 100):
            recommendations.append(f"CO₂ is high ({latest_reading.co2_ppm} ppm). Increase ventilation.")
            if not Notification.objects.filter(title="High CO₂ Alert", is_read=False).exists():
                Notification.objects.create(
                    title="High CO₂ Alert",
                    description=f"CO₂ levels are at {latest_reading.co2_ppm} ppm. Check ventilation.",
                    category="environmental",
                    level="warning"
                )
        
        if latest_reading.humidity < (settings_obj.humidifier_value - 10):
            recommendations.append(f"Humidity is low ({latest_reading.humidity}%). Increase humidifier.")
            if not Notification.objects.filter(title="Low Humidity Alert", is_read=False).exists():
                Notification.objects.create(
                    title="Low Humidity Alert",
                    description=f"Humidity is at {latest_reading.humidity}%. Check humidifier.",
                    category="environmental",
                    level="warning"
                )
        
        if latest_reading.temperature < (settings_obj.heater_value - 2):
            recommendations.append(f"Temperature is low ({latest_reading.temperature}°C). Increase heater target.")
            if not Notification.objects.filter(title="Low Temperature Alert", is_read=False).exists():
                Notification.objects.create(
                    title="Low Temperature Alert",
                    description=f"Temperature is at {latest_reading.temperature}°C. Check heater.",
                    category="environmental",
                    level="warning"
                )

    if not recommendations:
        recommendations.append("System is stable. All sensors within optimal range.")
    
    data_to_send = {
        'settings': {
            'fan_on': settings_obj.fan_on, 'fan_auto': settings_obj.fan_auto, 'fan_value': settings_obj.fan_value,
            'humidifier_on': settings_obj.humidifier_on, 'humidifier_auto': settings_obj.humidifier_auto, 'humidifier_value': settings_obj.humidifier_value,
            'heater_on': settings_obj.heater_on, 'heater_auto': settings_obj.heater_auto, 'heater_value': settings_obj.heater_value,
            'co2_on': settings_obj.co2_on, 'co2_auto': settings_obj.co2_auto, 'co2_value': settings_obj.co2_value,
            'lights_on': settings_obj.lights_on, 'lights_auto': settings_obj.lights_auto, 'lights_value': settings_obj.lights_value,
        },
        'thresholds': {
            'fan_temp_threshold': float(settings_obj.fan_temp_threshold),
            'fan_humidity_threshold': float(settings_obj.fan_humidity_threshold),
            'fan_air_quality_threshold': settings_obj.fan_air_quality_threshold,
            'humidifier_low_threshold': float(settings_obj.humidifier_low_threshold),
            'humidifier_high_threshold': float(settings_obj.humidifier_high_threshold),
            'heater_low_threshold': float(settings_obj.heater_low_threshold),
            'heater_high_threshold': float(settings_obj.heater_high_threshold),
            'hysteresis_margin': float(settings_obj.hysteresis_margin),
        },
        'recommendations': recommendations,
        'ml_predictions': predictions  # Include predictions in response
    }
    return JsonResponse(data_to_send)


# --- NEW: Watering Cycle API ---
@login_required(login_url='login')
@require_http_methods(["POST"])
def watering_api(request):
    try:
        # Simulate the cycle taking 5 seconds
        time.sleep(5) 
        
        # Create the notification
        Notification.objects.create(
            title="Watering Cycle Complete",
            description="Automated watering cycle completed successfully in all rooms.",
            category="system",
            level="success"
        )
        return JsonResponse({'success': True, 'message': 'Watering cycle complete.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


