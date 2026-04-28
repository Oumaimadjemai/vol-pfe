import requests
import logging
from typing import Dict, List, Optional
import time
import os
from threading import Lock

logger = logging.getLogger(__name__)


class AuthServiceClient:
    """Client for communicating with auth service using Eureka discovery"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern to reuse the same client instance"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AuthServiceClient, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, request=None):
        if self._initialized:
            self.request = request
            return
            
        self.request = request
        self.service_name = os.getenv("AUTH_SERVICE_NAME", "AUTH-SERVICE")
        self.eureka_server = os.getenv("EUREKA_SERVER", "http://localhost:8888/eureka/")
        self.timeout = int(os.getenv("AUTH_SERVICE_TIMEOUT", "30"))
        self._service_url = None
        self._last_fetch = 0
        self._cache_ttl = int(os.getenv("SERVICE_DISCOVERY_CACHE_TTL", "60"))
        self._fallback_url = os.getenv("AUTH_SERVICE_FALLBACK_URL", "http://localhost:8000")
        self._use_eureka = os.getenv("USE_EUREKA_DISCOVERY", "True").lower() == "true"
        self._initialized = True
        
        # Ensure eureka_server ends with /
        if self.eureka_server and not self.eureka_server.endswith('/'):
            self.eureka_server += '/'
        
        logger.info(f"AuthServiceClient initialized")
        logger.info(f"  Service: {self.service_name}")
        logger.info(f"  Use Eureka: {self._use_eureka}")
        logger.info(f"  Eureka URL: {self.eureka_server}")
        logger.info(f"  Fallback URL: {self._fallback_url}")
    
    def _get_service_from_eureka(self) -> Optional[str]:
        """Fetch service instance from Eureka server"""
        if not self._use_eureka:
            logger.debug("Eureka discovery disabled")
            return None
        
        try:
            # Headers to request JSON format from Eureka
            eureka_headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # Query Eureka for the service
            url = f"{self.eureka_server}apps/{self.service_name}"
            logger.debug(f"Querying Eureka: {url}")
            
            response = requests.get(url, headers=eureka_headers, timeout=5)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError as e:
                    logger.error(f"Invalid JSON from Eureka: {e}")
                    logger.error(f"Response preview: {response.text[:200]}")
                    return None
                
                # Parse Eureka response
                application = data.get('application', {})
                instances = application.get('instance', [])
                
                if not instances:
                    logger.warning(f"No instances found for {self.service_name}")
                    return None
                
                # Handle single instance
                if not isinstance(instances, list):
                    instances = [instances]
                
                # Get first available instance
                instance = instances[0]
                
                # Extract host
                host = instance.get('ipAddr')
                if not host:
                    host = instance.get('hostName')
                if not host:
                    host = instance.get('ipAddress', 'localhost')
                
                # Extract port
                port_info = instance.get('port', {})
                if isinstance(port_info, dict):
                    port = port_info.get('$', 8000)
                else:
                    port = port_info or 8000
                
                # Check status
                status = instance.get('status', 'UNKNOWN')
                if status.upper() != 'UP':
                    logger.warning(f"Instance {host}:{port} status is {status}")
                
                service_url = f"http://{host}:{port}"
                logger.info(f"Discovered {self.service_name} at {service_url} (status: {status})")
                return service_url
                
            elif response.status_code == 404:
                logger.warning(f"Service {self.service_name} not found in Eureka")
                # List available services for debugging
                self._list_available_services()
                return None
            else:
                logger.warning(f"Eureka returned status {response.status_code}")
                return None
                
        except requests.Timeout:
            logger.error(f"Timeout connecting to Eureka: {self.eureka_server}")
            return None
        except requests.ConnectionError:
            logger.error(f"Cannot connect to Eureka: {self.eureka_server}")
            return None
        except Exception as e:
            logger.error(f"Eureka discovery error: {e}")
            return None
    
    def _list_available_services(self):
        """List all services in Eureka for debugging"""
        try:
            eureka_headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            response = requests.get(f"{self.eureka_server}apps/", headers=eureka_headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                applications = data.get('applications', {}).get('application', [])
                if applications:
                    if not isinstance(applications, list):
                        applications = [applications]
                    services = [app.get('name') for app in applications if app.get('name')]
                    logger.info(f"Available services in Eureka: {services}")
                else:
                    logger.info("No services registered in Eureka")
        except Exception as e:
            logger.error(f"Failed to list services: {e}")
    
    def _get_service_url(self) -> str:
        """Get service URL with caching"""
        current_time = time.time()
        
        # Check cache
        if self._service_url and (current_time - self._last_fetch) < self._cache_ttl:
            return self._service_url
        
        # Try Eureka discovery
        if self._use_eureka:
            url = self._get_service_from_eureka()
            if url:
                self._service_url = url
                self._last_fetch = current_time
                logger.info(f"Using discovered URL: {url}")
                return url
            else:
                logger.warning("Eureka discovery failed, using fallback URL")
        
        # Use fallback
        logger.info(f"Using fallback URL: {self._fallback_url}")
        self._service_url = self._fallback_url
        self._last_fetch = current_time
        return self._fallback_url
    
    def _get_auth_headers(self) -> Dict:
        """Get authorization headers from the original request"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Forward Authorization header
        if self.request:
            # Check headers attribute
            if hasattr(self.request, 'headers'):
                auth_header = self.request.headers.get('Authorization')
                if auth_header:
                    headers['Authorization'] = auth_header
            
            # Check META for Django
            if hasattr(self.request, 'META'):
                auth_header = self.request.META.get('HTTP_AUTHORIZATION')
                if auth_header and 'Authorization' not in headers:
                    headers['Authorization'] = auth_header
        
        return headers
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """Make HTTP request with retry logic"""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                service_url = self._get_service_url()
                full_url = f"{service_url}{endpoint}"
                
                logger.debug(f"{method} {full_url} (attempt {attempt + 1})")
                
                response = requests.request(
                    method, 
                    full_url, 
                    timeout=self.timeout,
                    **kwargs
                )
                
                # Success or client error (4xx)
                if response.status_code < 500:
                    return response
                
                # Server error - retry
                logger.warning(f"Server error {response.status_code}, retrying...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    self._refresh_service_url()  # Try different instance
                    continue
                return response
                
            except (requests.Timeout, requests.ConnectionError) as e:
                logger.warning(f"Request error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    self._refresh_service_url()
                else:
                    raise
        
        return None
    
    def _refresh_service_url(self):
        """Force refresh of service URL"""
        self._service_url = None
        self._last_fetch = 0
    
    # Business methods
    def get_voyageur_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Get voyageur info by user_id"""
        endpoint = f"/auth/voyageurs/by-user/{user_id}/"
        
        try:
            headers = self._get_auth_headers()
            response = self._make_request('GET', endpoint, headers=headers)
            
            if response and response.status_code == 200:
                return response.json()
            elif response and response.status_code == 404:
                logger.warning(f"Voyageur not found for user_id {user_id}")
                return None
            else:
                logger.error(f"Failed to get voyageur: {response.status_code if response else 'No response'}")
                return None
        except Exception as e:
            logger.error(f"Error getting voyageur: {e}")
            return None
    
    def get_voyageur_by_id(self, voyageur_id: int) -> Optional[Dict]:
        """Get voyageur info by voyageur ID"""
        endpoint = f"/auth/voyageurs/{voyageur_id}/"
        
        try:
            headers = self._get_auth_headers()
            response = self._make_request('GET', endpoint, headers=headers)
            
            if response and response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get voyageur {voyageur_id}")
                return None
        except Exception as e:
            logger.error(f"Error getting voyageur: {e}")
            return None
    
    def get_passengers_by_voyageur(self, voyageur_id: int) -> List[Dict]:
        """Get all passengers for a specific voyageur"""
        endpoint = f"/auth/passengers/by-voyageur/{voyageur_id}/"
        
        try:
            headers = self._get_auth_headers()
            response = self._make_request('GET', endpoint, headers=headers)
            
            if response and response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'results' in data:
                    return data['results']
                else:
                    return []
            else:
                return []
        except Exception as e:
            logger.error(f"Error getting passengers: {e}")
            return []
    
    def create_passenger(self, passenger_data: Dict, voyageur_id: int) -> Optional[Dict]:
        """Create a new passenger"""
        endpoint = "/auth/passengers/create/"
        passenger_data['voyageur'] = voyageur_id
        
        try:
            headers = self._get_auth_headers()
            response = self._make_request('POST', endpoint, json=passenger_data, headers=headers)
            
            if response and response.status_code in [200, 201]:
                return response.json()
            else:
                logger.error(f"Failed to create passenger: {response.status_code if response else 'No response'}")
                return None
        except Exception as e:
            logger.error(f"Error creating passenger: {e}")
            return None
        
    def get_passenger(self, passenger_id: int) -> Optional[Dict]:
     """Get a single passenger by ID"""
     endpoint = f"/auth/passengers/{passenger_id}/"
    
     try:
        headers = self._get_auth_headers()
        response = self._make_request('GET', endpoint, headers=headers)
        
        if response and response.status_code == 200:
            data = response.json()
            logger.info(f"Found passenger: id={data.get('id')}")
            return data
        elif response and response.status_code == 404:
            logger.warning(f"Passenger not found with id {passenger_id}")
            return None
        else:
            logger.error(f"Failed to get passenger with id {passenger_id}")
            return None
            
     except Exception as e:
        logger.error(f"Error getting passenger with id {passenger_id}: {e}", exc_info=True)
        return None
    
    def health_check(self) -> bool:
        """Check if auth service is reachable"""
        try:
            endpoint = "/auth/health/"
            headers = self._get_auth_headers()
            response = self._make_request('GET', endpoint, headers=headers, timeout=5)
            return response is not None and response.status_code == 200
        except Exception:
            return False