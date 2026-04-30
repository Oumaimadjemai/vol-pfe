"""
URL configuration for ms_destination project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

# Health check endpoints
def health_check(request):
    return JsonResponse({"status": "UP", "service": "ms-destination"})

def info(request):
    return JsonResponse({
        "app": {
            "name": "ms-destination",
            "description": "Destination Service",
            "version": "1.0.0"
        }
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('dest.urls')),  # Include api URLs
    path('actuator/health/', health_check, name='health_check'),
    path('actuator/info/', info, name='info'),
]