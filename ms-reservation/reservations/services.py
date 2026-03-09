import requests
import logging
from typing import Dict, List, Optional
from django.conf import settings
import py_eureka_client.eureka_client as eureka_client
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AuthServiceClient:
    """Client for communicating with auth service via Eureka"""
    
    def __init__(self, request=None):
        self.request = request
        self.service_name = "auth-service"
        self.base_url = None
        self.cache_timeout = 300  # 5 minutes
    
    def _get_service_url(self):
        """Get service URL from Eureka or cache"""
        if not self.base_url:
            cache_key = f"eureka:{self.service_name}"
            cached_url = cache.get(cache_key)
            
            if cached_url:
                self.base_url = cached_url
                logger.info(f"Using cached auth service URL: {self.base_url}")
            else:
                try:
                    # Try to get from Eureka
                    self.base_url = eureka_client.get_app(self.service_name)
                    cache.set(cache_key, self.base_url, self.cache_timeout)
                    logger.info(f"Auth service URL from Eureka: {self.base_url}")
                except Exception as e:
                    logger.error(f"Failed to get auth service URL from Eureka: {e}")
                    self.base_url = settings.AUTH_SERVICE_URL.rstrip('/')
                    logger.info(f"Using fallback auth service URL: {self.base_url}")
        
        return self.base_url
    
    def _get_auth_headers(self):
        """Get authorization headers from the original request"""
        headers = {
            "Content-Type": "application/json",
        }
        
        # Forward the Authorization header if it exists
        if self.request and hasattr(self.request, 'headers'):
            auth_header = self.request.headers.get('Authorization')
            if auth_header:
                headers['Authorization'] = auth_header
                logger.info(f"Forwarding Authorization header: {auth_header[:20]}...")
            else:
                logger.warning("No Authorization header found in request")
        else:
            logger.warning("No request object available for auth headers")
        
        return headers
    
    def get_voyageur_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Get voyageur info by user_id"""
        base_url = self._get_service_url()
        endpoint = f"{base_url}/auth/voyageurs/by-user/{user_id}/"
        
        try:
            logger.info(f"Getting voyageur from: {endpoint}")
            headers = self._get_auth_headers()
            
            response = requests.get(endpoint, timeout=5, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Found voyageur: {data}")
                return data
            elif response.status_code == 401:
                logger.error(f"Authentication failed when getting voyageur: {response.status_code}")
                return None
            else:
                logger.error(f"Failed to get voyageur: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error getting voyageur for user_id {user_id}: {e}")
            return None
    
    def get_voyageur_by_id(self, voyageur_id: int) -> Optional[Dict]:
        """Get voyageur info by voyageur ID"""
        base_url = self._get_service_url()
        endpoint = f"{base_url}/auth/voyageurs/{voyageur_id}/"
        
        try:
            logger.info(f"Getting voyageur by ID from: {endpoint}")
            headers = self._get_auth_headers()
            
            response = requests.get(endpoint, timeout=5, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Found voyageur: {data}")
                return data
            elif response.status_code == 401:
                logger.error(f"Authentication failed when getting voyageur by ID: {response.status_code}")
                return None
            else:
                logger.error(f"Failed to get voyageur by ID: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error getting voyageur with id {voyageur_id}: {e}")
            return None
    
    def get_passenger(self, passenger_id: int) -> Optional[Dict]:
        """Get passenger info by ID"""
        base_url = self._get_service_url()
        endpoint = f"{base_url}/auth/passengers/{passenger_id}/"
        
        try:
            logger.info(f"Getting passenger from: {endpoint}")
            headers = self._get_auth_headers()
            
            response = requests.get(endpoint, timeout=5, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Found passenger: {data}")
                return data
            elif response.status_code == 401:
                logger.error(f"Authentication failed when getting passenger: {response.status_code}")
                return None
            else:
                logger.error(f"Failed to get passenger: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error getting passenger with id {passenger_id}: {e}")
            return None
    
    def create_passenger(self, passenger_data: Dict, voyageur_id: int) -> Optional[Dict]:
        """Create a new passenger"""
        base_url = self._get_service_url()
        endpoint = f"{base_url}/auth/passengers/create/"
        
        # Ensure voyageur_id is in the data
        passenger_data['voyageur'] = voyageur_id
        
        try:
            logger.info(f"Creating passenger at: {endpoint}")
            logger.info(f"Passenger data: {passenger_data}")
            
            headers = self._get_auth_headers()
            
            response = requests.post(
                endpoint, 
                json=passenger_data, 
                timeout=10,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                logger.info(f"Successfully created passenger: {data}")
                return data
            elif response.status_code == 400:
                logger.error(f"Validation error creating passenger: {response.text}")
                return None
            elif response.status_code == 401:
                logger.error(f"Authentication failed when creating passenger: {response.status_code}")
                return None
            elif response.status_code == 403:
                logger.error(f"Authorization failed when creating passenger: {response.status_code}")
                return None
            else:
                logger.error(f"Failed to create passenger: {response.status_code} - {response.text}")
                return None
                    
        except requests.RequestException as e:
            logger.error(f"Error creating passenger: {e}")
            return None
    
    def get_voyageur_passengers(self, voyageur_id: int) -> List[Dict]:
        """Get all passengers for a voyageur"""
        base_url = self._get_service_url()
        endpoint = f"{base_url}/auth/passengers/by-voyageur/{voyageur_id}/"
        
        try:
            logger.info(f"Getting passengers from: {endpoint}")
            headers = self._get_auth_headers()
            
            response = requests.get(endpoint, timeout=5, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                # Handle both list response and paginated response
                if isinstance(data, list):
                    logger.info(f"Found {len(data)} passengers")
                    return data
                elif isinstance(data, dict) and 'results' in data:
                    logger.info(f"Found {len(data['results'])} passengers")
                    return data['results']
                else:
                    logger.warning(f"Unexpected response format: {type(data)}")
                    return []
            elif response.status_code == 401:
                logger.error(f"Authentication failed when getting passengers: {response.status_code}")
                return []
            else:
                logger.error(f"Failed to get passengers: {response.status_code} - {response.text}")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Error getting passengers for voyageur {voyageur_id}: {e}")
            return []