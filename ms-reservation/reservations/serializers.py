from rest_framework import serializers
from .models import (
    Reservation, FlightSegment, PassengerReservation, 
    Payment, PriceConfirmation
)
from django.utils import timezone
from datetime import datetime
import json
from datetime import date, datetime
from decimal import Decimal


class CustomJSONEncoder(json.JSONEncoder):
    """JSON Encoder personnalisé qui gère les dates, datetime et Decimal"""
    
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super().default(obj)


class PassengerInfoSerializer(serializers.Serializer):
    """Serializer for passenger information from frontend"""
    nom = serializers.CharField(max_length=50)
    prenom = serializers.CharField(max_length=50)
    date_naissance = serializers.DateField(input_formats=['%Y-%m-%d'])
    sexe = serializers.ChoiceField(choices=['homme', 'femme'])
    num_passport = serializers.CharField(max_length=20, required=False, allow_blank=True)
    date_exp_passport = serializers.DateField(required=False, allow_null=True, input_formats=['%Y-%m-%d'])
    email = serializers.EmailField(required=False, allow_blank=True)
    telephone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    nationalite = serializers.CharField(max_length=2, default='FR', required=False)
    lieu_naissance = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    def validate(self, data):
        if data.get('num_passport') and not data.get('date_exp_passport'):
            raise serializers.ValidationError(
                "La date d'expiration du passport est requise"
            )
        return data


class FlightSelectionSerializer(serializers.Serializer):
    """Serializer for flight selection from frontend"""
    flight_id = serializers.CharField(max_length=100)
    airline = serializers.CharField(max_length=100)
    flightNumber = serializers.CharField(max_length=20)
    price = serializers.DictField()
    departure = serializers.DictField()
    arrival = serializers.DictField()
    duration = serializers.CharField()
    segments = serializers.ListField()
    baggage = serializers.DictField()
    refundable = serializers.DictField()
    seatsAvailable = serializers.IntegerField(min_value=1)
    
    def validate_seatsAvailable(self, value):
        context = self.context
        passengers_count = context.get('passengers_count', 0)
        
        if value < passengers_count:
            raise serializers.ValidationError(
                f"Seulement {value} sièges disponibles pour {passengers_count} passagers"
            )
        return value


class ReservationRequestSerializer(serializers.Serializer):
    search_params   = serializers.DictField()
    trip_type       = serializers.ChoiceField(choices=[
        ('ALLER_SIMPLE',      'Aller simple'),
        ('ALLER_RETOUR',      'Aller-retour'),
        ('MULTI_DESTINATION', 'Multi-destination'),
    ])
    selected_flights = serializers.ListField(child=FlightSelectionSerializer())
    passengers = serializers.ListField(
        child=PassengerInfoSerializer(),
        required=False,
        default=list
    )
    existing_passenger_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )
    payment_method = serializers.ChoiceField(choices=[
        ('CARD',     'Card'),
        ('CASH',     'Cash (En espèces)'),
        ('DELIVERY', 'Delivery'),
    ])

    def validate(self, data):
        explicit_count = (
            len(data.get('passengers', [])) +
            len(data.get('existing_passenger_ids', []))
        )
        # 0 is valid — means solo booking (voyageur = passenger)
        # the view will auto-create the passenger from the voyageur profile

        for flight in data['selected_flights']:
            # seats check: count the voyageur too when explicit_count == 0
            effective_count = explicit_count if explicit_count > 0 else 1
            if flight['seatsAvailable'] < effective_count:
                raise serializers.ValidationError(
                    f"Pas assez de sièges sur le vol {flight['flightNumber']}"
                )

        if data['trip_type'] == 'ALLER_SIMPLE' and len(data['selected_flights']) != 1:
            raise serializers.ValidationError(
                "Un vol simple ne doit contenir qu'un seul segment"
            )

        return data
class PriceConfirmationSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PriceConfirmation
        fields = [
            'id', 'offered_price', 'confirmed_price', 'currency',
            'confirmed_offer', 'confirmed_at', 'expires_at', 'is_valid'
        ]


class PassengerReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PassengerReservation
        fields = [
            'id', 'passenger', 'check_in_status', 'seat_number',
            'baggage_quantity', 'price_paid', 'amadeus_traveler_id'
        ]
        read_only_fields = ['id']


class FlightSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightSegment
        fields = [
            'id', 'segment_number', 'origin', 'destination',
            'departure_date', 'departure_time', 'arrival_date', 'arrival_time',
            'flight_data', 'price', 'per_passenger_price'
        ]
        read_only_fields = ['id']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'amount', 'currency', 'status', 'payment_method',
            'transaction_id', 'created_at', 'completed_at'
        ]
        read_only_fields = ['id', 'created_at', 'completed_at']


