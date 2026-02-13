# users/apps.py
from django.apps import AppConfig

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        # Import from project root (auth_service)
        print("Starting Eureka client...")
        from auth_service.eureka_client import start_eureka_client
        start_eureka_client()
