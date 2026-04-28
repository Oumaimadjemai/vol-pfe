#users/kafka_utils.py
import json
import logging
import threading
import os
from datetime import datetime
import uuid
from kafka import KafkaProducer, KafkaConsumer
from django.conf import settings

logger = logging.getLogger(__name__)

class KafkaClient:
    """Single Kafka client for publishing events"""
    
    _producer = None
    
    @classmethod
    def get_producer(cls):
        if cls._producer is None:
            try:
                bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
                cls._producer = KafkaProducer(
                    bootstrap_servers=bootstrap_servers.split(','),
                    value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                    compression_type='gzip',
                    acks='all',
                    retries=3,
                    max_request_size=10485760  # 10MB
                )
                logger.info(f"✅ Kafka producer connected to {bootstrap_servers}")
            except Exception as e:
                logger.error(f"❌ Failed to connect Kafka: {e}")
        return cls._producer
    
    @classmethod
    def send_event(cls, topic, event_type, payload, source_service):
        """Send an event to Kafka topic"""
        producer = cls.get_producer()
        if not producer:
            return False
        
        message = {
            'event_id': str(uuid.uuid4()),
            'event_type': event_type,
            'source': source_service,
            'payload': payload,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            future = producer.send(topic, value=message)
            result = future.get(timeout=10)
            logger.info(f"📤 Event sent: {event_type} -> {topic} (partition: {result.partition})")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send event: {e}")
            return False


class KafkaConsumerBase:
    """Base consumer class - extend this for your service"""
    
    def __init__(self, topics, group_id):
        self.topics = topics
        self.group_id = group_id
        self.consumer = None
        self.running = False
        self.thread = None
    
    def start(self):
        """Start consumer in background thread"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._consume, daemon=True)
        self.thread.start()
        logger.info(f"✅ Kafka consumer started for {self.group_id} on topics: {self.topics}")
    
    def _consume(self):
        """Main consumption loop"""
        try:
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
            self.consumer = KafkaConsumer(
                *self.topics,
                bootstrap_servers=bootstrap_servers.split(','),
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id=self.group_id,
                session_timeout_ms=30000,
                max_poll_records=100
            )
            
            logger.info(f"🔄 Consumer listening on: {self.topics}")
            
            for message in self.consumer:
                if not self.running:
                    break
                self.process_message(message.value)
                
        except Exception as e:
            logger.error(f"❌ Consumer error: {e}")
            self.running = False
    
    def process_message(self, event):
        """Override this method in child classes"""
        raise NotImplementedError("Subclasses must implement process_message")
    
    def stop(self):
        """Stop the consumer"""
        self.running = False
        if self.consumer:
            self.consumer.close()
        logger.info("🛑 Consumer stopped")


# Singleton producer instance
kafka = KafkaClient()