import requests
import logging
from rest_framework import authentication, exceptions
from django.conf import settings
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class AuthServiceUser:
    """
    Simple user class that mimics Django User model
    """
    def __init__(self, user_data: Dict):
        self.id = user_data.get('id')
        self.email = user_data.get('email')
        self.username = user_data.get('username')
        self.role = user_data.get('role')
        self.is_authenticated = True
        self.is_active = user_data.get('is_active', True)
        
        # Extract voyageur data if present
        self.voyageur_data = user_data.get('voyageur', {})
        self.voyageur_id = user_data.get('voyageur_id') or (self.voyageur_data.get('id') if self.voyageur_data else None)
        
        logger.info(f"Created AuthServiceUser: id={self.id}, email={self.email}, voyageur_id={self.voyageur_id}")
    
    @property
    def is_anonymous(self):
        return False
    
    def __str__(self):
        return f"User {self.id} - {self.email}"


class AuthServiceJWTAuthentication(authentication.BaseAuthentication):
    """
    JWT Authentication that validates tokens by calling the auth service /me endpoint
    """
    
    def __init__(self):
        self.auth_service_url = settings.AUTH_SERVICE_URL.rstrip('/')
        self.timeout = getattr(settings, 'AUTH_SERVICE_TIMEOUT', 5)
        logger.info(f"AuthServiceJWTAuthentication initialized with URL: {self.auth_service_url}")
    
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            logger.warning("No Authorization header found")
            return None
        
        # Extract token
        parts = auth_header.split()
        
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            logger.warning(f"Invalid Authorization header format: {auth_header[:20]}...")
            return None
        
        token = parts[1]
        logger.info(f"Validating token: {token[:20]}...")
        
        # Validate token with auth service
        user_data = self._validate_token(token)
        
        if not user_data:
            logger.error("Token validation failed")
            raise exceptions.AuthenticationFailed('Token invalide ou expiré')
        
        # Create user object
        user = AuthServiceUser(user_data)
        logger.info(f"Token validated for user: {user.email}")
        
        # Attach token to request for later use
        request.auth_token = token
        
        return (user, token)
    
    def _validate_token(self, token: str) -> Optional[Dict]:
        """
        Call auth service /me endpoint to validate token
        """
        # Try different possible endpoints
        endpoints = [
            f"{self.auth_service_url}/api/me/",
            f"{self.auth_service_url}/me/",
            f"{self.auth_service_url}/users/me/",
            f"{self.auth_service_url}/auth/me/",
        ]
        
        for endpoint in endpoints:
            try:
                logger.info(f"Trying endpoint: {endpoint}")
                response = requests.get(
                    endpoint,
                    headers={'Authorization': f'Bearer {token}'},
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    logger.info(f"Token validated successfully at {endpoint}")
                    return user_data
                else:
                    logger.debug(f"Endpoint {endpoint} returned {response.status_code}")
                    
            except requests.ConnectionError:
                logger.debug(f"Cannot connect to {endpoint}")
                continue
            except requests.Timeout:
                logger.debug(f"Timeout connecting to {endpoint}")
                continue
            except Exception as e:
                logger.debug(f"Error with {endpoint}: {e}")
                continue
        
        logger.error("All auth service endpoints failed")
        return None
    
    def authenticate_header(self, request):
        return 'Bearer'