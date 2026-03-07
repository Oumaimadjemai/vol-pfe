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
    flight_id = serializers.CharField(max_length=50)
    airline = serializers.CharField(max_length=10)
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
    """Main serializer for reservation creation"""
    search_params = serializers.DictField()
    trip_type = serializers.ChoiceField(choices=[
        ('ALLER_SIMPLE', 'Aller simple'),
        ('ALLER_RETOUR', 'Aller-retour'),
        ('MULTI_DESTINATION', 'Multi-destination'),
    ])
    
    selected_flights = serializers.ListField(
        child=FlightSelectionSerializer()
    )
    
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
        ('CARD', 'Carte bancaire'),
        ('PAYPAL', 'PayPal'),
        ('BANK_TRANSFER', 'Virement bancaire'),
        ('CASH', 'Espèces'),
    ])
    
    def validate(self, data):
        passengers_count = len(data.get('passengers', [])) + len(data.get('existing_passenger_ids', []))
        
        if passengers_count == 0:
            raise serializers.ValidationError("Au moins un passager est requis")
        
        for flight in data['selected_flights']:
            if flight['seatsAvailable'] < passengers_count:
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
            'amadeus_offer_id', 'confirmed_at', 'expires_at', 'is_valid'
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
            'amadeus_offer_id', 'amadeus_pnr', 'amadeus_booking_data',
            'last_confirmed_price', 'price_confirmed_at', 'confirmed_offer_data',
            'total_price', 'currency', 'expiry_date', 'confirmation_date',
            'flight_segments', 'passenger_reservations', 'payment',
            'price_confirmations'
        ]
        read_only_fields = [
            'id', 'reservation_number', 'created_at', 'updated_at',
            'amadeus_offer_id', 'amadeus_pnr', 'amadeus_booking_data',
            'last_confirmed_price', 'price_confirmed_at', 'confirmed_offer_data',
            'expiry_date', 'confirmation_date'
        ]


class ReservationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            'id', 'reservation_number', 'created_at', 'status',
            'trip_type', 'total_price', 'currency', 'amadeus_pnr'
        ]