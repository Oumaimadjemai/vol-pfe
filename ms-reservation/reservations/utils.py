from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """Custom exception handler for REST framework"""
    response = exception_handler(exc, context)
    
    if response is not None:
        response.data['status_code'] = response.status_code
        
        # Log the error
        logger.error(f"API Error: {exc}", exc_info=True)
    else:
        # Unhandled exceptions
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        response = Response(
            {
                'error': 'Une erreur inattendue est survenue',
                'detail': str(exc)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return response


def format_amadeus_error(error):
    """Format Amadeus error for response"""
    return {
        'code': getattr(error, 'code', 'UNKNOWN'),
        'title': getattr(error, 'title', 'Erreur Amadeus'),
        'detail': getattr(error, 'detail', str(error))
    }

