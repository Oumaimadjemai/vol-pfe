import sys
import os
from django.apps import AppConfig

# Management commands that must never start background threads
_SKIP_COMMANDS = {
    'migrate', 'makemigrations', 'collectstatic',
    'shell', 'test', 'createsuperuser', 'dbshell',
    'showmigrations', 'sqlmigrate', 'check',
}


class ReservationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reservations'

    def ready(self):
        # Skip background threads for management commands
        if any(cmd in sys.argv for cmd in _SKIP_COMMANDS):
            return

        # On Django's dev server, ready() is called twice (once by the
        # reloader parent, once by the worker child). Only run in the
        # worker child — RUN_MAIN is set by the reloader on the child.
        # For Gunicorn/uWSGI, RUN_MAIN is not set at all, so we always run.
        is_dev_server = 'runserver' in sys.argv
        if is_dev_server and os.getenv('RUN_MAIN') != 'true':
            return

        self._start_kafka()
        self._start_eureka()

    # ------------------------------------------------------------------ #

    def _start_kafka(self):
        if os.getenv('KAFKA_ENABLED', 'True').lower() != 'true':
            print("⚠️ Kafka disabled via KAFKA_ENABLED=False")
            return
        try:
            from .kafka_consumer import start_reservation_consumer
            start_reservation_consumer()
            print("✅ Reservation service Kafka consumer started")
        except Exception as e:
            print(f"⚠️ Failed to start Kafka consumer: {e}")

    def _start_eureka(self):
        if os.getenv('DISABLE_EUREKA', 'False').lower() == 'true':
            print("⚠️ Eureka disabled via DISABLE_EUREKA=True")
            return
        try:
            from .eureka_client import start_eureka_client
            start_eureka_client()
        except Exception as e:
            print(f"⚠️ Failed to start Eureka client: {e}")