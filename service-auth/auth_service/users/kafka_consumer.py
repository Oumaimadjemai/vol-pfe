# service-auth/kafka_consumer.py
import logging
from django.db import transaction
from kafka_utils import KafkaConsumerBase

logger = logging.getLogger(__name__)


class AuthServiceConsumer(KafkaConsumerBase):
    """Consumer for auth service - listens for passport verification results"""
    
    def __init__(self):
        super().__init__(
            topics=['passport-verification-results', 'user-events', 'voyageur-events'],
            group_id='auth-service-group'
        )
    
    def process_message(self, event):
        """Process incoming Kafka messages"""
        event_type = event.get('event_type')
        payload = event.get('payload', {})
        source = event.get('source', 'unknown')
        
        logger.info(f"📥 Processing event: {event_type} from {source}")
        
        if event_type == 'PASSPORT_VERIFIED':
            self._update_passport_status(payload)
        elif event_type == 'PASSPORT_REJECTED':
            self._handle_passport_rejection(payload)
        elif event_type == 'USER_UPDATED':
            self._sync_user_data(payload)
        elif event_type == 'VOYAGEUR_UPDATED':
            self._sync_voyageur_data(payload)
    
    def _update_passport_status(self, payload):
        """Update voyageur passport verification status"""
        from .models import Voyageur
        
        voyageur_id = payload.get('voyageur_id')
        verified = payload.get('verified', False)
        score = payload.get('score', 0.0)
        details = payload.get('details', {})
        
        try:
            with transaction.atomic():
                voyageur = Voyageur.objects.select_for_update().get(id=voyageur_id)
                voyageur.passport_verified = verified
                voyageur.passport_verification_score = score
                voyageur.passport_verification_details = details  # You may need to add this field
                voyageur.save()
                logger.info(f"✅ Updated voyageur {voyageur_id}: passport_verified={verified}, score={score}")
        except Voyageur.DoesNotExist:
            logger.error(f"❌ Voyageur {voyageur_id} not found")
        except Exception as e:
            logger.error(f"❌ Failed to update voyageur: {e}")
    
    def _handle_passport_rejection(self, payload):
        """Handle rejected passport"""
        voyageur_id = payload.get('voyageur_id')
        reason = payload.get('reason', 'No reason provided')
        logger.warning(f"⚠️ Passport rejected for voyageur {voyageur_id}: {reason}")
    
    def _sync_user_data(self, payload):
        """Sync user data from other services"""
        logger.info(f"🔄 User data sync: {payload.get('user_id')}")
    
    def _sync_voyageur_data(self, payload):
        """Sync voyageur data from other services"""
        logger.info(f"🔄 Voyageur data sync: {payload.get('voyageur_id')}")


# Singleton instance
_auth_consumer = None

def start_auth_consumer():
    """Start the auth service Kafka consumer"""
    global _auth_consumer
    if _auth_consumer is None:
        _auth_consumer = AuthServiceConsumer()
        _auth_consumer.start()
    return _auth_consumer

def stop_auth_consumer():
    """Stop the auth service Kafka consumer"""
    global _auth_consumer
    if _auth_consumer:
        _auth_consumer.stop()
        _auth_consumer = None