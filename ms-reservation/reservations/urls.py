from django.urls import path
from django.http import JsonResponse
from . import views

# Health check endpoints
def health_check(request):
    return JsonResponse({"status": "UP", "service": "ms-reservation"})

def info(request):
    return JsonResponse({
        "app": {
            "name": "ms-reservation",
            "description": "Reservation Service",
            "version": "1.0.0"
        }
    })

urlpatterns = [
    # Health check endpoints
    path('actuator/health/', health_check, name='health_check'),
    path('actuator/info/', info, name='info'),
    
    # Test endpoint
    path('test-auth/', views.test_auth, name='test-auth'),
    
    # Reservation endpoints
    path('reservations/', views.ReservationViewSet.as_view({
        'get': 'list',
        'post': 'create'
    })),
    path('reservations/<int:pk>/', views.ReservationViewSet.as_view({
        'get': 'retrieve'
    })),
    path('reservations/<int:pk>/confirm_price/', views.ReservationViewSet.as_view({
        'post': 'confirm_price'
    })),
    path('reservations/<int:pk>/retry_failed/', views.ReservationViewSet.as_view({
        'post': 'retry_failed'
    })),
    path('reservations/<int:pk>/book/', views.ReservationViewSet.as_view({
        'post': 'book'
    })),
    path('reservations/<int:pk>/booking_status/', views.ReservationViewSet.as_view({
        'get': 'booking_status'
    })),
    path('reservations/<int:pk>/cancel_booking/', views.ReservationViewSet.as_view({
        'post': 'cancel_booking'
    })),
    path('reservations/by-voyageur/<int:voyageur_id>/', 
         views.ReservationViewSet.as_view({'get': 'get_by_voyageur'}),
         name='reservations-by-voyageur'),
    
    path('reservations/my-reservations/', 
         views.ReservationViewSet.as_view({'get': 'my_reservations'}),
         name='my-reservations'),
    
    path('reservations/<int:pk>/full-details/', 
         views.ReservationViewSet.as_view({'get': 'full_details'}),
         name='reservation-full-details'),
     path('reservations/admin/all/', 
         views.ReservationViewSet.as_view({'get': 'admin_all_reservations'}),
         name='admin-all-reservations'),
     path('reservations/<int:pk>/ticket/', 
         views.ReservationViewSet.as_view({'get': 'get_ticket'}),
         name='reservation-ticket'),
    
    path('reservations/<int:pk>/ticket/download/', 
         views.ReservationViewSet.as_view({'get': 'download_ticket'}),
         name='reservation-ticket-download'),
    path('reservations/<int:pk>/cancel_reservation/', 
         views.ReservationViewSet.as_view({'post': 'cancel_booking'}),
         name='cancel-reservation'),
    path('reservations/<int:pk>/request_refund/', 
         views.ReservationViewSet.as_view({'post': 'request_refund'}),
         name='request-refund'),
    path('reservations/<int:pk>/refund_eligibility/', 
         views.ReservationViewSet.as_view({'get': 'get_refund_eligibility'}),
         name='refund-eligibility'),
]