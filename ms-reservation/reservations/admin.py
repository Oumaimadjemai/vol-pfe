from django.contrib import admin
from .models import Reservation, FlightSegment, PassengerReservation, Payment, PriceConfirmation


class FlightSegmentInline(admin.TabularInline):
    model = FlightSegment
    extra = 0


class PassengerReservationInline(admin.TabularInline):
    model = PassengerReservation
    extra = 0


class PriceConfirmationInline(admin.TabularInline):
    model = PriceConfirmation
    extra = 0


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = [
        'reservation_number', 'voyageur', 'status', 'trip_type',
        'total_price', 'currency', 'amadeus_pnr', 'created_at'
    ]
    list_filter = ['status', 'trip_type', 'created_at']
    search_fields = ['reservation_number', 'amadeus_pnr', 'voyageur']
    readonly_fields = [
        'reservation_number', 'created_at', 'updated_at',
        'amadeus_offer_id', 'amadeus_pnr', 'amadeus_booking_data'
    ]
    inlines = [FlightSegmentInline, PassengerReservationInline, PriceConfirmationInline]
    
    fieldsets = (
        ('Informations générales', {
            'fields': (
                'reservation_number', 'voyageur', 'status', 'trip_type',
                'created_at', 'updated_at'
            )
        }),
        ('Amadeus', {
            'fields': (
                'amadeus_offer_id', 'amadeus_pnr', 'amadeus_booking_data'
            )
        }),
        ('Prix', {
            'fields': (
                'total_price', 'currency', 'last_confirmed_price',
                'price_confirmed_at', 'confirmed_offer_data'
            )
        }),
        ('Paramètres de recherche', {
            'fields': ('search_params',)
        }),
        ('Dates importantes', {
            'fields': ('expiry_date', 'confirmation_date')
        }),
    )


@admin.register(FlightSegment)
class FlightSegmentAdmin(admin.ModelAdmin):
    list_display = [
        'reservation', 'segment_number', 'origin', 'destination',
        'departure_date', 'departure_time', 'price'
    ]
    list_filter = ['origin', 'destination', 'departure_date']
    search_fields = ['reservation__reservation_number', 'origin', 'destination']


@admin.register(PassengerReservation)
class PassengerReservationAdmin(admin.ModelAdmin):
    list_display = [
        'reservation', 'passenger', 'check_in_status',
        'seat_number', 'price_paid', 'amadeus_traveler_id'
    ]
    list_filter = ['check_in_status']
    search_fields = ['reservation__reservation_number', 'passenger']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'reservation', 'amount', 'currency', 'status',
        'payment_method', 'transaction_id', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['reservation__reservation_number', 'transaction_id']


@admin.register(PriceConfirmation)
class PriceConfirmationAdmin(admin.ModelAdmin):
    list_display = [
        'reservation', 'offered_price', 'confirmed_price',
        'currency', 'confirmed_at', 'expires_at'
    ]
    list_filter = ['confirmed_at']
    search_fields = ['reservation__reservation_number', 'amadeus_offer_id']