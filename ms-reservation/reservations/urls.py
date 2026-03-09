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
]