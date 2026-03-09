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
            cache_key = f"amadeus_offer:{flight_offer.get('id', '')}"
            cached_offer = cache.get(cache_key)
            if cached_offer:
                return cached_offer
            
            logger.info(f"Confirming flight offer")
            
            if 'flightOffers' in flight_offer:
                offer_to_confirm = flight_offer['flightOffers'][0]
            else:
                offer_to_confirm = flight_offer
            
            response = self.client.shopping.flight_offers.pricing.post(
                offer_to_confirm,
                include='detailed-fare-rules'
            )
            
            confirmed_offer = response.data
            logger.info(f"Flight offer confirmed")
            
            cache.set(cache_key, confirmed_offer, 300)
            return confirmed_offer
            
        except ResponseError as error:
            logger.error(f"Amadeus pricing error: {error}")
            if hasattr(error, 'response') and error.response:
                logger.error(f"Error details: {error.response.body}")
            return None
    
    def create_booking(self, confirmed_offer: Dict, travelers: List[Dict]) -> Optional[Dict]:
        """
        Step 3: Create the actual booking in Amadeus
        """
        try:
            formatted_travelers = self._format_travelers(travelers)
            
            if 'flightOffers' in confirmed_offer:
                flight_offers = confirmed_offer['flightOffers']
            else:
                flight_offers = [confirmed_offer]
            
            logger.info(f"Creating booking with {len(flight_offers)} flight offers and {len(formatted_travelers)} travelers")
            
            response = self.client.booking.flight_orders.post(
                flight_offers,
                formatted_travelers
            )
            
            booking = response.data
            pnr = booking.get('id')
            logger.info(f"Booking created with PNR: {pnr}")
            return booking
            
        except ResponseError as error:
            logger.error(f"Amadeus booking error: {error}")
            if hasattr(error, 'response') and error.response:
                logger.error(f"Error details: {error.response.body}")
                
                if 'PRICE DISCREPANCY' in str(error):
                    logger.info("Price discrepancy detected, need to reconfirm price")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in create_booking: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_booking(self, booking_id: str) -> Optional[Dict]:
        """
        Récupère les détails d'une réservation depuis Amadeus
        """
        try:
            cache_key = f"amadeus_booking:{booking_id}"
            cached_booking = cache.get(cache_key)
            if cached_booking:
                return cached_booking
            
            logger.info(f"Retrieving booking with ID: {booking_id}")
            
            response = self.client.booking.flight_order(booking_id).get()
            
            booking_data = response.data
            logger.info(f"Booking retrieved successfully")
            
            # Cache pour 1 minute seulement
            cache.set(cache_key, booking_data, 60)
            
            return booking_data
            
        except ResponseError as error:
            logger.error(f"Amadeus get booking error: {error}")
            if hasattr(error, 'response') and error.response:
                logger.error(f"Error details: {error.response.body}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_booking: {e}")
            return None
    
    def cancel_booking(self, booking_id: str) -> bool:
        """
        Annule une réservation dans Amadeus
        """
        try:
            logger.info(f"Cancelling booking with ID: {booking_id}")
            
            self.client.booking.flight_order(booking_id).delete()
            
            logger.info(f"Booking cancelled successfully")
            
            # Supprimer du cache
            cache.delete(f"amadeus_booking:{booking_id}")
            
            return True
            
        except ResponseError as error:
            logger.error(f"Amadeus cancellation error: {error}")
            if hasattr(error, 'response') and error.response:
                logger.error(f"Error details: {error.response.body}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in cancel_booking: {e}")
            return False
    
    def search_flights(self, params: Dict) -> Optional[List[Dict]]:
        """
        Recherche des vols
        """
        try:
            cache_key = f"flight_search:{hash(frozenset(params.items()))}"
            cached_results = cache.get(cache_key)
            if cached_results:
                return cached_results
            
            required_params = ['originLocationCode', 'destinationLocationCode', 'departureDate']
            for param in required_params:
                if param not in params:
                    logger.error(f"Missing required parameter: {param}")
                    return None
            
            request_params = {
                'originLocationCode': params.get('originLocationCode'),
                'destinationLocationCode': params.get('destinationLocationCode'),
                'departureDate': params.get('departureDate'),
                'adults': int(params.get('adults', 1)),
                'max': int(params.get('max', 10)),
                'currencyCode': params.get('currencyCode', 'DZD')
            }
            
            if params.get('returnDate'):
                request_params['returnDate'] = params.get('returnDate')
            
            if params.get('children'):
                request_params['children'] = int(params.get('children'))
            
            if params.get('infants'):
                request_params['infants'] = int(params.get('infants'))
            
            if params.get('travelClass'):
                request_params['travelClass'] = params.get('travelClass')
            
            logger.info(f"Calling Amadeus API with params: {request_params}")
            
            response = self.client.shopping.flight_offers_search.get(**request_params)
            
            results = response.data
            logger.info(f"Amadeus API returned {len(results) if results else 0} results")
            
            cache.set(cache_key, results, 300)
            return results
            
        except ResponseError as error:
            logger.error(f"Amadeus search error: {error}")
            if hasattr(error, 'response') and error.response:
                logger.error(f"Error details: {error.response.body}")
            return None
    
    def _format_travelers(self, travelers: List[Dict]) -> List[Dict]:
        """Format traveler data for Amadeus API"""
        formatted = []
        for idx, traveler in enumerate(travelers, 1):
            traveler_type = self._get_traveler_type(traveler.get('date_naissance'))
            
            phone = traveler.get('telephone', '')
            if phone:
                phone = ''.join(filter(str.isdigit, phone))
            
            formatted_traveler = {
                'id': str(idx),
                'dateOfBirth': traveler.get('date_naissance'),
                'name': {
                    'firstName': traveler.get('prenom'),
                    'lastName': traveler.get('nom')
                },
                'contact': {
                    'emailAddress': traveler.get('email', ''),
                }
            }
            
            if phone and len(phone) >= 8:
                formatted_traveler['contact']['phones'] = [{
                    'deviceType': 'MOBILE',
                    'countryCallingCode': '213',
                    'number': phone[-9:] if len(phone) > 9 else phone
                }]
            
            if traveler.get('num_passport'):
                formatted_traveler['documents'] = [{
                    'documentType': 'PASSPORT',
                    'number': traveler.get('num_passport'),
                    'expiryDate': traveler.get('date_exp_passport'),
                    'issuanceCountry': traveler.get('nationalite', 'DZ'),
                    'nationality': traveler.get('nationalite', 'DZ'),
                    'holder': True
                }]
            
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
            if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
                age -= 1
            
            if age < 2:
                return 'INFANT'
            elif age < 12:
                return 'CHILD'
            else:
                return 'ADULT'
        except Exception as e:
            logger.error(f"Error calculating traveler type: {e}")
            return 'ADULT'


class AmadeusService:
    """Service layer for Amadeus operations"""
    
    def __init__(self):
        self.client = AmadeusClient()
    
    def process_reservation(self, flight_data: Dict, passengers: List[Dict]) -> Dict:
        """
        Complete reservation flow with Amadeus
        """
        logger.info("Processing reservation with Amadeus")
        
        booking = self.client.create_booking(flight_data, passengers)
        
        if not booking:
            raise Exception("Failed to create booking in Amadeus")
        
        pnr = booking.get('id')
        logger.info(f"Booking successful with PNR: {pnr}")
        
        return {
            'confirmed_offer': flight_data,
            'booking': booking,
            'pnr': pnr,
            'status': 'CONFIRMED'
        }