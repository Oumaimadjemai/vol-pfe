import json
import logging
import threading
import os
from kafka import KafkaConsumer
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ReservationKafkaConsumer:
    """
    Consumes user/voyageur/passenger events from ms-auth.
    Caches received data locally so the booking flow can avoid
    redundant HTTP round-trips to the auth service.
    """

    _instance = None
    _running = False
    _consumer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self):
        if self._running:
            return
        self._running = True
        thread = threading.Thread(target=self._consume, daemon=True)
        thread.start()
        logger.info("✅ Reservation Kafka consumer started — listening on "
                    "user-events, voyageur-events, passenger-events")

    def stop(self):
        self._running = False
        if self._consumer:
            self._consumer.close()
        logger.info("🛑 Reservation Kafka consumer stopped")

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #

    def _consume(self):
        try:
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
            self._consumer = KafkaConsumer(
                'user-events',
                'voyageur-events',
                'passenger-events',
                bootstrap_servers=bootstrap_servers.split(','),
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id='reservation-service-group',
                session_timeout_ms=30000,
                max_poll_records=100,
            )
            logger.info("🔄 Reservation consumer listening…")
            for message in self._consumer:
                if not self._running:
                    break
                try:
                    self._dispatch(message.value)
                except Exception as e:
                    logger.error(f"❌ Error processing message: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"❌ Consumer loop error: {e}", exc_info=True)
            self._running = False

    # ------------------------------------------------------------------ #
    # Dispatcher
    # ------------------------------------------------------------------ #

    def _dispatch(self, event: dict):
        event_type = event.get('event_type')
        payload    = event.get('payload', {})
        source     = event.get('source', 'unknown')
        logger.info(f"📥 {event_type} from {source}")

        handlers = {
            'USER_REGISTERED':    self._on_user_registered,
            'USER_UPDATED':       self._on_user_updated,
            'USER_DELETED':       self._on_user_deleted,
            'VOYAGEUR_REGISTERED': self._on_voyageur_upsert,
            'VOYAGEUR_UPDATED':   self._on_voyageur_upsert,
            'PASSENGER_CREATED':  self._on_passenger_upsert,
            'PASSENGER_UPDATED':  self._on_passenger_upsert,
            'PASSENGER_DELETED':  self._on_passenger_deleted,
        }

        handler = handlers.get(event_type)
        if handler:
            handler(payload)
        else:
            logger.debug(f"Unhandled event type: {event_type}")

    # ------------------------------------------------------------------ #
    # User handlers
    # ------------------------------------------------------------------ #

    def _on_user_registered(self, payload: dict):
        user_id = payload.get('user_id')
        role    = payload.get('role')
        logger.info(f"👤 New user {user_id} (role={role})")
        # Cache minimal user info — useful when we need email/role quickly
        self._set(f"user:{user_id}", {
            'id':       user_id,
            'email':    payload.get('email'),
            'role':     role,
            'username': payload.get('username'),
        })

    def _on_user_updated(self, payload: dict):
        user_id = payload.get('user_id')
        logger.info(f"🔄 User updated: {user_id}")
        # Merge into existing cache entry
        existing = self._get(f"user:{user_id}") or {}
        existing.update({
            'email':      payload.get('email', existing.get('email')),
            'role':       payload.get('role',  existing.get('role')),
            'username':   payload.get('username', existing.get('username')),
            'is_active':  payload.get('is_active', existing.get('is_active')),
            'is_blocked': payload.get('is_blocked', existing.get('is_blocked')),
        })
        self._set(f"user:{user_id}", existing)

    def _on_user_deleted(self, payload: dict):
        user_id = payload.get('user_id')
        logger.info(f"🗑️ User deleted: {user_id}")
        cache.delete(f"user:{user_id}")

    # ------------------------------------------------------------------ #
    # Voyageur handlers
    # ------------------------------------------------------------------ #

    def _on_voyageur_upsert(self, payload: dict):
        voyageur_id = payload.get('voyageur_id')
        user_id     = payload.get('user_id')
        logger.info(f"✈️ Voyageur upsert: {voyageur_id}")

        data = {
            'id':         voyageur_id,
            'user_id':    user_id,
            'nom':        payload.get('nom'),
            'prenom':     payload.get('prenom'),
            'email':      payload.get('email'),
            'telephone':  payload.get('telephone'),
        }
        self._set(f"voyageur:{voyageur_id}", data, ttl=7200)

        # Also index by user_id so get_voyageur_by_user_id() can hit cache
        if user_id:
            self._set(f"voyageur_by_user:{user_id}", voyageur_id, ttl=7200)

    # ------------------------------------------------------------------ #
    # Passenger handlers
    # ------------------------------------------------------------------ #

    def _on_passenger_upsert(self, payload: dict):
        passenger_id = payload.get('passenger_id')
        voyageur_id  = payload.get('voyageur_id')
        logger.info(f"👤 Passenger upsert: {passenger_id}")

        data = {
            'id':             passenger_id,
            'voyageur_id':    voyageur_id,
            'nom':            payload.get('nom'),
            'prenom':         payload.get('prenom'),
            'date_naissance': payload.get('date_naissance'),
        }
        self._set(f"passenger:{passenger_id}", data)

        # Keep a set of passenger IDs per voyageur (stored as a list)
        if voyageur_id:
            ids = self._get(f"passengers_for_voyageur:{voyageur_id}") or []
            if passenger_id not in ids:
                ids.append(passenger_id)
                self._set(f"passengers_for_voyageur:{voyageur_id}", ids, ttl=7200)

    def _on_passenger_deleted(self, payload: dict):
        passenger_id = payload.get('passenger_id')
        voyageur_id  = payload.get('voyageur_id')
        logger.info(f"🗑️ Passenger deleted: {passenger_id}")

        cache.delete(f"passenger:{passenger_id}")

        if voyageur_id:
            ids = self._get(f"passengers_for_voyageur:{voyageur_id}") or []
            ids = [i for i in ids if i != passenger_id]
            self._set(f"passengers_for_voyageur:{voyageur_id}", ids, ttl=7200)

    # ------------------------------------------------------------------ #
    # Cache helpers
    # ------------------------------------------------------------------ #

    _DEFAULT_TTL = 3600  # 1 hour

    def _set(self, key: str, value, ttl: int = None):
        cache.set(key, value, timeout=ttl or self._DEFAULT_TTL)
        logger.debug(f"📦 Cached {key}")

    def _get(self, key: str):
        return cache.get(key)


# ------------------------------------------------------------------ #
# Public API
# ------------------------------------------------------------------ #

_consumer_instance = None


def start_reservation_consumer():
    global _consumer_instance
    if _consumer_instance is None:
        _consumer_instance = ReservationKafkaConsumer()
        _consumer_instance.start()
    return _consumer_instance


def stop_reservation_consumer():
    global _consumer_instance
    if _consumer_instance:
        _consumer_instance.stop()
        _consumer_instance = None