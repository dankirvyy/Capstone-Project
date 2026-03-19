"""
GCash Payment Service (Sandbox Mode)
Handles GCash payment integration with sandbox/test environment.

In production, replace the sandbox methods with actual GCash API calls.
Currently supports simulation of:
- Successful payments
- Failed payments
- Pending payments

For production integration, use PayMongo or GCash direct API:
- PayMongo: https://developers.paymongo.com/
- GCash: https://developer.gcash.com/
"""

import logging
import secrets
import hashlib
import hmac
from decimal import Decimal
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

logger = logging.getLogger(__name__)


# Sandbox Configuration
GCASH_SANDBOX_MODE = True  # Set to False in production
GCASH_SANDBOX_SECRET_KEY = 'gcash_sandbox_secret_key_12345'  # Replace with actual key in production


class GCashPaymentService:
    """
    GCash Payment Service for handling sandbox and production payments.
    
    Usage:
        service = GCashPaymentService()
        result = service.create_payment(order)
        # Returns: {'success': True, 'payment_url': '...', 'transaction_id': '...'}
    """
    
    def __init__(self):
        self.sandbox_mode = getattr(settings, 'GCASH_SANDBOX_MODE', True)
        self.secret_key = getattr(settings, 'GCASH_SECRET_KEY', GCASH_SANDBOX_SECRET_KEY)
    
    def generate_transaction_id(self):
        """Generate unique transaction ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_str = secrets.token_hex(8).upper()
        return f"GCASH-{timestamp}-{random_str}"
    
    def generate_reference_number(self, order_number):
        """Generate payment reference number"""
        return f"REF-{order_number}-{secrets.token_hex(4).upper()}"
    
    def create_payment(self, order, request=None):
        """
        Create a GCash payment session for an order.
        
        In sandbox mode, this generates a simulated payment page URL.
        In production, this would call the actual GCash/PayMongo API.
        
        Args:
            order: Order object with total_amount
            request: HttpRequest object for building URLs
            
        Returns:
            dict: {
                'success': bool,
                'payment_url': str (URL to redirect customer),
                'transaction_id': str,
                'reference_number': str,
                'error': str (if failed)
            }
        """
        try:
            transaction_id = self.generate_transaction_id()
            reference_number = self.generate_reference_number(order.order_number)
            
            # Update order with transaction details
            order.transaction_id = transaction_id
            order.payment_reference = reference_number
            order.payment_status = 'PENDING'
            order.save()
            
            if self.sandbox_mode:
                # Sandbox: Build URL to our simulated payment page
                if request:
                    base_url = request.build_absolute_uri('/')[:-1]
                else:
                    base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
                
                payment_url = f"{base_url}/payment/gcash/{order.order_number}/"
                
                logger.info(f"[SANDBOX] GCash payment created for order {order.order_number}")
                
                return {
                    'success': True,
                    'payment_url': payment_url,
                    'transaction_id': transaction_id,
                    'reference_number': reference_number,
                    'sandbox_mode': True
                }
            else:
                # Production: Call actual GCash/PayMongo API
                # TODO: Implement actual API call
                # Example with PayMongo:
                # response = paymongo_client.sources.create(
                #     type='gcash',
                #     amount=int(order.total_amount * 100),  # In centavos
                #     currency='PHP',
                #     redirect={
                #         'success': f"{base_url}/payment/gcash/callback/success/",
                #         'failed': f"{base_url}/payment/gcash/callback/failed/"
                #     }
                # )
                
                return {
                    'success': False,
                    'error': 'Production GCash API not yet configured'
                }
                
        except Exception as e:
            logger.error(f"GCash payment creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_payment(self, order, action='success'):
        """
        Verify and complete a GCash payment.
        
        In sandbox mode, this simulates payment verification.
        In production, this would verify the payment with GCash/PayMongo API.
        
        Args:
            order: Order object
            action: 'success', 'failed', or 'pending'
            
        Returns:
            dict: {
                'success': bool,
                'payment_status': str,
                'message': str
            }
        """
        try:
            if self.sandbox_mode:
                if action == 'success':
                    order.payment_status = 'PAID'
                    order.is_paid = True
                    order.paid_at = timezone.now()
                    # Keep order status as PENDING - admin will manually process
                    # order.status stays as 'PENDING' until admin confirms
                    order.save()
                    
                    logger.info(f"[SANDBOX] Payment successful for order {order.order_number}")
                    
                    return {
                        'success': True,
                        'payment_status': 'PAID',
                        'message': 'Payment successful! Your order is awaiting confirmation from our team.'
                    }
                    
                elif action == 'failed':
                    order.payment_status = 'FAILED'
                    order.is_paid = False
                    # Don't change order status - keep as PENDING for retry
                    order.save()
                    
                    logger.info(f"[SANDBOX] Payment failed for order {order.order_number}")
                    
                    return {
                        'success': False,
                        'payment_status': 'FAILED',
                        'message': 'Payment failed. Please try again or choose a different payment method.'
                    }
                    
                elif action == 'pending':
                    order.payment_status = 'PENDING'
                    order.is_paid = False
                    order.save()
                    
                    logger.info(f"[SANDBOX] Payment pending for order {order.order_number}")
                    
                    return {
                        'success': True,
                        'payment_status': 'PENDING',
                        'message': 'Payment is being processed. We will notify you once confirmed.'
                    }
                    
                else:
                    return {
                        'success': False,
                        'payment_status': 'UNKNOWN',
                        'message': 'Invalid payment action'
                    }
            else:
                # Production: Verify with actual API
                # TODO: Implement actual verification
                return {
                    'success': False,
                    'payment_status': 'UNKNOWN',
                    'message': 'Production verification not implemented'
                }
                
        except Exception as e:
            logger.error(f"GCash payment verification failed: {str(e)}")
            return {
                'success': False,
                'payment_status': 'ERROR',
                'message': str(e)
            }
    
    def verify_webhook_signature(self, payload, signature):
        """
        Verify webhook signature from payment gateway.
        
        Args:
            payload: Raw request body
            signature: Signature from header
            
        Returns:
            bool: True if signature is valid
        """
        if self.sandbox_mode:
            # In sandbox, accept all webhooks
            return True
        
        # Production: Verify HMAC signature
        expected_signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def get_payment_status_display(self, status):
        """Get human-readable payment status"""
        status_map = {
            'UNPAID': ('Unpaid', 'secondary'),
            'PENDING': ('Payment Pending', 'warning'),
            'PAID': ('Paid', 'success'),
            'FAILED': ('Payment Failed', 'danger'),
            'REFUNDED': ('Refunded', 'info'),
        }
        return status_map.get(status, ('Unknown', 'secondary'))
    
    def cancel_payment(self, order):
        """
        Cancel a pending payment.
        
        Args:
            order: Order object
            
        Returns:
            dict: Result of cancellation
        """
        if order.payment_status == 'PAID':
            return {
                'success': False,
                'message': 'Cannot cancel a completed payment. Use refund instead.'
            }
        
        order.payment_status = 'UNPAID'
        order.transaction_id = None
        order.payment_reference = None
        order.save()
        
        return {
            'success': True,
            'message': 'Payment cancelled successfully'
        }
    
    def process_refund(self, order):
        """
        Process refund for a paid GCash order.
        
        In sandbox mode, this simulates the refund process.
        In production, this would call the actual GCash/PayMongo refund API.
        
        Args:
            order: Order object with payment to refund
            
        Returns:
            dict: {
                'success': bool,
                'refund_id': str,
                'refund_amount': Decimal,
                'message': str,
                'error': str (if failed)
            }
        """
        try:
            # Validate order can be refunded
            if order.payment_method != 'GCASH':
                return {
                    'success': False,
                    'error': 'Order was not paid via GCash'
                }
            
            if order.payment_status != 'PAID':
                return {
                    'success': False,
                    'error': f'Cannot refund order with payment status: {order.payment_status}'
                }
            
            refund_amount = order.total_amount
            refund_id = f"REFUND-{order.order_number}-{secrets.token_hex(4).upper()}"
            
            if self.sandbox_mode:
                # Sandbox: Simulate refund process
                logger.info(f"[SANDBOX] Processing refund for order {order.order_number}")
                logger.info(f"[SANDBOX] Refund ID: {refund_id}")
                logger.info(f"[SANDBOX] Refund Amount: ₱{refund_amount}")
                
                # Update order payment status
                order.payment_status = 'REFUNDED'
                order.is_paid = False
                order.admin_notes = (order.admin_notes or '') + f"\n[REFUND] {timezone.now().strftime('%Y-%m-%d %H:%M')} - Refund processed. Refund ID: {refund_id}, Amount: ₱{refund_amount}"
                order.save()
                
                logger.info(f"[SANDBOX] Refund completed for order {order.order_number}")
                
                return {
                    'success': True,
                    'refund_id': refund_id,
                    'refund_amount': refund_amount,
                    'message': f'Refund of ₱{refund_amount} has been processed. Refund ID: {refund_id}',
                    'sandbox_mode': True
                }
            else:
                # Production: Call actual GCash/PayMongo refund API
                # TODO: Implement actual API call
                # Example with PayMongo:
                # response = paymongo_client.refunds.create(
                #     payment_id=order.transaction_id,
                #     amount=int(refund_amount * 100),  # In centavos
                #     reason='requested_by_customer'
                # )
                
                return {
                    'success': False,
                    'error': 'Production GCash refund API not yet configured'
                }
                
        except Exception as e:
            logger.error(f"GCash refund failed for order {order.order_number}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instance
gcash_service = GCashPaymentService()


def create_gcash_payment(order, request=None):
    """Convenience function to create GCash payment"""
    return gcash_service.create_payment(order, request)


def verify_gcash_payment(order, action='success'):
    """Convenience function to verify GCash payment"""
    return gcash_service.verify_payment(order, action)


def get_payment_status_display(status):
    """Get payment status display info"""
    return gcash_service.get_payment_status_display(status)


def process_gcash_refund(order):
    """Convenience function to process GCash refund"""
    return gcash_service.process_refund(order)
