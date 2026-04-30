from django.apps import AppConfig
import threading
import os
import logging

logger = logging.getLogger(__name__)


class DestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dest'
    verbose_name = 'Destination Management'
    
    def ready(self):
        """Start Eureka client when Django app is ready"""
        # Fix: Check for RUN_MAIN properly
        is_main_process = os.environ.get('RUN_MAIN') == 'true'
        is_auto_reload = os.environ.get('DJANGO_AUTORELOAD') is not None
        
        if not is_auto_reload:
            # Start Eureka in background
            self.start_eureka_in_background()
    
    def start_eureka_in_background(self):
        """Start Eureka client in a background thread"""
        try:
            from .eureka_client import start_eureka_client
            
            # Add a small delay to ensure network is ready
            import time
            time.sleep(3)
            
            # Start Eureka in a separate thread
            thread = threading.Thread(target=start_eureka_client, daemon=True)
            thread.start()
            logger.info("Eureka client thread started")
        except Exception as e:
            logger.error(f"Failed to start Eureka client: {e}")