from django.apps import AppConfig
import sys


class ReservationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reservations'

    def ready(self):
        """Called when Django app is ready"""
        # Only start Eureka client for runserver or gunicorn commands
        if len(sys.argv) > 1 and sys.argv[1] in ['runserver', 'gunicorn']:
            print("\n🚀 Initializing reservation service...")
            from .eureka_client import start_eureka_client
            start_eureka_client()