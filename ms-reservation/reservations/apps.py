from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class ReservationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reservations'  # Replace with your app name

    def ready(self):
        """Start Eureka client when Django app is ready"""
        # Import here to avoid circular imports
        from . import eureka_client
        
        # Only start in production-like environments
        import os
        import sys
        
        # Skip during migrations and tests
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            logger.info("Skipping Eureka client start during migrations")
            return
        
        if 'test' in sys.argv:
            logger.info("Skipping Eureka client start during tests")
            return
        
        # Start Eureka client
        try:
            eureka_client.start_eureka_client()
        except Exception as e:
            logger.error(f"Failed to start Eureka client: {e}")