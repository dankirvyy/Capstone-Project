# Google OAuth Integration Guide

This guide explains how to set up Google OAuth login for the KABUTOMATE mushroom dashboard.

## Prerequisites

1. **Google Cloud Console Account**: You need access to Google Cloud Console
2. **Django development server running**: The app should be accessible

## Step 1: Install django-allauth

Run the following command in your terminal:

```bash
pip install django-allauth
```

## Step 2: Run Database Migrations

The allauth apps need database tables. Run:

```bash
python manage.py migrate
```

This will create tables for:
- django.contrib.sites
- allauth.account
- allauth.socialaccount
- allauth.socialaccount.providers.google

## Step 3: Create a Site in Django Admin

1. Start the development server: `python manage.py runserver`
2. Go to Django Admin: http://127.0.0.1:8000/admin/
3. Log in with your admin credentials
4. Navigate to **Sites** → **Sites**
5. Edit the existing site (or create one):
   - **Domain name**: `127.0.0.1:8000` (for development) or your production domain
   - **Display name**: `KABUTOMATE`
6. Save the site

**Important**: Make sure the Site ID matches `SITE_ID = 1` in settings.py

## Step 4: Set Up Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth client ID**
5. Select **Web application** as the application type
6. Configure the OAuth client:
   - **Name**: `KABUTOMATE Login`
   - **Authorized JavaScript origins**: 
     - `http://127.0.0.1:8000`
     - `http://localhost:8000`
   - **Authorized redirect URIs**:
     - `http://127.0.0.1:8000/accounts/google/login/callback/`
     - `http://localhost:8000/accounts/google/login/callback/`
7. Click **Create**
8. Copy the **Client ID** and **Client Secret**

## Step 5: Configure OAuth in Django Admin

1. Go to Django Admin: http://127.0.0.1:8000/admin/
2. Navigate to **Social Accounts** → **Social applications**
3. Click **Add Social Application**
4. Fill in the form:                                                                
   - **Provider**: Google   
   - **Name**: Google Login
   - **Client id**: (paste the Client ID from Google)
   - **Secret key**: (paste the Client Secret from Google)
   - **Sites**: Select `127.0.0.1:8000` (move it to the Chosen sites)
5. Save

## Step 6: Test the Integration

1. Go to the login page: http://127.0.0.1:8000/login/
2. Click the "Sign in with Google" button
3. You should be redirected to Google's login page
4. After signing in with Google, you'll be redirected back to the shop

## How It Works

### For New Users (Sign Up with Google)
- A new User account is created with the Google email as username
- A UserProfile is automatically created with role = 'CUSTOMER'
- User is redirected to `/shop/`

### For Returning Users (Sign In with Google)
- User is authenticated using their linked Google account
- User is redirected based on their role:
  - Admins → `/dashboard/`
  - Customers → `/shop/`

## Production Setup

For production deployment, update:

1. **settings.py**: 
   - Set `DEBUG = False`
   - Update `ALLOWED_HOSTS` with your domain

2. **Django Admin Sites**:
   - Update the Site domain to your production domain

3. **Google Cloud Console**:
   - Add production URLs to Authorized origins and redirect URIs

## Troubleshooting

### "Site matching query does not exist" error
- Make sure you have a Site created in Django Admin
- Verify `SITE_ID = 1` in settings.py matches your Site's ID

### OAuth callback error
- Check that the redirect URI in Google Console exactly matches:
  `http://127.0.0.1:8000/accounts/google/login/callback/`
- Make sure there are no trailing slashes issues

### "Login cancelled" or "Access denied"
- User cancelled the Google sign-in flow
- Check if the OAuth consent screen is properly configured

## Files Modified

The following files were created/modified for Google OAuth:

- `mushroom_dashboard/settings.py` - Added allauth apps, middleware, and configuration
- `mushroom_dashboard/urls.py` - Added allauth URL patterns
- `core/adapters.py` - Custom adapters for role-based redirects
- `templates/login.html` - Added Google sign-in button
- `templates/register.html` - Added Google sign-up button
