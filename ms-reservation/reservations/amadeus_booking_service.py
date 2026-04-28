import logging
from typing import Dict, List, Optional
from datetime import datetime
from .amadeus_client import amadeus_service
import json
logger = logging.getLogger(__name__)


class AmadeusBookingService:
    """Service for handling real bookings with Amadeus API"""
    
    def __init__(self):
        self.amadeus = amadeus_service
    
    def create_booking_reference(self, flight_offer: Dict, passengers: List[Dict]) -> Dict:
        """Create a real booking using Amadeus API"""
        try:
            if isinstance(flight_offer, str):
                try:
                    flight_offer = json.loads(flight_offer)
                    logger.info("Parsed flight offer from string input")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse flight offer: {e}")
                    return {
                        'id': None,
                        'status': 'FAILED',
                        'error': 'Invalid flight offer format',
                        'error_code': 'INVALID_OFFER',
                        'requires_new_search': True
                    }
            logger.info(f"Creating real booking with Amadeus for {len(passengers)} passengers")
            
            # Process the reservation
            result = self.amadeus.process_reservation(flight_offer, passengers)
            
            if not result or not result.get('pnr'):
                logger.error("Failed to create booking with Amadeus")
                return {
                    'id': None,
                    'status': 'FAILED',
                    'error': 'Unable to create booking. Please try again.',
                    'error_code': 'BOOKING_FAILED',
                    'requires_new_search': True
                }
            
            # Extract traveler IDs
            booking = result.get('booking', {})
            travelers = booking.get('travelers', [])
            
            booking_response = {
                'id': result['pnr'],
                'status': 'CONFIRMED',
                'source': 'AMADEUS',
                'travelers': travelers,
                'traveler_ids': result.get('traveler_ids', {}),
                'booking_reference': booking.get('id'),
                'confirmed_offer': result.get('confirmed_offer'),
                'booking_data': booking,
                'created_at': datetime.now().isoformat()
            }
            
            logger.info(f"Real booking created with PNR: {result['pnr']}")
            return booking_response
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error creating Amadeus booking: {error_msg}", exc_info=True)
            
            if "expired" in error_msg.lower() or "offer" in error_msg.lower():
                return {
                    'id': None,
                    'status': 'FAILED',
                    'error': 'Le prix du vol n\'est plus valide. Veuillez effectuer une nouvelle recherche.',
                    'error_code': 'PRICE_EXPIRED',
                    'requires_new_search': True
                }
            
            return {
                'id': None,
                'status': 'FAILED',
                'error': f'Erreur technique: {error_msg}',
                'error_code': 'TECHNICAL_ERROR',
                'requires_new_search': True
            }
    
    def get_booking(self, pnr: str) -> Optional[Dict]:
        """Get real booking details from Amadeus"""
        try:
            booking = self.amadeus.get_booking_details(pnr)
            if booking:
                return {
                    'id': pnr,
                    'status': booking.get('status', 'CONFIRMED'),
                    'booking_data': booking,
                    'travelers': booking.get('travelers', [])
                }
            return None
        except Exception as e:
            logger.error(f"Error getting booking {pnr}: {e}")
            return None
    
    def cancel_booking(self, pnr: str) -> bool:
        """Cancel a real booking in Amadeus"""
        try:
            result = self.amadeus.cancel_reservation(pnr)
            if result:
                logger.info(f"Booking {pnr} cancelled successfully in Amadeus")
            return result
        except Exception as e:
            logger.error(f"Error cancelling booking {pnr}: {e}")
            return False
    
    def get_seat_maps(self, pnr: str) -> Optional[Dict]:
        """Get seat maps for a booking"""
        try:
            seat_maps = self.amadeus.get_seat_maps(pnr)
            return seat_maps
        except Exception as e:
            logger.error(f"Error getting seat maps for {pnr}: {e}")
            return None


amadeus_booking_service = AmadeusBookingService()