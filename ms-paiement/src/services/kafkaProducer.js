// src/services/kafkaProducer.js
const { Kafka } = require('kafkajs');

class KafkaProducer {
  constructor() {
    this.kafka = new Kafka({
      clientId: 'ms-paiement',
      brokers: ['kafka:29092'],  // ⭐ nafs broker li f docker-compose
    });
    this.producer = null;
    this.connected = false;
  }

  async connect() {
    if (this.connected) return;
    
    try {
      this.producer = this.kafka.producer();
      await this.producer.connect();
      this.connected = true;
      console.log('✅ Kafka Producer connecté (ms-paiement)');
    } catch (error) {
      console.error('❌ Erreur connexion Kafka:', error.message);
    }
  }

  async sendPaymentConfirmed(paymentData) {
    await this.connect();
    
    if (!this.producer) {
      console.log('⚠️ Kafka non disponible, message perdu');
      return false;
    }
    
    try {
      await this.producer.send({
        topic: 'payment.confirmed',
        messages: [
          {
            key: String(paymentData.reservationId),
            value: JSON.stringify(paymentData),
          },
        ],
      });
      console.log(`📤 [Kafka] Message envoyé: réservation ${paymentData.reservationId}`);
      return true;
    } catch (error) {
      console.error('❌ [Kafka] Erreur envoi:', error.message);
      return false;
    }
  }

  async disconnect() {
    if (this.producer && this.connected) {
      await this.producer.disconnect();
      this.connected = false;
      console.log('Kafka Producer déconnecté');
    }
  }
}

module.exports = new KafkaProducer();