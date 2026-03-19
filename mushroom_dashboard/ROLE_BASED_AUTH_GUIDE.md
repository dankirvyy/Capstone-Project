# Role-Based Authentication System

This document explains the new role-based authentication system implemented in the Kabutomate mushroom dashboard.

## Overview

The system now supports two user roles:
1. **ADMIN** - Full access to the dashboard, analytics, production, inventory, POS, and order management
2. **CUSTOMER** - Access to the shop, cart, checkout, and their profile

## Features Implemented

### 1. User Roles
- Added `UserProfile` model that extends the Django User model
- Two roles: ADMIN and CUSTOMER
- Automatic profile creation for new users via Django signals

### 2. Customer Registration
- New registration page at `/register/`
- Collects customer information including:
  - Username, email, password
  - First name, last name
  - Phone number
  - Address, city, postal code
- All new registrations are assigned the CUSTOMER role by default
- Auto-login after successful registration

### 3. Role-Based Login Redirects
- **Admins** are redirected to `/` (dashboard) after login
- **Customers** are redirected to `/shop/` after login

### 4. Access Control

#### Admin-Only Pages (require ADMIN role):
- Dashboard (`/`)
- Environment Control (`/environment/`)
- Production Management (`/production/`)
- Inventory Management (`/inventory/`)
- Analytics (`/analytics/`)
- Weather (`/weather/`)
- Notifications (`/notifications/`)
- POS System (`/pos/`)
- Order Management (`/orders/`)

#### Public Pages (no login required):
- Login (`/login/`)
- Registration (`/register/`)
- Shop (`/shop/`)

#### Customer-Accessible Pages (require login):
- Shop (`/shop/`)
- Cart (`/cart/`)
- Checkout (`/checkout/`)
- Profile (`/profile/`)

## Usage

### For Customers:
1. Visit `/register/` to create a new account
2. Fill in the registration form
3. After successful registration, you'll be redirected to the shop
4. Browse products and add them to your cart
5. Proceed to checkout to place orders

### For Admins:
1. Login with your admin credentials at `/login/`
2. You'll be redirected to the dashboard
3. Access all admin features including:
   - Production batches
   - Inventory management
   - POS system for in-store sales
   - Order management for e-commerce orders
   - Analytics and reports

## Creating Admin Users

### Method 1: Using Django Admin
```bash
python manage.py createsuperuser
```
The user profile will automatically be created with ADMIN role for superusers.

### Method 2: Using Custom Management Command
```bash
python manage.py create_admin <username> <email> <password>
```

### Method 3: Updating Existing Users
Run the `update_user_profiles.py` script to ensure all existing users have profiles:
```bash
Get-Content update_user_profiles.py | python manage.py shell
```

## Database Changes

A new migration was created: `0013_userprofile.py`

This adds the `core_userprofile` table with the following fields:
- `user_id` (OneToOne with auth_user)
- `role` (ADMIN or CUSTOMER)
- `phone`
- `address`
- `city`
- `postal_code`
- `created_at`

## Security Features

1. **Automatic Redirects**: Customers trying to access admin pages are automatically redirected to the shop
2. **Decorator-Based Protection**: All admin views use the `@admin_required` decorator
3. **Login Required**: Both admin and customer pages require authentication
4. **Password Validation**: Minimum 6 characters for registration
5. **Unique Constraints**: Username and email must be unique

## Testing the System

1. **Test Customer Registration**:
   - Go to `/register/`
   - Create a new customer account
   - Verify redirect to shop after registration
   - Try accessing `/` - should redirect to `/shop/`

2. **Test Admin Access**:
   - Login with admin credentials
   - Verify redirect to dashboard
   - Access all admin features
   - Try accessing shop - should work for admins too

3. **Test Logout**:
   - Logout from either role
   - Verify redirect to login page
   - Verify no access to protected pages

## Files Modified/Created

### Modified:
- `core/models.py` - Added UserProfile model with signals
- `core/views.py` - Added admin_required decorator, register_view, updated login_view
- `core/ecommerce_views.py` - Updated POS and order management views with admin_required
- `core/urls.py` - Added register route
- `templates/login.html` - Added registration link

### Created:
- `templates/register.html` - Customer registration page
- `core/management/commands/create_admin.py` - Admin creation command
- `update_user_profiles.py` - Script to update existing users
- `core/migrations/0013_userprofile.py` - Database migration

## Notes

- The shop is accessible to everyone (no login required), but checkout requires account creation
- Admins can access both admin features and customer features (shop)
- All existing superusers and staff members are automatically assigned ADMIN role
- Regular users created before the update are assigned CUSTOMER role
