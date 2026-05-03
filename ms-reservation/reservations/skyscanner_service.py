import requests
import logging
from typing import Dict, List, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class SkyscannerService:
    """Service for communicating with Node.js Skyscanner flight service"""
    
    def __init__(self):
        self.base_url = getattr(settings, 'SERVICE_VOLS_URL', 'http://localhost:3002')
        self.timeout = getattr(settings, 'SERVICE_VOLS_TIMEOUT', 30)
    
    def _get_headers(self, request=None):
        """Get headers for API calls"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        if request and hasattr(request, 'META'):
            auth_header = request.META.get('HTTP_AUTHORIZATION')
            if auth_header:
                headers['Authorization'] = auth_header
        
        return headers
    
    def search_flights(self, params: Dict, request=None) -> Optional[Dict]:
        """Search flights using Skyscanner via Node.js service"""
        try:
            url = f"{self.base_url}/api/flights/search"
            headers = self._get_headers(request)
            
            logger.info(f"Calling Skyscanner flight search: {url}")
            logger.info(f"Params: {params}")
            
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Flight search returned {data.get('data', {}).get('count', 0)} flights")
                return data
            else:
                logger.error(f"Flight service error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling flight service: {str(e)}")
            return None
    
    def check_flight_availability(self, flight_id: str, request=None) -> Optional[Dict]:
        """Check flight availability"""
        try:
            url = f"{self.base_url}/api/flights/{flight_id}/availability"
            headers = self._get_headers(request)
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            return None
                
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return None


# Singleton instance
skyscanner_service = SkyscannerService()