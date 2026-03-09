from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime, timedelta, date
import logging
import re
from typing import List, Dict, Optional
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
        self.auth_client = None

    def get_auth_client(self):
        if not self.auth_client:
            self.auth_client = AuthServiceClient(self.request)
        return self.auth_client
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ReservationListSerializer
        return ReservationSerializer
    
    def get_queryset(self):
        """Filter reservations by current voyageur"""
        user = self.request.user
        
        if hasattr(user, 'voyageur_id') and user.voyageur_id:
            logger.info(f"Filtering reservations for voyageur_id: {user.voyageur_id}")
            return Reservation.objects.filter(voyageur=user.voyageur_id)
        
        auth_client = self.get_auth_client()
        voyageur_data = auth_client.get_voyageur_by_user_id(user.id)
        
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
        logger.info(f"Creating reservation with data: {request.data}")
        
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
        auth_client = self.get_auth_client()
        
        try:
            voyageur_id = None
            
            if hasattr(user, 'voyageur_id') and user.voyageur_id:
                voyageur_id = user.voyageur_id
                logger.info(f"Using voyageur_id {voyageur_id} from authenticated user")
            else:
                voyageur_data = auth_client.get_voyageur_by_user_id(user.id)
                if voyageur_data:
                    voyageur_id = voyageur_data.get('id')
                    logger.info(f"Fetched voyageur_id {voyageur_id} from auth service")
            
            if not voyageur_id:
                return Response(
                    {'error': 'Voyageur non trouvé'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            total_price = sum(
                flight['price']['total'] for flight in data['selected_flights']
            )
            
            reservation = Reservation.objects.create(
                voyageur=voyageur_id,
                trip_type=data['trip_type'],
                search_params=data['search_params'],
                total_price=total_price,
                currency=data['selected_flights'][0]['price']['currency'],
                status='PENDING_PRICE',
                original_offer=data['selected_flights'][0]
            )
            
            for idx, flight in enumerate(data['selected_flights'], 1):
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
            
            passenger_ids = list(data.get('existing_passenger_ids', []))
            
            for passenger_data in data.get('passengers', []):
                allowed_fields = [
                    "nom", "prenom", "date_naissance", "sexe",
                    "num_passport", "date_exp_passport"
                ]
                
                passenger_data_for_api = {
                    key: passenger_data[key]
                    for key in allowed_fields
                    if key in passenger_data
                }
                
                passenger_data_for_api["voyageur"] = voyageur_id
                
                if 'date_naissance' in passenger_data_for_api:
                    if isinstance(passenger_data_for_api['date_naissance'], date):
                        passenger_data_for_api['date_naissance'] = passenger_data_for_api['date_naissance'].isoformat()
                
                if 'date_exp_passport' in passenger_data_for_api and passenger_data_for_api['date_exp_passport']:
                    if isinstance(passenger_data_for_api['date_exp_passport'], date):
                        passenger_data_for_api['date_exp_passport'] = passenger_data_for_api['date_exp_passport'].isoformat()
                
                logger.info(f"Sending passenger data to auth service: {passenger_data_for_api}")
                
                created_passenger = auth_client.create_passenger(
                    passenger_data_for_api,
                    voyageur_id
                )
                
                if created_passenger:
                    passenger_ids.append(created_passenger['id'])
                    logger.info(f"Successfully created passenger with ID: {created_passenger['id']}")
                else:
                    logger.error(f"Failed to create passenger: {passenger_data_for_api}")
            
            if not passenger_ids:
                return Response(
                    {'error': 'Aucun passager valide n\'a pu être créé'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            for passenger_id in passenger_ids:
                price_paid = total_price / len(passenger_ids) if passenger_ids else 0
                baggage_quantity = data['selected_flights'][0].get('baggage', {}).get('quantity', 0)
                
                PassengerReservation.objects.create(
                    reservation=reservation,
                    passenger=passenger_id,
                    price_paid=price_paid,
                    baggage_quantity=baggage_quantity
                )
            
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

    def _get_valid_amadeus_offer(self, reservation: Reservation) -> Optional[Dict]:
        """Récupère une offre Amadeus valide"""
        try:
            search_params = reservation.search_params
            currency = 'DZD'
            
            amadeus_params = {
                'originLocationCode': search_params.get('origin'),
                'destinationLocationCode': search_params.get('destination'),
                'departureDate': search_params.get('departureDate'),
                'adults': search_params.get('adults', 1),
                'children': search_params.get('children', 0),
                'infants': search_params.get('infants', 0),
                'travelClass': search_params.get('travelClass', 'ECONOMY'),
                'currencyCode': currency,
                'max': 10
            }
            
            if reservation.trip_type == 'ALLER_RETOUR' and search_params.get('returnDate'):
                amadeus_params['returnDate'] = search_params.get('returnDate')
            
            logger.info(f"Searching for fresh Amadeus offers with params: {amadeus_params}")
            
            fresh_offers = self.amadeus_service.client.search_flights(amadeus_params)
            
            if not fresh_offers:
                logger.warning("No offers found in Amadeus search")
                return None
            
            logger.info(f"Found {len(fresh_offers)} offers from Amadeus")
            return fresh_offers[0]
            
        except Exception as e:
            logger.error(f"Error getting valid Amadeus offer: {e}")
            return None

    @action(detail=True, methods=['post'])
    def confirm_price(self, request, pk=None):
        """Step 2: Confirm price with Amadeus"""
        reservation = self.get_object()
        
        if reservation.status not in ['PENDING_PRICE', 'FAILED']:
            return Response(
                {'error': 'Cette réservation ne peut pas être confirmée'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amadeus_offer = self._get_valid_amadeus_offer(reservation)
            
            if not amadeus_offer:
                return Response(
                    {
                        'error': 'Aucun vol disponible pour ces critères',
                        'action': 'RECHERCHER_NOUVEAU_VOL',
                        'message': 'Veuillez effectuer une nouvelle recherche de vols'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            logger.info(f"Using Amadeus offer: {amadeus_offer.get('id')}")
            
            confirmed_offer = self.amadeus_service.client.confirm_flight_offer(amadeus_offer)
            
            if not confirmed_offer:
                return Response(
                    {
                        'error': 'Impossible de confirmer le prix',
                        'action': 'RECHERCHER_NOUVEAU_VOL',
                        'message': 'Veuillez réessayer'
                    },
                    status=status.HTTP_409_CONFLICT
                )
            
            new_price = float(confirmed_offer.get('flightOffers', [{}])[0]
                            .get('price', {})
                            .get('grandTotal', 0))
            
            currency = confirmed_offer.get('flightOffers', [{}])[0] \
                                  .get('price', {}) \
                                  .get('currency', 'DZD')
            
            logger.info(f"New price confirmed: {new_price} {currency}")
            
            price_confirmation = PriceConfirmation.objects.create(
                reservation=reservation,
                offered_price=reservation.total_price,
                confirmed_price=new_price,
                currency=currency,
                confirmed_offer=confirmed_offer,
                expires_at=timezone.now() + timedelta(minutes=5)
            )
            
            reservation.status = 'PRICE_CONFIRMED'
            reservation.last_confirmed_price = new_price
            reservation.price_confirmed_at = timezone.now()
            reservation.confirmed_offer = confirmed_offer
            reservation.expiry_date = price_confirmation.expires_at
            reservation.total_price = new_price
            reservation.currency = currency
            reservation.save()
            
            try:
                payment = reservation.payment
                payment.amount = new_price
                payment.currency = currency
                payment.save()
                logger.info(f"Payment amount updated to {new_price} {currency}")
            except Payment.DoesNotExist:
                logger.warning("No payment found for reservation")
            
            return Response({
                'message': 'Prix confirmé avec succès',
                'reservation': ReservationSerializer(reservation).data,
                'price_confirmation': PriceConfirmationSerializer(price_confirmation).data,
                'warning': 'Cette confirmation expire dans 5 minutes'
            })
            
        except Exception as e:
            logger.error(f"Error confirming price: {str(e)}", exc_info=True)
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Erreur lors de la confirmation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def book(self, request, pk=None):
     """Step 3: Book with Amadeus after price confirmation"""
     reservation = self.get_object()
     auth_client = self.get_auth_client()
    
     logger.info(f"Booking attempt for reservation {reservation.id} with status: {reservation.status}")
    
     if reservation.status == 'FAILED':
        return Response(
            {
                'error': 'Cette réservation a échoué précédemment',
                'action': 'RECONFIRMER_PRIX'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
     if reservation.status != 'PRICE_CONFIRMED':
        return Response(
            {
                'error': f'Statut invalide: {reservation.status}',
                'expected': 'PRICE_CONFIRMED'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
     latest_confirmation = reservation.price_confirmations.last()
    
     if not latest_confirmation or not latest_confirmation.is_valid():
        reservation.status = 'EXPIRED'
        reservation.save()
        return Response(
            {'error': 'La confirmation de prix a expiré'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
     try:
        passengers_data = []
        for pr in reservation.passenger_reservations.all():
            passenger_data = auth_client.get_passenger(pr.passenger)
            if passenger_data:
                voyageur_data = auth_client.get_voyageur_by_id(reservation.voyageur)
                if voyageur_data:
                    passenger_data['email'] = voyageur_data.get('user', {}).get('email')
                    passenger_data['telephone'] = voyageur_data.get('telephone')
                passengers_data.append(passenger_data)
        
        if not passengers_data:
            return Response(
                {'error': 'Aucun passager trouvé'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Effectuer la réservation
        booking_result = self.amadeus_service.process_reservation(
            reservation.confirmed_offer,
            passengers_data
        )
        
        # Nettoyer le PNR
        import re
        clean_pnr = re.sub(r'[^A-Za-z0-9]', '', str(booking_result['pnr']))[:50]
        
        # Mettre à jour la réservation
        reservation.status = 'CONFIRMED'
        reservation.amadeus_pnr = clean_pnr
        reservation.amadeus_booking_data = booking_result['booking']
        reservation.confirmation_date = timezone.now()
        reservation.save()
        
        # Mettre à jour les IDs des voyageurs
        travelers = booking_result['booking'].get('travelers', [])
        for idx, pr in enumerate(reservation.passenger_reservations.all()):
            if idx < len(travelers):
                pr.amadeus_traveler_id = travelers[idx].get('id')
                pr.save()
        
        # Mettre à jour le paiement
        try:
            payment = reservation.payment
            payment.status = 'COMPLETED'
            payment.completed_at = timezone.now()
            payment.transaction_id = f"AMADEUS-{clean_pnr}"
            payment.save()
        except Payment.DoesNotExist:
            pass
        
        # === RÉPONSE MINIMALISTE ===
        first_segment = reservation.flight_segments.first()
        
        response_data = {
            'message': 'Réservation confirmée avec succès',
            'pnr': clean_pnr,
            'status': reservation.status,
            'payment_status': 'COMPLETED',
            'total_price': f"{reservation.total_price} {reservation.currency}",
            'passengers': len(passengers_data),
            'flight': {
                'origin': first_segment.origin,
                'destination': first_segment.destination,
                'date': str(first_segment.departure_date),
                'time': str(first_segment.departure_time)
            }
        }
        
        # Ajouter le vol retour si c'est un aller-retour
        if reservation.trip_type == 'ALLER_RETOUR' and reservation.flight_segments.count() > 1:
            last_segment = reservation.flight_segments.last()
            response_data['return_flight'] = {
                'origin': last_segment.origin,
                'destination': last_segment.destination,
                'date': str(last_segment.departure_date),
                'time': str(last_segment.departure_time)
            }
        
        return Response(response_data)
        
     except Exception as e:
        logger.error(f"Error booking: {str(e)}", exc_info=True)
        reservation.status = 'FAILED'
        reservation.save()
        return Response(
            {'error': 'Erreur lors de la réservation'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) 
     
    @action(detail=True, methods=['post'])
    def retry_failed(self, request, pk=None):
        """Réessayer une réservation qui a échoué"""
        reservation = self.get_object()
        
        if reservation.status != 'FAILED':
            return Response(
                {'error': f'Cette réservation n\'est pas en échec (statut: {reservation.status})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reservation.status = 'PENDING_PRICE'
        reservation.save()
        
        return Response({
            'message': 'Réservation remise en attente. Veuillez confirmer le prix.',
            'reservation': ReservationSerializer(reservation).data,
            'action': 'CONFIRMER_PRIX'
        })
    
    def _parse_flight_offers(self, offers_data: List[Dict]) -> List[Dict]:
        """Parse raw Amadeus flight offers"""
        parsed_offers = []
        
        for offer in offers_data[:10]:
            try:
                itinerary = offer['itineraries'][0]
                segment = itinerary['segments'][0]
                
                price = float(offer['price']['total'])
                
                total_passengers = 0
                for tp in offer['travelerPricings']:
                    if tp['travelerType'] in ['ADULT', 'CHILD', 'INFANT']:
                        total_passengers += 1
                
                per_passenger_price = price / total_passengers if total_passengers > 0 else price
                
                baggage_info = {'quantity': 0, 'included': 'Non spécifié'}
                for traveler_pricing in offer.get('travelerPricings', []):
                    for fare_detail in traveler_pricing.get('fareDetailsBySegment', []):
                        if 'includedCheckedBags' in fare_detail:
                            quantity = fare_detail['includedCheckedBags'].get('quantity', 0)
                            baggage_info = {
                                'quantity': quantity,
                                'included': f"{quantity} bagage(s)" if quantity > 0 else "Non inclus"
                            }
                            break
                
                is_refundable = any(
                    tp['fareDetailsBySegment'][0].get('isRefundable', False)
                    for tp in offer['travelerPricings']
                )
                
                flight_offer = {
                    'flight_id': offer['id'],
                    'airline': segment['carrierCode'],
                    'flightNumber': segment['number'],
                    'departure': {
                        'airport': segment['departure']['iataCode'],
                        'time': segment['departure']['at'],
                        'terminal': segment['departure'].get('terminal', '')
                    },
                    'arrival': {
                        'airport': segment['arrival']['iataCode'],
                        'time': segment['arrival']['at'],
                        'terminal': segment['arrival'].get('terminal', '')
                    },
                    'duration': self._format_duration(itinerary['duration']),
                    'segments': [
                        {
                            'departure': {
                                'airport': seg['departure']['iataCode'],
                                'time': seg['departure']['at']
                            },
                            'arrival': {
                                'airport': seg['arrival']['iataCode'],
                                'time': seg['arrival']['at']
                            },
                            'airline': seg['carrierCode'],
                            'flightNumber': seg['number'],
                            'aircraft': seg['aircraft']['code'],
                            'duration': seg['duration']
                        }
                        for seg in itinerary['segments']
                    ],
                    'price': {
                        'total': price,
                        'currency': offer['price']['currency'],
                        'perPassenger': per_passenger_price
                    },
                    'baggage': baggage_info,
                    'refundable': {
                        'isRefundable': is_refundable,
                        'policy': 'Remboursable' if is_refundable else 'Non remboursable'
                    },
                    'seatsAvailable': offer.get('numberOfBookableSeats', 0)
                }
                
                parsed_offers.append(flight_offer)
                
            except Exception as e:
                logger.error(f"Error parsing flight offer: {e}")
                continue
        
        return parsed_offers
    
    def _format_duration(self, duration: str) -> str:
        """Format ISO 8601 duration to human readable format"""
        try:
            duration = duration.replace('PT', '')
            
            hours = 0
            minutes = 0
            
            if 'H' in duration:
                hours_part = duration.split('H')[0]
                hours = int(hours_part)
                duration = duration.split('H')[1] if 'H' in duration else ''
            
            if 'M' in duration:
                minutes_part = duration.split('M')[0]
                minutes = int(minutes_part)
            
            if hours > 0 and minutes > 0:
                return f"{hours}h {minutes}min"
            elif hours > 0:
                return f"{hours}h"
            elif minutes > 0:
                return f"{minutes}min"
            else:
                return duration
        except:
            return duration
    
    def _update_reservation_flight(self, reservation, new_flight_data):
        """Update reservation with new flight data"""
        try:
            flight_segment = reservation.flight_segments.first()
            
            departure_time_str = new_flight_data['departure']['time'].replace('Z', '+00:00')
            arrival_time_str = new_flight_data['arrival']['time'].replace('Z', '+00:00')
            
            departure_datetime = datetime.fromisoformat(departure_time_str)
            arrival_datetime = datetime.fromisoformat(arrival_time_str)
            
            flight_segment.flight_data = new_flight_data
            flight_segment.price = new_flight_data['price']['total']
            flight_segment.per_passenger_price = new_flight_data['price']['perPassenger']
            flight_segment.departure_date = departure_datetime.date()
            flight_segment.departure_time = departure_datetime.time()
            flight_segment.arrival_date = arrival_datetime.date()
            flight_segment.arrival_time = arrival_datetime.time()
            flight_segment.save()
            
            logger.info(f"Updated reservation {reservation.id} with new flight data")
            
        except Exception as e:
            logger.error(f"Error updating reservation flight: {e}")
            raise
    
    @action(detail=True, methods=['post'])
    def select_alternative_flight(self, request, pk=None):
        """Select an alternative flight when the original is unavailable"""
        reservation = self.get_object()
        
        if reservation.status not in ['PENDING_PRICE', 'FAILED']:
            return Response(
                {'error': 'Cette réservation ne peut pas être modifiée'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        new_flight_data = request.data.get('flight')
        if not new_flight_data:
            return Response(
                {'error': 'Nouveau vol non fourni'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            self._update_reservation_flight(reservation, new_flight_data)
            
            reservation.original_offer = new_flight_data
            reservation.total_price = new_flight_data['price']['total']
            reservation.currency = new_flight_data['price']['currency']
            reservation.status = 'PENDING_PRICE'
            reservation.save()
            
            try:
                payment = reservation.payment
                payment.amount = new_flight_data['price']['total']
                payment.currency = new_flight_data['price']['currency']
                payment.save()
            except Payment.DoesNotExist:
                pass
            
            return Response({
                'message': 'Vol mis à jour avec succès. Veuillez confirmer le prix.',
                'reservation': ReservationSerializer(reservation).data,
                'action': 'CONFIRMER_PRIX'
            })
            
        except Exception as e:
            logger.error(f"Error selecting alternative flight: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Erreur lors de la sélection: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def booking_status(self, request, pk=None):
     """Check booking status with Amadeus - Version simplifiée"""
     reservation = self.get_object()
    
     if not reservation.amadeus_pnr:
        return Response(
            {'error': 'Pas de réservation Amadeus associée'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
     try:
        booking_data = self.amadeus_service.client.get_booking(reservation.amadeus_pnr)
        
        if not booking_data:
            return Response(
                {'error': 'Réservation introuvable chez Amadeus'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Extraire les informations essentielles
        flight_offer = booking_data.get('flightOffers', [{}])[0]
        first_segment = flight_offer.get('itineraries', [{}])[0].get('segments', [{}])[0]
        
        # Statut réel du vol
        flight_status = first_segment.get('bookingStatus', 'UNKNOWN')
        
        # Prix
        price = flight_offer.get('price', {})
        
        # Réponse minimaliste
        return Response({
            'pnr': reservation.amadeus_pnr,
            'status': flight_status,
            'total_price': f"{price.get('grandTotal', '0')} {price.get('currency', 'DZD')}",
            'flight': {
                'from': first_segment.get('departure', {}).get('iataCode'),
                'to': first_segment.get('arrival', {}).get('iataCode'),
                'date': first_segment.get('departure', {}).get('at', '').split('T')[0],
                'time': first_segment.get('departure', {}).get('at', '').split('T')[1] if 'T' in first_segment.get('departure', {}).get('at', '') else '',
                'airline': first_segment.get('carrierCode'),
                'flight_number': first_segment.get('number')
            },
            'passengers': len(booking_data.get('travelers', []))
        })
        
     except Exception as e:
        logger.error(f"Error checking booking status: {str(e)}", exc_info=True)
        return Response(
            {'error': 'Erreur lors de la vérification'},
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