from django.db import models
from django.utils import timezone
from datetime import date
import uuid


class Reservation(models.Model):
    """Main reservation model with Amadeus integration"""

    STATUS_CHOICES = (
        ('PENDING_PRICE', 'Waiting price confirmation'),
        ('PRICE_CONFIRMED', 'Price confirmed'),
        ('BOOKING_PENDING', 'Booking in progress'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
        ('FAILED', 'Failed'),
    )

    TRIP_TYPE_CHOICES = (
        ('ALLER_SIMPLE', 'One way'),
        ('ALLER_RETOUR', 'Round trip'),
        ('MULTI_DESTINATION', 'Multi city'),
    )

    # Identifiers
    reservation_number = models.CharField(max_length=25, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Relation with auth service
    voyageur = models.IntegerField()

    # Trip info
    trip_type = models.CharField(max_length=20, choices=TRIP_TYPE_CHOICES)
    search_params = models.JSONField(default=dict)

    # Pricing
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")

    # Amadeus integration
    original_offer = models.JSONField(null=True, blank=True)
    confirmed_offer = models.JSONField(null=True, blank=True)

    amadeus_pnr = models.CharField(max_length=100, null=True, blank=True)
    amadeus_booking_data = models.JSONField(null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING_PRICE"
    )

    # Price confirmation tracking
    last_confirmed_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    price_confirmed_at = models.DateTimeField(null=True, blank=True)

    # Important dates
    expiry_date = models.DateTimeField(null=True, blank=True)
    confirmation_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["reservation_number"]),
            models.Index(fields=["voyageur"]),
            models.Index(fields=["status"]),
            models.Index(fields=["amadeus_pnr"]),
        ]

    def save(self, *args, **kwargs):
        if not self.reservation_number:
            self.reservation_number = self.generate_reservation_number()
        super().save(*args, **kwargs)

    def generate_reservation_number(self):
        return f"RES-{uuid.uuid4().hex[:8].upper()}-{date.today().strftime('%Y%m')}"

    def __str__(self):
        return f"{self.reservation_number} ({self.status})"


class FlightSegment(models.Model):
    """Flight segment for reservation"""

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="flight_segments"
    )

    segment_number = models.PositiveSmallIntegerField()

    origin = models.CharField(max_length=3)
    destination = models.CharField(max_length=3)

    departure_date = models.DateField()
    departure_time = models.TimeField()

    arrival_date = models.DateField()
    arrival_time = models.TimeField()

    # store raw segment data
    flight_data = models.JSONField(default=dict)

    price = models.DecimalField(max_digits=12, decimal_places=2)
    per_passenger_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["segment_number"]
        unique_together = ("reservation", "segment_number")

    def __str__(self):
        return f"{self.origin} → {self.destination}"


class PassengerReservation(models.Model):
    """Passenger ↔ Reservation relation"""

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="passenger_reservations"
    )

    passenger = models.IntegerField()

    check_in_status = models.BooleanField(default=False)
    seat_number = models.CharField(max_length=10, null=True, blank=True)
    baggage_quantity = models.PositiveIntegerField(default=0)

    price_paid = models.DecimalField(max_digits=12, decimal_places=2)

    amadeus_traveler_id = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        unique_together = ("reservation", "passenger")

    def __str__(self):
        return f"Passenger {self.passenger}"


class Payment(models.Model):
    """Payment information"""

    PAYMENT_STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("REFUNDED", "Refunded"),
    )

    PAYMENT_METHOD_CHOICES = (
        ("CARD", "Card"),
        ("PAYPAL", "PayPal"),
        ("BANK_TRANSFER", "Bank transfer"),
        ("CASH", "Cash"),
    )

    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.CASCADE,
        related_name="payment"
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)

    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="PENDING"
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES
    )

    transaction_id = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment {self.id}"


class PriceConfirmation(models.Model):
    """Track Amadeus price confirmations"""

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="price_confirmations"
    )

    offered_price = models.DecimalField(max_digits=12, decimal_places=2)
    confirmed_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        null=True,
        blank=True
    )

    currency = models.CharField(max_length=3)

    confirmed_offer = models.JSONField(null=True, blank=True)

    confirmed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self):
        return timezone.now() < self.expires_at