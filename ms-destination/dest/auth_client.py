import requests
import logging
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

User = get_user_model()
logger = logging.getLogger(__name__)


class AuthServiceClient:
    """Client to communicate with Auth Service"""
    
    def __init__(self):
        self.auth_service_url = settings.AUTH_SERVICE_URL
        logger.info(f"Auth Service URL: {self.auth_service_url}")
    
    def verify_token(self, token):
        """Verify JWT token with Auth Service"""
        try:
            response = requests.get(
                f"{self.auth_service_url}/auth/me/",
                headers={'Authorization': f'Bearer {token}'},
                timeout=5
            )
            if response.status_code == 200:
                logger.info(f"Token verified for user: {response.json().get('email')}")
                return response.json()
            else:
                logger.warning(f"Token verification failed: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None
    
    def get_or_create_user(self, user_data):
        """Get or create Django user from auth service data"""
        try:
            user_id = user_data.get('id')
            email = user_data.get('email')
            username = user_data.get('username')
            
            # If no username is provided, generate one from email
            if not username:
                username = email.split('@')[0] if email else f"user_{user_id}"
            
            # Try to get existing user
            user, created = User.objects.get_or_create(
                id=user_id,
                defaults={
                    'username': username,
                    'email': email,
                    'is_active': user_data.get('is_active', True),
                    'is_staff': user_data.get('role') == 'admin',
                    'is_superuser': user_data.get('role') == 'admin',
                }
            )
            
            if not created:
                # Update existing user
                user.email = email
                user.is_active = user_data.get('is_active', True)
                user.is_staff = user_data.get('role') == 'admin'
                user.is_superuser = user_data.get('role') == 'admin'
                user.save()
            
            return user
            
        except Exception as e:
            logger.error(f"Error creating/getting user: {e}")
            return None


class OptionalJWTAuthentication(BaseAuthentication):
    """
    JWT Authentication that doesn't fail for unauthenticated requests.
    Returns None for unauthenticated, user for authenticated.
    """
    
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        
        # No token - allow anonymous access
        if not auth_header:
            return None
        
        try:
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                return None
            
            token = parts[1]
            
            # Verify token with Auth Service
            auth_client = AuthServiceClient()
            user_data = auth_client.verify_token(token)
            
            # Invalid token - allow anonymous access
            if not user_data:
                return None
            
            # Get or create user
            user = auth_client.get_or_create_user(user_data)
            
            if not user:
                return None
            
            # Add custom attributes
            user.role = user_data.get('role')
            user.original_data = user_data
            
            return (user, token)
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            # Return None to allow anonymous access
            return None
    
    def authenticate_header(self, request):
        return 'Bearer'