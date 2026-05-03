from django.contrib import admin
from .models import Reservation, FlightSegment, PassengerReservation, Payment, PriceConfirmation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'reservation_number', 'voyageur', 'status', 
        'trip_type', 'total_price', 'currency', 'created_at'
    ]
    list_filter = ['status', 'trip_type', 'created_at']
    search_fields = ['reservation_number', 'amadeus_pnr', 'voyageur']
    readonly_fields = [
        'reservation_number', 
        'created_at', 
        'updated_at',
        'amadeus_pnr', 
        'amadeus_booking_data',
        'last_confirmed_price', 
        'price_confirmed_at', 
        'confirmed_offer',
        'expiry_date', 
        'confirmation_date'
    ]
    fieldsets = (
        ('Identification', {
            'fields': ('reservation_number', 'voyageur', 'status')
        }),
        ('Trip Information', {
            'fields': ('trip_type', 'search_params')
        }),
        ('Pricing', {
            'fields': ('total_price', 'currency', 'last_confirmed_price')
        }),
        ('Amadeus Integration', {
            'fields': ('original_offer', 'confirmed_offer', 'amadeus_pnr', 'amadeus_booking_data')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at', 'price_confirmed_at', 
                      'expiry_date', 'confirmation_date')
        }),
    )


@admin.register(FlightSegment)
class FlightSegmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'reservation', 'segment_number', 'origin', 'destination', 
                   'departure_date', 'departure_time', 'price']
    list_filter = ['departure_date', 'origin', 'destination']
    search_fields = ['reservation__reservation_number', 'origin', 'destination']


@admin.register(PassengerReservation)
class PassengerReservationAdmin(admin.ModelAdmin):
    list_display = ['id', 'reservation', 'passenger', 'check_in_status', 'price_paid']
    list_filter = ['check_in_status']
    search_fields = ['reservation__reservation_number', 'passenger']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'reservation', 'amount', 'currency', 'status', 'payment_method', 'created_at']
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['reservation__reservation_number', 'transaction_id']


@admin.register(PriceConfirmation)
class PriceConfirmationAdmin(admin.ModelAdmin):
    list_display = ['id', 'reservation', 'offered_price', 'confirmed_price', 
                   'confirmed_at', 'expires_at', 'is_valid']
    list_filter = ['confirmed_at']
    search_fields = ['reservation__reservation_number']
    
    def is_valid(self, obj):
        return obj.is_valid()
    is_valid.boolean = True
    is_valid.short_description = 'Valid'