class ReservationSerializer(serializers.ModelSerializer):
    flight_segments = FlightSegmentSerializer(many=True, read_only=True)
    passenger_reservations = PassengerReservationSerializer(many=True, read_only=True)
    payment = PaymentSerializer(read_only=True)
    price_confirmations = PriceConfirmationSerializer(many=True, read_only=True)
    
    class Meta:
        model = Reservation
        fields = [
            'id', 'reservation_number', 'created_at', 'updated_at',
            'voyageur', 'status', 'trip_type', 'search_params',
            'original_offer', 'confirmed_offer', 'amadeus_pnr', 'amadeus_booking_data',
            'last_confirmed_price', 'price_confirmed_at',
            'total_price', 'currency', 'expiry_date', 'confirmation_date',
            'flight_segments', 'passenger_reservations', 'payment',
            'price_confirmations'
        ]
        read_only_fields = [
            'id', 'reservation_number', 'created_at', 'updated_at',
            'original_offer', 'confirmed_offer', 'amadeus_pnr', 'amadeus_booking_data',
            'last_confirmed_price', 'price_confirmed_at',
            'expiry_date', 'confirmation_date'
        ]


class ReservationListSerializer(serializers.ModelSerializer):
    """Serializer for reservation list with voyageur and passenger info"""
    voyageur_details = serializers.SerializerMethodField()
    passenger_count = serializers.SerializerMethodField()
    passenger_names = serializers.SerializerMethodField()
    flight_origin = serializers.SerializerMethodField()
    flight_destination = serializers.SerializerMethodField()
    departure_date = serializers.SerializerMethodField()
    
    class Meta:
        model = Reservation
        fields = [
            'id', 
            'reservation_number', 
            'created_at', 
            'status',
            'trip_type', 
            'total_price', 
            'currency', 
            'amadeus_pnr',
            'voyageur',
            'voyageur_details',
            'passenger_count',
            'passenger_names',
            'flight_origin',
            'flight_destination',
            'departure_date'
        ]
    
    def get_voyageur_details(self, obj):
        """Get voyageur details from auth service"""
        request = self.context.get('request')
        if not request:
            return None
        
        auth_client = request.META.get('auth_client')
        if not auth_client:
            return None
        
        try:
            voyageur_data = auth_client.get_voyageur_by_id(obj.voyageur)
            if voyageur_data:
                return {
                    'id': voyageur_data.get('id'),
                    'nom': voyageur_data.get('nom'),
                    'prenom': voyageur_data.get('prenom'),
                    'email': voyageur_data.get('email'),
                    'telephone': voyageur_data.get('telephone')
                }
        except Exception:
            pass
        
        return None
    
    def get_passenger_count(self, obj):
        """Get number of passengers for this reservation"""
        return obj.passenger_reservations.count()
    
    def get_passenger_names(self, obj):
        """Get passenger names from auth service"""
        request = self.context.get('request')
        if not request:
            return []
        
        auth_client = request.META.get('auth_client')
        if not auth_client:
            return []
        
        try:
            # Get all passengers for this voyageur
            voyageur_passengers = auth_client.get_passengers_by_voyageur(obj.voyageur)
            passenger_map = {p.get('id'): p for p in voyageur_passengers}
            
            passenger_names = []
            for pr in obj.passenger_reservations.all():
                passenger_data = passenger_map.get(pr.passenger)
                if passenger_data:
                    passenger_names.append(f"{passenger_data.get('prenom')} {passenger_data.get('nom')}")
            
            return passenger_names
        except Exception:
            pass
        
        return []
    
    def get_flight_origin(self, obj):
        """Get origin of first flight segment"""
        first_segment = obj.flight_segments.first()
        if first_segment:
            return first_segment.origin
        return None
    
    def get_flight_destination(self, obj):
        """Get destination of last flight segment"""
        last_segment = obj.flight_segments.last()
        if last_segment:
            return last_segment.destination
        return None
    
    def get_departure_date(self, obj):
        """Get departure date of first flight segment"""
        first_segment = obj.flight_segments.first()
        if first_segment:
            return first_segment.departure_date
        return None


