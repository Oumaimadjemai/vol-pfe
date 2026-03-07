import requests
import logging
from typing import Dict, List, Optional
from django.conf import settings
import py_eureka_client.eureka_client as eureka_client
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AuthServiceClient:
    """Client for communicating with auth service via Eureka"""
    
    def __init__(self):
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
    
    def get_voyageur_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Get voyageur info by user_id"""
        base_url = self._get_service_url()
        
        # Try different possible endpoints
        endpoints = [
            f"{base_url}/api/voyageurs/by-user/{user_id}/",
            f"{base_url}/voyageurs/by-user/{user_id}/",
            f"{base_url}/users/voyageurs/by-user/{user_id}/",
            f"{base_url}/auth/voyageurs/by-user/{user_id}/",
        ]
        
        for endpoint in endpoints:
            try:
                logger.info(f"Trying to get voyageur from: {endpoint}")
                response = requests.get(endpoint, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Found voyageur: {data}")
                    return data
            except requests.RequestException as e:
                logger.debug(f"Endpoint {endpoint} failed: {e}")
                continue
        
        logger.error(f"Could not find voyageur for user_id {user_id} in any endpoint")
        return None
    
    def get_voyageur_by_id(self, voyageur_id: int) -> Optional[Dict]:
        """Get voyageur info by voyageur ID"""
        base_url = self._get_service_url()
        
        # Try different possible endpoints
        endpoints = [
            f"{base_url}/api/voyageurs/{voyageur_id}/",
            f"{base_url}/voyageurs/{voyageur_id}/",
            f"{base_url}/users/voyageurs/{voyageur_id}/",
            f"{base_url}/auth/voyageurs/{voyageur_id}/",
        ]
        
        for endpoint in endpoints:
            try:
                logger.info(f"Trying to get voyageur by ID from: {endpoint}")
                response = requests.get(endpoint, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Found voyageur: {data}")
                    return data
            except requests.RequestException as e:
                logger.debug(f"Endpoint {endpoint} failed: {e}")
                continue
        
        logger.error(f"Could not find voyageur with id {voyageur_id} in any endpoint")
        return None
    
    def get_passenger(self, passenger_id: int) -> Optional[Dict]:
        """Get passenger info by ID"""
        base_url = self._get_service_url()
        
        # Try different possible endpoints
        endpoints = [
            f"{base_url}/api/passengers/{passenger_id}/",
            f"{base_url}/passengers/{passenger_id}/",
            f"{base_url}/users/passengers/{passenger_id}/",
            f"{base_url}/auth/passengers/{passenger_id}/",
        ]
        
        for endpoint in endpoints:
            try:
                logger.info(f"Trying to get passenger from: {endpoint}")
                response = requests.get(endpoint, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Found passenger: {data}")
                    return data
            except requests.RequestException as e:
                logger.debug(f"Endpoint {endpoint} failed: {e}")
                continue
        
        logger.error(f"Could not find passenger with id {passenger_id} in any endpoint")
        return None
    
    def create_passenger(self, passenger_data: Dict, voyageur_id: int) -> Optional[Dict]:
        """Create a new passenger"""
        base_url = self._get_service_url()
        
        # Ensure voyageur_id is in the data
        passenger_data['voyageur'] = voyageur_id
        
        # Try different possible endpoints
        endpoints = [
            f"{base_url}/api/passengers/",
            f"{base_url}/api/passengers/create/",
            f"{base_url}/passengers/",
            f"{base_url}/users/passengers/",
        ]
        
        for endpoint in endpoints:
            try:
                logger.info(f"Trying to create passenger at: {endpoint}")
                logger.info(f"Passenger data: {passenger_data}")
                
                response = requests.post(
                    endpoint, 
                    json=passenger_data, 
                    timeout=5,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    logger.info(f"Created passenger: {data}")
                    return data
                else:
                    logger.warning(f"Endpoint {endpoint} returned {response.status_code}: {response.text}")
                    
            except requests.RequestException as e:
                logger.debug(f"Endpoint {endpoint} failed: {e}")
                continue
        
        logger.error("Could not create passenger in any endpoint")
        return None
    
    def get_voyageur_passengers(self, voyageur_id: int) -> List[Dict]:
        """Get all passengers for a voyageur"""
        base_url = self._get_service_url()
        
        # Try different possible endpoints
        endpoints = [
            f"{base_url}/api/passengers/by-voyageur/{voyageur_id}/",
            f"{base_url}/passengers/by-voyageur/{voyageur_id}/",
            f"{base_url}/users/passengers/by-voyageur/{voyageur_id}/",
            f"{base_url}/auth/passengers/by-voyageur/{voyageur_id}/",
        ]
        
        for endpoint in endpoints:
            try:
                logger.info(f"Trying to get passengers from: {endpoint}")
                response = requests.get(endpoint, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Found {len(data)} passengers")
                    return data if isinstance(data, list) else data.get('results', [])
            except requests.RequestException as e:
                logger.debug(f"Endpoint {endpoint} failed: {e}")
                continue
        
        logger.error(f"Could not find passengers for voyageur {voyageur_id} in any endpoint")
        return []