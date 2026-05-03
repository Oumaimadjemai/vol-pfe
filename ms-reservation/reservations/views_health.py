from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@require_GET
def health_check(request):
    """Health check endpoint for Eureka"""
    return JsonResponse({
        "status": "UP",
        "service": "ms-reservation",
        "port": 8001
    })


@csrf_exempt
@require_GET
def info(request):
    """Info endpoint for Eureka"""
    return JsonResponse({
        "app": {
            "name": "ms-reservation",
            "description": "Reservation Service",
            "version": "1.0.0"
        }
    })