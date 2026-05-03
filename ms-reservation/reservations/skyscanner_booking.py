import uuid
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SkyscannerBookingService:
    """
    Service for handling bookings with Skyscanner
    Note: Skyscanner is a search API, actual booking is done via airline websites
    """
    
    def __init__(self):
        pass
    
    def create_booking_reference(self, flight_data: Dict, passengers: List[Dict]) -> Dict:
        """
        Create a booking reference (PNR simulation since Skyscanner doesn't create bookings)
        """
        # Generate a simulated PNR
        pnr = f"SKY-{uuid.uuid4().hex[:6].upper()}"
        
        # Extract flight info
        if 'flights' in flight_data:
            flight = flight_data.get('flights', [{}])[0]
        else:
            flight = flight_data
        
        booking_data = {
            'id': pnr,
            'status': 'CONFIRMED',
            'booking_date': datetime.now().isoformat(),
            'flight_offers': [flight_data] if not isinstance(flight_data, list) else flight_data,
            'travelers': passengers,
            'itineraries': self._extract_itineraries(flight_data),
            'booking_url': flight.get('bookingUrl', None),
            'source': 'SKYSCANNER'
        }
        
        logger.info(f"Created simulated booking with PNR: {pnr}")
        return booking_data
    
    def _extract_itineraries(self, flight_data: Dict) -> List[Dict]:
        """Extract itinerary information from flight data"""
        itineraries = []
        
        if 'flights' in flight_data:
            flights = flight_data['flights']
        elif isinstance(flight_data, list):
            flights = flight_data
        else:
            flights = [flight_data]
        
        for flight in flights:
            itinerary = {
                'segments': [{
                    'carrierCode': flight.get('airlineCode', flight.get('airline', 'SKY')[:2]),
                    'number': flight.get('flightNumber', '0000'),
                    'departure': {
                        'iataCode': flight.get('departure', {}).get('airport'),
                        'at': flight.get('departure', {}).get('time')
                    },
                    'arrival': {
                        'iataCode': flight.get('arrival', {}).get('airport'),
                        'at': flight.get('arrival', {}).get('time')
                    },
                    'bookingStatus': 'CONFIRMED'
                }]
            }
            itineraries.append(itinerary)
        
        return itineraries
    
    def get_booking(self, pnr: str) -> Optional[Dict]:
        """Get booking details by PNR (simulated)"""
        from .models import Reservation
        
        try:
            reservation = Reservation.objects.filter(amadeus_pnr=pnr).first()
            
            if reservation:
                return {
                    'id': pnr,
                    'status': reservation.status,
                    'total_price': str(reservation.total_price),
                    'currency': reservation.currency,
                    'booking_date': reservation.created_at.isoformat(),
                    'flight_offers': [reservation.original_offer] if reservation.original_offer else [],
                    'travelers': []
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting booking: {str(e)}")
            return None
    
    def cancel_booking(self, pnr: str) -> bool:
        """Cancel a booking (simulated - updates database status)"""
        from .models import Reservation
        
        try:
            reservation = Reservation.objects.filter(amadeus_pnr=pnr).first()
            if reservation:
                reservation.status = 'CANCELLED'
                reservation.save()
                logger.info(f"Booking {pnr} cancelled")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error cancelling booking: {str(e)}")
            return False


# Singleton instance - IMPORTANT: This is what you need to import
skyscanner_booking_service = SkyscannerBookingService()