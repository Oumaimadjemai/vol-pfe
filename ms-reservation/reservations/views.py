from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime, timedelta, date
import logging

from .models import Reservation, FlightSegment, Payment, PriceConfirmation, PassengerReservation
from .serializers import (
    ReservationSerializer, ReservationListSerializer,
    ReservationRequestSerializer, PassengerInfoSerializer,
    PaymentSerializer, PriceConfirmationSerializer
)
from .services import AuthServiceClient
from .amadeus_client import AmadeusService
from .authentication import AuthServiceJWTAuthentication

logger = logging.getLogger(__name__)


class ReservationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing reservations with Amadeus integration"""
    queryset = Reservation.objects.all()
    authentication_classes = [AuthServiceJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.amadeus_service = AmadeusService()
        self.auth_client = AuthServiceClient()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ReservationListSerializer
        return ReservationSerializer
    
    def get_queryset(self):
        """Filter reservations by current voyageur"""
        user = self.request.user
        
        # User object already has voyageur_id from authentication
        if hasattr(user, 'voyageur_id') and user.voyageur_id:
            logger.info(f"Filtering reservations for voyageur_id: {user.voyageur_id}")
            return Reservation.objects.filter(voyageur=user.voyageur_id)
        
        # Fallback: try to get voyageur from auth service
        voyageur_data = self.auth_client.get_voyageur_by_user_id(user.id)
        
        if voyageur_data:
            voyageur_id = voyageur_data.get('id')
            logger.info(f"Found voyageur_id {voyageur_id} for user {user.id}")
            return Reservation.objects.filter(voyageur=voyageur_id)
        
        logger.warning(f"No voyageur found for user {user.id}")
        return Reservation.objects.none()
    
    def create(self, request, *args, **kwargs):
        """
        Step 1: Create initial reservation with price confirmation
        """
        # Log the incoming data for debugging
        logger.info(f"Creating reservation with data: {request.data}")
        
        # Calculate passengers count
        passengers_count = len(request.data.get('passengers', [])) + len(request.data.get('existing_passenger_ids', []))
        
        serializer = ReservationRequestSerializer(
            data=request.data,
            context={'passengers_count': passengers_count}
        )
        
        if not serializer.is_valid():
            logger.error(f"Validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        user = request.user
        
        try:
            # Get voyageur ID from authenticated user
            voyageur_id = None
            
            if hasattr(user, 'voyageur_id') and user.voyageur_id:
                voyageur_id = user.voyageur_id
                logger.info(f"Using voyageur_id {voyageur_id} from authenticated user")
            else:
                # Fallback: fetch from auth service
                voyageur_data = self.auth_client.get_voyageur_by_user_id(user.id)
                if voyageur_data:
                    voyageur_id = voyageur_data.get('id')
                    logger.info(f"Fetched voyageur_id {voyageur_id} from auth service")
            
            if not voyageur_id:
                return Response(
                    {'error': 'Voyageur non trouvé'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Calculate total price
            total_price = sum(
                flight['price']['total'] for flight in data['selected_flights']
            )
            
            # Create reservation
            reservation = Reservation.objects.create(
                voyageur=voyageur_id,
                trip_type=data['trip_type'],
                search_params=data['search_params'],
                total_price=total_price,
                currency=data['selected_flights'][0]['price']['currency'],
                status='PENDING_PRICE'
            )
            
            # Create flight segments
            for idx, flight in enumerate(data['selected_flights'], 1):
                # Parse datetime strings
                departure_time_str = flight['departure']['time'].replace('Z', '+00:00')
                arrival_time_str = flight['arrival']['time'].replace('Z', '+00:00')
                
                departure_datetime = datetime.fromisoformat(departure_time_str)
                arrival_datetime = datetime.fromisoformat(arrival_time_str)
                
                FlightSegment.objects.create(
                    reservation=reservation,
                    segment_number=idx,
                    origin=flight['departure']['airport'],
                    destination=flight['arrival']['airport'],
                    departure_date=departure_datetime.date(),
                    departure_time=departure_datetime.time(),
                    arrival_date=arrival_datetime.date(),
                    arrival_time=arrival_datetime.time(),
                    flight_data=flight,
                    price=flight['price']['total'],
                    per_passenger_price=flight['price']['perPassenger']
                )
            
            # Create passengers in auth service
            passenger_ids = list(data.get('existing_passenger_ids', []))
            
            for passenger_data in data.get('passengers', []):
                # Convert date objects to strings for JSON serialization
                passenger_data_for_api = passenger_data.copy()
                if 'date_naissance' in passenger_data_for_api and isinstance(passenger_data_for_api['date_naissance'], date):
                    passenger_data_for_api['date_naissance'] = passenger_data_for_api['date_naissance'].isoformat()
                if 'date_exp_passport' in passenger_data_for_api and passenger_data_for_api['date_exp_passport'] and isinstance(passenger_data_for_api['date_exp_passport'], date):
                    passenger_data_for_api['date_exp_passport'] = passenger_data_for_api['date_exp_passport'].isoformat()
                
                created_passenger = self.auth_client.create_passenger(
                    passenger_data_for_api,
                    voyageur_id
                )
                if created_passenger:
                    passenger_ids.append(created_passenger['id'])
            
            # Create passenger-reservation associations
            for passenger_id in passenger_ids:
                # Calculate price per passenger (simplified)
                price_paid = total_price / len(passenger_ids) if passenger_ids else 0
                
                # Get baggage quantity from flight data
                baggage_quantity = data['selected_flights'][0].get('baggage', {}).get('quantity', 0)
                
                PassengerReservation.objects.create(
                    reservation=reservation,
                    passenger=passenger_id,
                    price_paid=price_paid,
                    baggage_quantity=baggage_quantity
                )
            
            # Create payment entry
            Payment.objects.create(
                reservation=reservation,
                amount=total_price,
                currency=reservation.currency,
                payment_method=data['payment_method']
            )
            
            response_serializer = ReservationSerializer(reservation)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Error creating reservation: {str(e)}", exc_info=True)
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Erreur lors de la création: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def confirm_price(self, request, pk=None):
        """
        Step 2: Confirm price with Amadeus before booking
        """
        reservation = self.get_object()
        
        if reservation.status != 'PENDING_PRICE':
            return Response(
                {'error': 'Cette réservation ne peut pas être confirmée'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            flight_segment = reservation.flight_segments.first()
            if not flight_segment:
                return Response(
                    {'error': 'Aucun vol trouvé'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            flight_offer = flight_segment.flight_data
            
            confirmed_offer = self.amadeus_service.client.confirm_flight_offer(flight_offer)
            
            if not confirmed_offer:
                return Response(
                    {
                        'error': 'Le prix a changé ou le vol n\'est plus disponible',
                        'action': 'RECHERCHER_NOUVEAU_VOL'
                    },
                    status=status.HTTP_409_CONFLICT
                )
            
            new_price = float(confirmed_offer.get('price', {}).get('total', 0))
            
            price_confirmation = PriceConfirmation.objects.create(
                reservation=reservation,
                offered_price=reservation.total_price,
                confirmed_price=new_price,
                currency=reservation.currency,
                amadeus_offer_id=confirmed_offer.get('id'),
                offer_data=confirmed_offer,
                expires_at=timezone.now() + timedelta(minutes=5)
            )
            
            reservation.status = 'PRICE_CONFIRMED'
            reservation.last_confirmed_price = new_price
            reservation.price_confirmed_at = timezone.now()
            reservation.confirmed_offer_data = confirmed_offer
            reservation.amadeus_offer_id = confirmed_offer.get('id')
            reservation.expiry_date = price_confirmation.expires_at
            reservation.save()
            
            return Response({
                'message': 'Prix confirmé',
                'reservation': ReservationSerializer(reservation).data,
                'price_confirmation': PriceConfirmationSerializer(price_confirmation).data
            })
            
        except Exception as e:
            logger.error(f"Error confirming price: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Erreur lors de la confirmation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def book(self, request, pk=None):
        """
        Step 3: Actually book with Amadeus after price confirmation
        """
        reservation = self.get_object()
        
        if reservation.status != 'PRICE_CONFIRMED':
            return Response(
                {'error': 'Le prix doit être confirmé avant la réservation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        latest_confirmation = reservation.price_confirmations.last()
        if not latest_confirmation or not latest_confirmation.is_valid():
            return Response(
                {
                    'error': 'La confirmation de prix a expiré',
                    'action': 'RECONFIRMER_PRIX'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get passengers from auth service
            passengers_data = []
            
            # Get all passenger reservations
            passenger_reservations = reservation.passenger_reservations.all()
            
            for pr in passenger_reservations:
                passenger_data = self.auth_client.get_passenger(pr.passenger_id)
                if passenger_data:
                    # Add voyageur info for contact
                    voyageur_data = self.auth_client.get_voyageur_by_id(reservation.voyageur)
                    if voyageur_data:
                        passenger_data['email'] = voyageur_data.get('user', {}).get('email')
                        passenger_data['telephone'] = voyageur_data.get('telephone')
                    passengers_data.append(passenger_data)
            
            if not passengers_data:
                return Response(
                    {'error': 'Aucun passager trouvé dans le service d\'authentification'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            booking_result = self.amadeus_service.process_reservation(
                reservation.confirmed_offer_data,
                passengers_data
            )
            
            reservation.status = 'CONFIRMED'
            reservation.amadeus_pnr = booking_result['pnr']
            reservation.amadeus_booking_data = booking_result['booking']
            reservation.confirmation_date = timezone.now()
            reservation.save()
            
            # Update passenger associations with Amadeus traveler IDs
            travelers = booking_result['booking'].get('travelers', [])
            for idx, pr in enumerate(reservation.passenger_reservations.all()):
                if idx < len(travelers):
                    pr.amadeus_traveler_id = travelers[idx].get('id')
                    pr.save()
            
            try:
                payment = reservation.payment
                payment.status = 'COMPLETED'
                payment.completed_at = timezone.now()
                payment.transaction_id = f"AMADEUS-{booking_result['pnr']}"
                payment.save()
            except Payment.DoesNotExist:
                pass
            
            return Response({
                'message': 'Réservation confirmée avec succès',
                'reservation': ReservationSerializer(reservation).data,
                'pnr': booking_result['pnr']
            })
            
        except Exception as e:
            logger.error(f"Error booking with Amadeus: {str(e)}", exc_info=True)
            
            reservation.status = 'FAILED'
            reservation.save()
            
            return Response(
                {'error': f'Erreur lors de la réservation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def booking_status(self, request, pk=None):
        """Check booking status with Amadeus"""
        reservation = self.get_object()
        
        if not reservation.amadeus_pnr:
            return Response(
                {'error': 'Pas de réservation Amadeus associée'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            booking_data = self.amadeus_service.client.get_booking(reservation.amadeus_pnr)
            
            if booking_data:
                return Response({
                    'pnr': reservation.amadeus_pnr,
                    'status': booking_data.get('flightOffers', [{}])[0].get('status'),
                    'data': booking_data
                })
            else:
                return Response(
                    {'error': 'Impossible de récupérer le statut'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"Error checking booking status: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Erreur lors de la vérification: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def cancel_booking(self, request, pk=None):
        """Cancel a confirmed booking with Amadeus"""
        reservation = self.get_object()
        
        if reservation.status != 'CONFIRMED':
            return Response(
                {'error': 'Seules les réservations confirmées peuvent être annulées'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not reservation.amadeus_pnr:
            return Response(
                {'error': 'Pas de réservation Amadeus associée'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cancelled = self.amadeus_service.client.cancel_booking(reservation.amadeus_pnr)
            
            if cancelled:
                reservation.status = 'CANCELLED'
                reservation.save()
                
                try:
                    payment = reservation.payment
                    payment.status = 'REFUNDED'
                    payment.save()
                except Payment.DoesNotExist:
                    pass
                
                return Response({
                    'message': 'Réservation annulée avec succès',
                    'reservation': ReservationSerializer(reservation).data
                })
            else:
                return Response(
                    {'error': 'Échec de l\'annulation'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"Error cancelling booking: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Erreur lors de l\'annulation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Test endpoint
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_auth(request):
    """Test endpoint to verify authentication"""
    user = request.user
    return Response({
        'authenticated': True,
        'user_id': user.id,
        'email': getattr(user, 'email', None),
        'voyageur_id': getattr(user, 'voyageur_id', None),
    })