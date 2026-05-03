#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ms_reservation.settings')
   
    # ⭐ Démarrer Kafka consumer en arrière-plan (si runserver)
    if 'runserver' in sys.argv:
        try:
            from kafka_consumer import start_reservation_consumer
            start_reservation_consumer()
            print('🚀 Kafka consumer thread démarré (écoute payment.confirmed)')
        except ImportError as e:
            print(f'⚠️ Kafka consumer non disponible: {e}')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
