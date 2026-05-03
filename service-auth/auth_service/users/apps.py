# service-auth/apps.py
from django.apps import AppConfig
import sys
import os
import threading
import time


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        import users.signals
        
        # Start Eureka client with a small delay to ensure Django is ready
        def start_eureka_with_delay():
            # Wait a bit for Django to fully initialize
            time.sleep(2)
            try:
                from auth_service.eureka_client import start_eureka_client
                start_eureka_client()
            except Exception as e:
                print(f"⚠️ Eureka startup error: {e}")
        
        # Start Eureka in background thread
        eureka_thread = threading.Thread(target=start_eureka_with_delay, daemon=True)
        eureka_thread.start()
        
        # Start Kafka consumer (only when running server, not migrations)
        if 'runserver' in sys.argv and os.getenv('KAFKA_ENABLED', 'True') == 'True':
            try:
                from .kafka_consumer import start_auth_consumer
                start_auth_consumer()
                print("✅ Auth service Kafka consumer started")
            except Exception as e:
                print(f"⚠️ Failed to start Kafka consumer: {e}")