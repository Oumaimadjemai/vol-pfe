from django.db import models
from django.utils import timezone
from datetime import date, timedelta
import uuid


class Reservation(models.Model):
    """Main reservation model with Amadeus integration"""
    STATUS_CHOICES = (
        ('PENDING_PRICE', 'En attente de confirmation prix'),
        ('PRICE_CONFIRMED', 'Prix confirmé'),
        ('BOOKING_PENDING', 'Réservation en cours'),
        ('CONFIRMED', 'Confirmée'),
        ('CANCELLED', 'Annulée'),
        ('EXPIRED', 'Expirée'),
        ('FAILED', 'Échouée'),
    )
    
    TRIP_TYPE_CHOICES = (
        ('ALLER_SIMPLE', 'Aller simple'),
        ('ALLER_RETOUR', 'Aller-retour'),
        ('MULTI_DESTINATION', 'Multi-destination'),
    )
    
    # Identifiants
    reservation_number = models.CharField(max_length=20, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Relations
    voyageur = models.IntegerField()  # ID from auth service
    
    # Amadeus specific fields
    amadeus_offer_id = models.CharField(max_length=100, null=True, blank=True)
    amadeus_pnr = models.CharField(max_length=20, null=True, blank=True)
    amadeus_booking_data = models.JSONField(default=dict, null=True, blank=True)
    
    # Price confirmation
    last_confirmed_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    price_confirmed_at = models.DateTimeField(null=True)
    confirmed_offer_data = models.JSONField(default=dict, null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_PRICE')
    trip_type = models.CharField(max_length=20, choices=TRIP_TYPE_CHOICES)
    
    # Search parameters
    search_params = models.JSONField(default=dict)
    
    # Price
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='DZD')
    
    # Important dates
    expiry_date = models.DateTimeField(null=True, blank=True)
    confirmation_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reservation_number']),
            models.Index(fields=['amadeus_pnr']),
            models.Index(fields=['voyageur', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.reservation_number:
            self.reservation_number = self.generate_reservation_number()
        super().save(*args, **kwargs)
    
    def generate_reservation_number(self):
        return f"RES-{uuid.uuid4().hex[:8].upper()}-{date.today().strftime('%Y%m')}"
    
    def __str__(self):
        return f"Réservation {self.reservation_number} - PNR: {self.amadeus_pnr}"


class FlightSegment(models.Model):
    """Flight segment for a reservation"""
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='flight_segments'
    )
    
    segment_number = models.PositiveSmallIntegerField()
    origin = models.CharField(max_length=3)
    destination = models.CharField(max_length=3)
    departure_date = models.DateField()
    departure_time = models.TimeField()
    arrival_date = models.DateField()
    arrival_time = models.TimeField()
    
    flight_data = models.JSONField(default=dict)
    
    price = models.DecimalField(max_digits=10, decimal_places=2)
    per_passenger_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        ordering = ['segment_number']
        unique_together = ['reservation', 'segment_number']
    
    def __str__(self):
        return f"Segment {self.segment_number}: {self.origin} → {self.destination}"


class PassengerReservation(models.Model):
    """Association between passengers and reservation"""
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='passenger_reservations'
    )
    passenger = models.IntegerField()  # ID from auth service
    
    check_in_status = models.BooleanField(default=False)
    seat_number = models.CharField(max_length=10, blank=True, null=True)
    baggage_quantity = models.PositiveSmallIntegerField(default=0)
    
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)
    
    amadeus_traveler_id = models.CharField(max_length=10, null=True, blank=True)
    
    class Meta:
        unique_together = ['reservation', 'passenger']
    
    def __str__(self):
        return f"Passenger {self.passenger} - {self.reservation.reservation_number}"


class Payment(models.Model):
    """Payment information"""
    PAYMENT_STATUS_CHOICES = (
        ('PENDING', 'En attente'),
        ('COMPLETED', 'Complété'),
        ('FAILED', 'Échoué'),
        ('REFUNDED', 'Remboursé'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('CARD', 'Carte bancaire'),
        ('PAYPAL', 'PayPal'),
        ('BANK_TRANSFER', 'Virement bancaire'),
        ('CASH', 'Espèces'),
    )
    
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.CASCADE,
        related_name='payment'
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='DZD')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Paiement {self.id} - {self.reservation.reservation_number}"


class PriceConfirmation(models.Model):
    """Track price confirmations (Step 2)"""
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='price_confirmations'
    )
    
    offered_price = models.DecimalField(max_digits=10, decimal_places=2)
    confirmed_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    
    amadeus_offer_id = models.CharField(max_length=100)
    offer_data = models.JSONField(default=dict)
    
    confirmed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def is_valid(self):
        return self.expires_at > timezone.now()