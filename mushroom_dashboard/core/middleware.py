"""
Middleware for tracking user behavior
"""
from .models import RecentlyViewed, Product
from django.utils import timezone


class RecentlyViewedMiddleware:
    """Track recently viewed products"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Track product views on shop page
        if request.path == '/shop/' and request.method == 'GET':
            # Get product_id from query params if accessing specific product
            product_id = request.GET.get('product_id')
            
            if product_id:
                try:
                    product = Product.objects.get(id=product_id, is_active=True)
                    
                    if request.user.is_authenticated:
                        # For authenticated users, use user field
                        RecentlyViewed.objects.update_or_create(
                            user=request.user,
                            product=product,
                            defaults={'viewed_at': timezone.now()}
                        )
                    else:
                        # For anonymous users, use session
                        if not request.session.session_key:
                            request.session.create()
                        
                        RecentlyViewed.objects.update_or_create(
                            session_key=request.session.session_key,
                            product=product,
                            defaults={'viewed_at': timezone.now()}
                        )
                    
                    # Limit to 10 most recent items
                    if request.user.is_authenticated:
                        recent_items = RecentlyViewed.objects.filter(user=request.user).order_by('-viewed_at')
                        if recent_items.count() > 10:
                            items_to_delete = recent_items[10:]
                            RecentlyViewed.objects.filter(id__in=[item.id for item in items_to_delete]).delete()
                    else:
                        recent_items = RecentlyViewed.objects.filter(session_key=request.session.session_key).order_by('-viewed_at')
                        if recent_items.count() > 10:
                            items_to_delete = recent_items[10:]
                            RecentlyViewed.objects.filter(id__in=[item.id for item in items_to_delete]).delete()
                            
                except Product.DoesNotExist:
                    pass
        
        return response
