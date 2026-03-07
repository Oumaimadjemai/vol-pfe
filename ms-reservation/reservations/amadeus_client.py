import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from amadeus import Client, ResponseError
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AmadeusClient:
    """Client for interacting with Amadeus Flight APIs"""
    
    def __init__(self):
        self.client = Client(
            client_id=settings.AMADEUS_API_KEY,
            client_secret=settings.AMADEUS_API_SECRET,
            hostname=settings.AMADEUS_ENVIRONMENT
        )
        self.cache_timeout = 300  # 5 minutes
    
    def confirm_flight_offer(self, flight_offer: Dict) -> Optional[Dict]:
        """
        Step 2: Confirm flight price and availability
        """
        try:
            # Check cache first
            cache_key = f"amadeus_offer:{flight_offer.get('id', '')}"
            cached_offer = cache.get(cache_key)
            if cached_offer:
                return cached_offer
            
            response = self.client.shopping.flight_offers.pricing.post(
                flight_offer,
                include='detailed-fare-rules'
            )
            
            confirmed_offer = response.data
            logger.info(f"Flight offer confirmed: {confirmed_offer.get('id')}")
            
            # Cache the confirmed offer
            cache.set(cache_key, confirmed_offer, 300)  # 5 minutes
            
            return confirmed_offer
            
        except ResponseError as error:
            logger.error(f"Amadeus pricing error: {error}")
            if 'PRICE DISCREPANCY' in str(error):
                # Price has changed - extract new price
                return self._extract_new_price(error)
            return None
    
    def create_booking(self, confirmed_offer: Dict, travelers: List[Dict]) -> Optional[Dict]:
        """
        Step 3: Create the actual booking in Amadeus
        """
        try:
            formatted_travelers = self._format_travelers(travelers)
            
            response = self.client.booking.flight_orders.post(
                {
                    'type': 'flight-order',
                    'flightOffers': [confirmed_offer],
                    'travelers': formatted_travelers
                }
            )
            
            booking = response.data
            logger.info(f"Booking created with PNR: {booking.get('id')}")
            return booking
            
        except ResponseError as error:
            logger.error(f"Amadeus booking error: {error}")
            return None
    
    def get_booking(self, booking_id: str) -> Optional[Dict]:
        """Retrieve booking details from Amadeus"""
        try:
            cache_key = f"amadeus_booking:{booking_id}"
            cached_booking = cache.get(cache_key)
            if cached_booking:
                return cached_booking
            
            response = self.client.booking.flight_order(booking_id).get()
            booking_data = response.data
            
            cache.set(cache_key, booking_data, 60)  # 1 minute
            return booking_data
            
        except ResponseError as error:
            logger.error(f"Amadeus get booking error: {error}")
            return None
    
    def cancel_booking(self, booking_id: str) -> bool:
        """Cancel a booking in Amadeus"""
        try:
            self.client.booking.flight_order(booking_id).delete()
            logger.info(f"Booking {booking_id} cancelled")
            
            # Clear cache
            cache.delete(f"amadeus_booking:{booking_id}")
            return True
            
        except ResponseError as error:
            logger.error(f"Amadeus cancellation error: {error}")
            return False
    
    def search_flights(self, params: Dict) -> Optional[List[Dict]]:
        """Search for flights (if needed)"""
        try:
            cache_key = f"flight_search:{hash(frozenset(params.items()))}"
            cached_results = cache.get(cache_key)
            if cached_results:
                return cached_results
            
            response = self.client.shopping.flight_offers_search.get(
                originLocationCode=params.get('origin'),
                destinationLocationCode=params.get('destination'),
                departureDate=params.get('departureDate'),
                returnDate=params.get('returnDate'),
                adults=params.get('adults', 1),
                children=params.get('children', 0),
                infants=params.get('infants', 0),
                travelClass=params.get('travelClass', 'ECONOMY'),
                nonStop=params.get('nonStop', False),
                currencyCode=params.get('currency', 'DZD'),
                max=params.get('max', 50)
            )
            
            results = response.data
            cache.set(cache_key, results, 300)  # 5 minutes
            return results
            
        except ResponseError as error:
            logger.error(f"Amadeus search error: {error}")
            return None
    
    def _format_travelers(self, travelers: List[Dict]) -> List[Dict]:
        """Format traveler data for Amadeus API"""
        formatted = []
        for idx, traveler in enumerate(travelers, 1):
            traveler_type = self._get_traveler_type(traveler.get('date_naissance'))
            
            formatted_traveler = {
                'id': str(idx),
                'dateOfBirth': traveler.get('date_naissance'),
                'name': {
                    'firstName': traveler.get('prenom'),
                    'lastName': traveler.get('nom')
                },
                'contact': {
                    'emailAddress': traveler.get('email', ''),
                    'phones': [{
                        'deviceType': 'MOBILE',
                        'countryCallingCode': '33',
                        'number': traveler.get('telephone', '')
                    }] if traveler.get('telephone') else []
                }
            }
            
            # Add documents if passport info exists
            if traveler.get('num_passport'):
                formatted_traveler['documents'] = [{
                    'documentType': 'PASSPORT',
                    'number': traveler.get('num_passport'),
                    'expiryDate': traveler.get('date_exp_passport'),
                    'nationality': traveler.get('nationalite', 'FR'),
                    'issuanceCountry': traveler.get('nationalite', 'FR')
                }]
            
            # Add traveler type if not adult
            if traveler_type != 'ADULT':
                formatted_traveler['travelerType'] = traveler_type
            
            formatted.append(formatted_traveler)
        
        return formatted
    
    def _get_traveler_type(self, birth_date_str: Optional[str]) -> str:
        """Determine traveler type based on age"""
        if not birth_date_str:
            return 'ADULT'
        
        try:
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            today = datetime.now().date()
            age = today.year - birth_date.year
            
            if age < 2:
                return 'INFANT'
            elif age < 12:
                return 'CHILD'
            else:
                return 'ADULT'
        except:
            return 'ADULT'
    
    def _extract_new_price(self, error_response) -> Optional[Dict]:
        """Extract new price from Amadeus error response"""
        try:
            # This is a simplified version - actual implementation depends on Amadeus error format
            return None
        except:
            return None


class AmadeusService:
    """Service layer for Amadeus operations"""
    
    def __init__(self):
        self.client = AmadeusClient()
    
    def process_reservation(self, flight_data: Dict, passengers: List[Dict]) -> Dict:
        """
        Complete reservation flow with Amadeus
        """
        # Step 1: Confirm price and availability
        confirmed_offer = self.client.confirm_flight_offer(flight_data)
        
        if not confirmed_offer:
            raise Exception("Flight not available or price changed")
        
        # Step 2: Create booking
        booking = self.client.create_booking(confirmed_offer, passengers)
        
        if not booking:
            raise Exception("Failed to create booking in Amadeus")
        
        return {
            'confirmed_offer': confirmed_offer,
            'booking': booking,
            'pnr': booking.get('id'),
            'status': booking.get('flightOffers', [{}])[0].get('status', 'CONFIRMED')
        }