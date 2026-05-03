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
    
    def search_flights(self, params: Dict) -> Optional[List[Dict]]:
        """Search for flights using Amadeus"""
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
    
    def confirm_flight_offer(self, flight_offer, retry_count: int = 0) -> Optional[Dict]:
        """Confirm flight price and availability with retry logic"""
        try:
            # CRITICAL FIX: Handle if flight_offer is a string or has different structure
            if isinstance(flight_offer, str):
                logger.error(f"flight_offer is a string: {flight_offer}")
                return None
            
            # Get the offer ID safely
            offer_id = flight_offer.get('id', 'unknown') if isinstance(flight_offer, dict) else 'unknown'
            cache_key = f"amadeus_offer:{offer_id}"
            cached_offer = cache.get(cache_key)
            if cached_offer:
                return cached_offer
            
            logger.info(f"Confirming flight offer: {offer_id}")
            
            # Handle different possible structures of flight_offer
            if isinstance(flight_offer, dict):
                if 'flightOffers' in flight_offer:
                    offer_to_confirm = flight_offer['flightOffers'][0]
                else:
                    offer_to_confirm = flight_offer
            else:
                logger.error(f"Unexpected flight_offer type: {type(flight_offer)}")
                return None
            
            # Ensure we have a proper dictionary
            if not isinstance(offer_to_confirm, dict):
                logger.error(f"offer_to_confirm is not a dict: {type(offer_to_confirm)}")
                return None
            
            clean_offer = self._clean_flight_offer(offer_to_confirm)
            
            logger.info(f"Sending to Amadeus pricing API")
            
            response = self.client.shopping.flight_offers.pricing.post(
                clean_offer,
                include='detailed-fare-rules'
            )
            
            confirmed_offer = response.data
            logger.info(f"Flight offer confirmed successfully")
            
            cache.set(cache_key, confirmed_offer, 300)
            return confirmed_offer
            
        except ResponseError as error:
            logger.error(f"Amadeus pricing error: {error}")
            
            if hasattr(error, 'response') and error.response:
                error_body = error.response.body
                logger.error(f"Error details: {error_body}")
                
                if error.response.status_code == 500:
                    error_code = None
                    if error_body and 'errors' in error_body:
                        errors = error_body.get('errors', [])
                        if errors:
                            error_code = errors[0].get('code')
                    
                    if error_code == 38189:
                        logger.warning("Flight offer expired or invalid")
                        
                        if retry_count < 2:
                            logger.info(f"Retrying with refreshed offer (attempt {retry_count + 1})")
                            refreshed_offer = self.refresh_flight_offer(flight_offer)
                            if refreshed_offer:
                                return self.confirm_flight_offer(refreshed_offer, retry_count + 1)
                        
                        return None
            
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error in confirm_flight_offer: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def refresh_flight_offer(self, original_offer: Dict) -> Optional[Dict]:
        """Try to refresh an expired flight offer by re-searching"""
        try:
            # Handle if original_offer is a string
            if isinstance(original_offer, str):
                logger.error(f"original_offer is a string: {original_offer}")
                return None
            
            if not isinstance(original_offer, dict):
                logger.error(f"original_offer is not a dict: {type(original_offer)}")
                return None
            
            itineraries = original_offer.get('itineraries', [])
            if not itineraries:
                return None
            
            first_segment = itineraries[0].get('segments', [{}])[0]
            
            search_params = {
                'originLocationCode': first_segment.get('departure', {}).get('iataCode'),
                'destinationLocationCode': first_segment.get('arrival', {}).get('iataCode'),
                'departureDate': first_segment.get('departure', {}).get('at', '')[:10],
                'adults': 1,
                'max': 5
            }
            
            if original_offer.get('travelerPricings'):
                for tp in original_offer.get('travelerPricings', []):
                    if tp.get('travelerType') == 'CHILD':
                        search_params['children'] = search_params.get('children', 0) + 1
                    elif tp.get('travelerType') == 'INFANT':
                        search_params['infants'] = search_params.get('infants', 0) + 1
            
            logger.info(f"Refreshing flight search with params: {search_params}")
            
            response = self.client.shopping.flight_offers_search.get(**search_params)
            
            if response.data and len(response.data) > 0:
                logger.info(f"Found {len(response.data)} refreshed offers")
                return response.data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error refreshing flight offer: {e}")
            return None
    
    def create_booking(self, confirmed_offer: Dict, travelers: List[Dict]) -> Optional[Dict]:
        """Create the actual booking in Amadeus"""
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
            return None
        except Exception as e:
            logger.error(f"Unexpected error in create_booking: {e}")
            return None
    
    def get_booking(self, booking_id: str) -> Optional[Dict]:
        """Retrieve booking details from Amadeus"""
        try:
            cache_key = f"amadeus_booking:{booking_id}"
            cached_booking = cache.get(cache_key)
            if cached_booking:
                return cached_booking
            
            logger.info(f"Retrieving booking with ID: {booking_id}")
            
            response = self.client.booking.flight_order(booking_id).get()
            
            booking_data = response.data
            logger.info(f"Booking retrieved successfully")
            
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
        """Cancel a booking in Amadeus"""
        try:
            logger.info(f"Cancelling booking with ID: {booking_id}")
            
            self.client.booking.flight_order(booking_id).delete()
            
            logger.info(f"Booking cancelled successfully")
            
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
    
    def get_traveler_seat_maps(self, booking_id: str) -> Optional[Dict]:
        """Get seat maps for a booking"""
        try:
            logger.info(f"Retrieving seat maps for booking: {booking_id}")
            
            response = self.client.shopping.seatmaps.get(booking_id)
            
            return response.data
            
        except ResponseError as error:
            logger.error(f"Amadeus seat map error: {error}")
            return None
        except Exception as e:
            logger.error(f"Error getting seat maps: {e}")
            return None
    
    def process_reservation(self, flight_offer, passengers: List[Dict]) -> Dict:
        """Complete reservation flow with Amadeus"""
        logger.info("Processing reservation with Amadeus")
        
        # Validate flight_offer
        if not flight_offer:
            raise Exception("No flight offer provided")
        
        if isinstance(flight_offer, str):
            raise Exception(f"Flight offer is a string, expected dict: {flight_offer}")
        
        if not isinstance(flight_offer, dict):
            raise Exception(f"Flight offer has unexpected type: {type(flight_offer)}")
        
        # First confirm the price
        confirmed_offer = self.confirm_flight_offer(flight_offer)
        if not confirmed_offer:
            raise Exception("Failed to confirm flight price - offer may be expired")
        
        # Then create booking
        booking = self.create_booking(confirmed_offer, passengers)
        if not booking:
            raise Exception("Failed to create booking in Amadeus")
        
        pnr = booking.get('id')
        logger.info(f"Booking successful with PNR: {pnr}")
        
        # Extract traveler IDs
        travelers = booking.get('travelers', [])
        traveler_id_map = {}
        for traveler in travelers:
            traveler_id_map[str(traveler.get('id'))] = traveler.get('id')
        
        return {
            'confirmed_offer': confirmed_offer,
            'booking': booking,
            'pnr': pnr,
            'traveler_ids': traveler_id_map,
            'status': 'CONFIRMED'
        }
    
    def _clean_flight_offer(self, offer: Dict) -> Dict:
        """Remove fields that might cause API errors"""
        clean_offer = {
            'type': offer.get('type', 'flight-offer'),
            'id': offer.get('id'),
            'source': offer.get('source', 'GDS'),
            'instantTicketingRequired': offer.get('instantTicketingRequired', False),
            'nonHomogeneous': offer.get('nonHomogeneous', False),
            'oneWay': offer.get('oneWay', False),
            'lastTicketingDate': offer.get('lastTicketingDate'),
            'lastTicketingDateTime': offer.get('lastTicketingDateTime'),
            'numberOfBookableSeats': offer.get('numberOfBookableSeats', 0),
            'itineraries': offer.get('itineraries', []),
            'price': offer.get('price', {}),
            'pricingOptions': offer.get('pricingOptions', {}),
            'validatingAirlineCodes': offer.get('validatingAirlineCodes', []),
            'travelerPricings': offer.get('travelerPricings', [])
        }
        
        # Remove None values
        clean_offer = {k: v for k, v in clean_offer.items() if v is not None}
        
        return clean_offer
    
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
    
    def process_reservation(self, flight_data, passengers: List[Dict]) -> Dict:
        """Complete reservation flow with Amadeus"""
        return self.client.process_reservation(flight_data, passengers)
    
    def get_booking_details(self, pnr: str) -> Optional[Dict]:
        """Get detailed booking information"""
        return self.client.get_booking(pnr)
    
    def cancel_reservation(self, pnr: str) -> bool:
        """Cancel a reservation"""
        return self.client.cancel_booking(pnr)
    
    def get_seat_maps(self, pnr: str) -> Optional[Dict]:
        """Get seat maps for a booking"""
        return self.client.get_traveler_seat_maps(pnr)


amadeus_service = AmadeusService()