class PassengerDetailSerializer(serializers.Serializer):
    """Serializer for detailed passenger information"""
    id = serializers.IntegerField()
    nom = serializers.CharField()
    prenom = serializers.CharField()
    date_naissance = serializers.DateField()
    sexe = serializers.CharField()
    num_passport = serializers.CharField(required=False, allow_blank=True)
    date_exp_passport = serializers.DateField(required=False, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    telephone = serializers.CharField(required=False, allow_blank=True)


class FlightSegmentDetailSerializer(serializers.ModelSerializer):
    """Detailed flight segment serializer with formatted times"""
    departure_datetime = serializers.SerializerMethodField()
    arrival_datetime = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    airline_name = serializers.SerializerMethodField()
    
    class Meta:
        model = FlightSegment
        fields = [
            'id', 'segment_number', 'origin', 'destination',
            'departure_date', 'departure_time', 'arrival_date', 'arrival_time',
            'departure_datetime', 'arrival_datetime', 'duration',
            'price', 'per_passenger_price', 'airline_name', 'flight_data'
        ]
    
    def get_departure_datetime(self, obj):
        return f"{obj.departure_date} {obj.departure_time}"
    
    def get_arrival_datetime(self, obj):
        return f"{obj.arrival_date} {obj.arrival_time}"
    
    def get_duration(self, obj):
        flight_data = obj.flight_data
        if flight_data and 'duration' in flight_data:
            return flight_data['duration']
        return "N/A"
    
    def get_airline_name(self, obj):
        flight_data = obj.flight_data
        if flight_data and 'airline' in flight_data:
            return flight_data['airline']
        return "N/A"


class ReservationDetailSerializer(serializers.ModelSerializer):
    """Detailed reservation serializer with passengers and flight details"""
    flight_segments = FlightSegmentDetailSerializer(many=True, read_only=True)
    passengers = serializers.SerializerMethodField()
    payment = PaymentSerializer(read_only=True)
    price_confirmations = PriceConfirmationSerializer(many=True, read_only=True)
    total_passengers = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_modify = serializers.SerializerMethodField()
    
    class Meta:
        model = Reservation
        fields = [
            'id', 
            'reservation_number', 
            'created_at', 
            'updated_at',
            'voyageur',
            'status', 
            'trip_type', 
            'search_params',
            'original_offer',
            'confirmed_offer',
            'amadeus_pnr', 
            'amadeus_booking_data',
            'last_confirmed_price',
            'price_confirmed_at',
            'total_price', 
            'currency', 
            'expiry_date', 
            'confirmation_date',
            'flight_segments', 
            'passengers', 
            'payment',
            'price_confirmations',
            'total_passengers', 
            'can_cancel', 
            'can_modify'
        ]
    
    def get_passengers(self, obj):
        """Get detailed passenger information from auth service"""
        request = self.context.get('request')
        if not request:
            return []
        
        auth_client = request.META.get('auth_client')
        if not auth_client:
            return []
        
        # Get all passengers for the voyageur in ONE request
        voyageur_passengers = auth_client.get_passengers_by_voyageur(obj.voyageur)
        
        if not voyageur_passengers:
            return []
        
        # Create a map for quick lookup
        passenger_map = {p.get('id'): p for p in voyageur_passengers}
        
        # Build response with reservation-specific info from PassengerReservation model
        passengers = []
        for pr in obj.passenger_reservations.all():
            passenger_data = passenger_map.get(pr.passenger)
            if passenger_data:
                passenger_info = {
                    'id': passenger_data.get('id'),
                    'nom': passenger_data.get('nom'),
                    'prenom': passenger_data.get('prenom'),
                    'date_naissance': passenger_data.get('date_naissance'),
                    'sexe': passenger_data.get('sexe'),
                    'num_passport': passenger_data.get('num_passport'),
                    'date_exp_passport': passenger_data.get('date_exp_passport'),
                    'email': passenger_data.get('email'),
                    'telephone': passenger_data.get('telephone'),
                    # Fields from PassengerReservation model
                    'seat_number': pr.seat_number,
                    'check_in_status': pr.check_in_status,
                    'baggage_quantity': pr.baggage_quantity,
                    'price_paid': str(pr.price_paid) if pr.price_paid else None,
                    'amadeus_traveler_id': pr.amadeus_traveler_id
                }
                passengers.append(passenger_info)
        
        return passengers
    
    def get_total_passengers(self, obj):
        return obj.passenger_reservations.count()
    
    def get_can_cancel(self, obj):
        """Check if reservation can be cancelled (only confirmed reservations can be cancelled)"""
        return obj.status == 'CONFIRMED'
    
    def get_can_modify(self, obj):
        """Check if reservation can be modified (only pending price or price confirmed can be modified)"""
        return obj.status in ['PENDING_PRICE', 'PRICE_CONFIRMED']