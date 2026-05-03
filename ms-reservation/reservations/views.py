from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime, timedelta, date
import logging
from typing import List, Dict, Optional
from .models import Reservation, FlightSegment, Payment, PriceConfirmation, PassengerReservation
from .serializers import *
from .services import AuthServiceClient
from .skyscanner_booking import skyscanner_booking_service
from .authentication import AuthServiceJWTAuthentication
from django.http import HttpResponse
from .skyscanner_booking import skyscanner_booking_service  # Use only skyscanner

logger = logging.getLogger(__name__)


class ReservationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing reservations with Skyscanner integration"""
    queryset = Reservation.objects.all()
    authentication_classes = [AuthServiceJWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_client = None

    def get_auth_client(self):
        if not self.auth_client:
            self.auth_client = AuthServiceClient(self.request)
        return self.auth_client
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ReservationListSerializer
        return ReservationSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['auth_client'] = self.get_auth_client()
        return context
    
    def list(self, request, *args, **kwargs):
        request.META['auth_client'] = self.get_auth_client()
        return super().list(request, *args, **kwargs)
    
    def get_queryset(self):
        user = self.request.user
        is_admin = False
        
        if hasattr(user, 'is_staff') and user.is_staff:
            is_admin = True
        elif hasattr(user, 'is_superuser') and user.is_superuser:
            is_admin = True
        elif hasattr(user, 'role') and user.role == 'admin':
            is_admin = True
        
        if is_admin:
            logger.info(f"Admin user {user.id} fetching all reservations")
            return Reservation.objects.all().order_by('-created_at')
        
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
        """Step 1: Create reservation with Skyscanner flight data"""
        logger.info(f"Creating reservation with data: {request.data}")

        passengers_count = (
            len(request.data.get('passengers', [])) +
            len(request.data.get('existing_passenger_ids', []))
        )

        serializer = ReservationRequestSerializer(
            data=request.data,
            context={'passengers_count': max(passengers_count, 1)}
        )

        if not serializer.is_valid():
            logger.error(f"Validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user
        auth_client = self.get_auth_client()

        try:
            # Resolve voyageur_id
            voyageur_id = None
            voyageur_profile = None

            if hasattr(user, 'voyageur_id') and user.voyageur_id:
                voyageur_id = user.voyageur_id
            else:
                voyageur_profile = auth_client.get_voyageur_by_user_id(user.id)
                if voyageur_profile:
                    voyageur_id = voyageur_profile.get('id')

            if not voyageur_id:
                return Response(
                    {'error': 'Voyageur non trouvé'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Build passenger ID list
            explicit_new = data.get('passengers', [])
            existing_ids = list(data.get('existing_passenger_ids', []))
            total_passengers = len(explicit_new) + len(existing_ids)

            passenger_ids = []

            if total_passengers == 0:
                # Solo booking
                if voyageur_profile is None:
                    voyageur_profile = auth_client.get_voyageur_by_id(voyageur_id)

                if not voyageur_profile:
                    return Response(
                        {'error': 'Impossible de récupérer le profil voyageur'},
                        status=status.HTTP_404_NOT_FOUND
                    )

                passenger_payload = {
                    'nom': voyageur_profile.get('nom', ''),
                    'prenom': voyageur_profile.get('prenom', ''),
                    'date_naissance': voyageur_profile.get('date_naissance', ''),
                    'sexe': voyageur_profile.get('sexe', 'homme'),
                    'num_passport': voyageur_profile.get('num_passport', ''),
                    'date_exp_passport': voyageur_profile.get('date_exp_passport'),
                    'voyageur': voyageur_id,
                }

                passenger_payload = {k: v for k, v in passenger_payload.items() if v}
                passenger_payload['voyageur'] = voyageur_id

                created = auth_client.create_passenger(passenger_payload, voyageur_id)
                if not created:
                    return Response(
                        {'error': 'Impossible de créer le passager depuis le profil voyageur'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                passenger_ids.append(created['id'])
                logger.info(f"Solo booking — created passenger {created['id']}")

            else:
                # Multi-passenger booking
                passenger_ids.extend(existing_ids)

                for pdata in explicit_new:
                    allowed = [
                        'nom', 'prenom', 'date_naissance', 'sexe',
                        'num_passport', 'date_exp_passport',
                    ]
                    payload = {k: pdata[k] for k in allowed if k in pdata}
                    if isinstance(payload.get('date_naissance'), date):
                        payload['date_naissance'] = payload['date_naissance'].isoformat()
                    if isinstance(payload.get('date_exp_passport'), date):
                        payload['date_exp_passport'] = payload['date_exp_passport'].isoformat()

                    created = auth_client.create_passenger(payload, voyageur_id)
                    if created:
                        passenger_ids.append(created['id'])
                        logger.info(f"Created passenger {created['id']}")
                    else:
                        logger.error(f"Failed to create passenger: {payload}")

                if not passenger_ids:
                    return Response(
                        {'error': 'Aucun passager valide n\'a pu être créé'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Create reservation
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

            # Flight segments
            for idx, flight in enumerate(data['selected_flights'], 1):
                FlightSegment.objects.create(
                    reservation=reservation,
                    segment_number=idx,
                    origin=flight['departure']['airport'],
                    destination=flight['arrival']['airport'],
                    departure_date=datetime.strptime(flight['departure']['time'][:10], '%Y-%m-%d').date(),
                    departure_time=datetime.strptime(flight['departure']['time'][11:16], '%H:%M').time(),
                    arrival_date=datetime.strptime(flight['arrival']['time'][:10], '%Y-%m-%d').date(),
                    arrival_time=datetime.strptime(flight['arrival']['time'][11:16], '%H:%M').time(),
                    flight_data=flight,
                    price=flight['price']['total'],
                    per_passenger_price=flight['price']['perPassenger'] or flight['price']['total']
                )

            # PassengerReservation links
            price_per_pax = total_price / len(passenger_ids)
            baggage_qty = data['selected_flights'][0].get('baggage', {}).get('quantity', 0)

            for pid in passenger_ids:
                PassengerReservation.objects.create(
                    reservation=reservation,
                    passenger=pid,
                    price_paid=price_per_pax,
                    baggage_quantity=baggage_qty
                )

            # Payment
            Payment.objects.create(
                reservation=reservation,
                amount=total_price,
                currency=reservation.currency,
                payment_method=data['payment_method']
            )

            return Response(
                ReservationSerializer(reservation).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"Error creating reservation: {e}", exc_info=True)
            return Response(
                {'error': f'Erreur lors de la création: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def confirm_price(self, request, pk=None):
        """Step 2: Confirm price for Skyscanner booking"""
        reservation = self.get_object()
        
        if reservation.status not in ['PENDING_PRICE', 'FAILED']:
            return Response(
                {'error': 'Cette réservation ne peut pas être confirmée'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            original_flight = reservation.original_offer
            
            if not original_flight:
                return Response(
                    {
                        'error': 'Aucune donnée de vol disponible',
                        'action': 'RECHERCHER_NOUVEAU_VOL',
                        'message': 'Veuillez effectuer une nouvelle recherche de vols'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            new_price = float(reservation.total_price)
            currency = reservation.currency
            
            logger.info(f"Price confirmed for Skyscanner booking: {new_price} {currency}")
            
            price_confirmation = PriceConfirmation.objects.create(
                reservation=reservation,
                offered_price=reservation.total_price,
                confirmed_price=new_price,
                currency=currency,
                confirmed_offer=reservation.original_offer,
                expires_at=timezone.now() + timedelta(minutes=30)
            )
            
            reservation.status = 'PRICE_CONFIRMED'
            reservation.last_confirmed_price = new_price
            reservation.price_confirmed_at = timezone.now()
            reservation.confirmed_offer = reservation.original_offer
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
                'warning': 'Cette confirmation expire dans 30 minutes'
            })
            
        except Exception as e:
            logger.error(f"Error confirming price: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Erreur lors de la confirmation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def book(self, request, pk=None):
        """Step 3: Create booking with Skyscanner (simulated)"""
        reservation = self.get_object()
        auth_client = self.get_auth_client()

        if reservation.status == 'FAILED':
            return Response({
                'error': 'Cette réservation a échoué précédemment',
                'action': 'RECONFIRMER_PRIX'
            }, status=status.HTTP_400_BAD_REQUEST)

        if reservation.status != 'PRICE_CONFIRMED':
            return Response({
                'error': f'Statut invalide: {reservation.status}',
                'expected': 'PRICE_CONFIRMED'
            }, status=status.HTTP_400_BAD_REQUEST)

        latest_confirmation = reservation.price_confirmations.last()
        if not latest_confirmation or not latest_confirmation.is_valid():
            reservation.status = 'EXPIRED'
            reservation.save()
            return Response({
                'error': 'La confirmation de prix a expiré',
                'action': 'NOUVELLE_RECHERCHE'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            pr_list = list(reservation.passenger_reservations.all())

            # Get voyageur contact info
            voyageur_data = auth_client.get_voyageur_by_id(reservation.voyageur)
            contact = {
                'email': (voyageur_data.get('user', {}) or {}).get('email') if voyageur_data else None,
                'telephone': voyageur_data.get('telephone') if voyageur_data else None,
            }

            # Get passengers data
            passenger_ids = [pr.passenger for pr in pr_list]
            passengers_by_id = auth_client.get_passengers_bulk(passenger_ids)

            passengers_data = []
            for pr in pr_list:
                p = passengers_by_id.get(pr.passenger)
                if p:
                    p['email'] = contact['email']
                    p['telephone'] = contact['telephone']
                    passengers_data.append(p)

            if not passengers_data:
                return Response(
                    {'error': 'Aucun passager trouvé'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create booking with Skyscanner
            booking_result = skyscanner_booking_service.create_booking_reference(
                reservation.confirmed_offer or reservation.original_offer,
                passengers_data
            )

            clean_pnr = booking_result.get('id', f"SKY-{reservation.id}")

            # Update reservation
            reservation.status = 'CONFIRMED'
            reservation.amadeus_pnr = clean_pnr
            reservation.amadeus_booking_data = booking_result
            reservation.confirmation_date = timezone.now()
            reservation.save()

            # Update payment
            try:
                payment = reservation.payment
                payment.status = 'COMPLETED'
                payment.completed_at = timezone.now()
                payment.transaction_id = f"SKYSCANNER-{clean_pnr}"
                payment.save()
            except Payment.DoesNotExist:
                pass

            first_segment = reservation.flight_segments.first()
            response_data = {
                'message': 'Réservation confirmée avec succès',
                'pnr': clean_pnr,
                'status': reservation.status,
                'payment_status': 'COMPLETED',
                'total_price': f"{reservation.total_price} {reservation.currency}",
                'passengers': len(passengers_data),
                'booking_url': booking_result.get('booking_url'),
                'flight': {
                    'origin': first_segment.origin,
                    'destination': first_segment.destination,
                    'date': str(first_segment.departure_date),
                    'time': str(first_segment.departure_time),
                }
            }

            if reservation.trip_type == 'ALLER_RETOUR' and reservation.flight_segments.count() > 1:
                last_segment = reservation.flight_segments.last()
                response_data['return_flight'] = {
                    'origin': last_segment.origin,
                    'destination': last_segment.destination,
                    'date': str(last_segment.departure_date),
                    'time': str(last_segment.departure_time),
                }

            return Response(response_data)

        except Exception as e:
            logger.error(f"Error booking: {e}", exc_info=True)
            reservation.status = 'FAILED'
            reservation.save()
            return Response({
                'error': f'Erreur lors de la réservation: {str(e)}',
                'action': 'RESEARCH'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
    
    @action(detail=True, methods=['post'])
    def cancel_booking(self, request, pk=None):
        """Cancel a confirmed booking in Skyscanner (simulated)"""
        reservation = self.get_object()
        
        if reservation.status != 'CONFIRMED':
            return Response(
                {'error': 'Seules les réservations confirmées peuvent être annulées'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not reservation.amadeus_pnr:
            return Response(
                {'error': 'Pas de PNR associé à cette réservation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if flight hasn't departed
        first_segment = reservation.flight_segments.first()
        if first_segment and first_segment.departure_date < timezone.now().date():
            return Response(
                {'error': 'Impossible d\'annuler un vol déjà effectué'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Cancel in Skyscanner
            cancelled = skyscanner_booking_service.cancel_booking(reservation.amadeus_pnr)
            
            if cancelled:
                reservation.status = 'CANCELLED'
                reservation.save()
                
                try:
                    payment = reservation.payment
                    payment.status = 'REFUND_PENDING'
                    payment.save()
                except Payment.DoesNotExist:
                    pass
                
                return Response({
                    'success': True,
                    'message': 'Réservation annulée avec succès',
                    'reservation_id': reservation.id,
                    'reservation_number': reservation.reservation_number,
                    'pnr': reservation.amadeus_pnr,
                    'new_status': reservation.status,
                    'payment_status': 'REFUND_PENDING',
                    'next_step': 'Pour obtenir un remboursement, veuillez faire une demande de remboursement.'
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
    
    @action(detail=False, methods=['get'], url_path='my-reservations')
    def my_reservations(self, request):
        """Get current user's own reservations with full details"""
        logger.info(f"Fetching my reservations for user: {request.user.id}")
        
        user = request.user
        auth_client = self.get_auth_client()
        
        try:
            voyageur_id = None
            
            if hasattr(user, 'voyageur_id') and user.voyageur_id:
                voyageur_id = user.voyageur_id
            else:
                voyageur_data = auth_client.get_voyageur_by_user_id(user.id)
                if voyageur_data:
                    voyageur_id = voyageur_data.get('id')
            
            if not voyageur_id:
                return Response(
                    {'error': 'Aucun profil voyageur trouvé'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            reservations = Reservation.objects.filter(voyageur=voyageur_id)\
                .prefetch_related('flight_segments', 'passenger_reservations', 'payment')\
                .order_by('-created_at')
            
            request.META['auth_client'] = auth_client
            
            serializer = ReservationDetailSerializer(
                reservations, 
                many=True, 
                context={'request': request}
            )
            
            total_spent = sum(float(r.total_price) for r in reservations)
            confirmed_count = reservations.filter(status='CONFIRMED').count()
            cancelled_count = reservations.filter(status='CANCELLED').count()
            upcoming_count = reservations.filter(
                status='CONFIRMED',
                flight_segments__departure_date__gte=timezone.now().date()
            ).distinct().count()
            
            voyageur_details = auth_client.get_voyageur_by_id(voyageur_id)
            
            response_data = {
                'voyageur': {
                    'id': voyageur_id,
                    'nom': voyageur_details.get('nom') if voyageur_details else None,
                    'prenom': voyageur_details.get('prenom') if voyageur_details else None,
                },
                'statistics': {
                    'total_reservations': reservations.count(),
                    'total_spent': f"{total_spent:.2f} DZD",
                    'confirmed': confirmed_count,
                    'cancelled': cancelled_count,
                    'upcoming': upcoming_count
                },
                'reservations': serializer.data
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching my reservations: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Erreur lors de la récupération: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def request_refund(self, request, pk=None):
        """Request a refund for a cancelled reservation"""
        reservation = self.get_object()
        reason = request.data.get('reason', '')
        
        if reservation.status != 'CANCELLED':
            return Response(
                {'error': 'Seules les réservations annulées peuvent être remboursées'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            payment = reservation.payment
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Aucun paiement trouvé pour cette réservation'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if payment.status == 'REFUNDED':
            return Response(
                {'error': 'Cette réservation a déjà été remboursée'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Calculate refund amount
            cancellation_fee_percentage = 10
            refund_amount = float(payment.amount) * (100 - cancellation_fee_percentage) / 100
            refund_transaction_id = f"REFUND-{reservation.reservation_number}-{int(timezone.now().timestamp())}"
            
            payment.status = 'REFUNDED'
            payment.completed_at = timezone.now()
            payment.transaction_id = refund_transaction_id
            payment.save()
            
            return Response({
                'success': True,
                'message': 'Demande de remboursement traitée avec succès',
                'reservation_id': reservation.id,
                'reservation_number': reservation.reservation_number,
                'original_amount': float(payment.amount),
                'refund_amount': refund_amount,
                'cancellation_fee': float(payment.amount) - refund_amount,
                'currency': payment.currency,
                'transaction_id': refund_transaction_id,
                'status': payment.status
            })
            
        except Exception as e:
            logger.error(f"Error processing refund: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Erreur lors du remboursement: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def get_refund_eligibility(self, request, pk=None):
        """Check if a reservation is eligible for refund"""
        reservation = self.get_object()
        
        try:
            payment = reservation.payment
        except Payment.DoesNotExist:
            return Response({
                'eligible': False,
                'reason': 'Aucun paiement trouvé'
            })
        
        is_eligible = False
        reason = None
        refund_percentage = 0
        
        if reservation.status == 'CONFIRMED':
            is_eligible = True
            reason = 'Réservation confirmée - Annulation possible'
            
            first_segment = reservation.flight_segments.first()
            if first_segment:
                days_until_departure = (first_segment.departure_date - timezone.now().date()).days
                
                if days_until_departure > 30:
                    refund_percentage = 100
                    reason = 'Annulation plus de 30 jours avant départ - Remboursement total'
                elif days_until_departure > 14:
                    refund_percentage = 75
                    reason = 'Annulation entre 15-30 jours avant départ - Remboursement 75%'
                elif days_until_departure > 7:
                    refund_percentage = 50
                    reason = 'Annulation entre 8-14 jours avant départ - Remboursement 50%'
                elif days_until_departure > 0:
                    refund_percentage = 25
                    reason = 'Annulation moins de 7 jours avant départ - Remboursement 25%'
                else:
                    reason = 'Vol déjà effectué - Non remboursable'
                    is_eligible = False
        elif reservation.status == 'CANCELLED':
            if payment.status == 'REFUNDED':
                reason = 'Déjà remboursée'
            else:
                is_eligible = True
                refund_percentage = 100
                reason = 'Réservation annulée - Remboursement possible'
        else:
            reason = f'Statut {reservation.status} - Non remboursable'
        
        return Response({
            'eligible': is_eligible,
            'reason': reason,
            'refund_percentage': refund_percentage,
            'status': reservation.status,
            'payment_status': payment.status,
            'total_amount': float(payment.amount),
            'estimated_refund': float(payment.amount) * refund_percentage / 100 if is_eligible else 0,
            'currency': payment.currency
        })


# Test endpoints
@api_view(['GET'])
@permission_classes([AllowAny])
def test_auth(request):
    return Response({
        'authenticated': False,
        'message': 'This endpoint is public.',
        'status': 'ok'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_auth_secure(request):
    user = request.user
    return Response({
        'authenticated': True,
        'user_id': user.id,
        'email': getattr(user, 'email', None),
        'voyageur_id': getattr(user, 'voyageur_id', None),
    })