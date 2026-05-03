const { Kafka } = require('kafkajs');

// ⭐ Configuration broker (7sab environnement)
const brokers = process.env.KAFKA_BOOTSTRAP_SERVERS || 'kafka:29092';

const kafka = new Kafka({
  clientId: 'ms-paiement',
  brokers: [brokers],
});

const producer = kafka.producer();

// ⭐ Connecter le producer
const connectProducer = async () => {
  try {
    await producer.connect();
    console.log('✅ Kafka Producer connecté (ms-paiement)');
  } catch (error) {
    console.error('❌ Erreur connexion Kafka:', error.message);
  }
};

// ⭐ Envoyer un événement
const sendEvent = async (topic, event) => {
  try {
    await producer.send({
      topic,
      messages: [
        { value: JSON.stringify(event) }
      ]
    });
    console.log(`📤 [KAFKA] Event envoyé sur le topic ${topic}:`, event);
  } catch (err) {
    console.error('❌ Erreur lors de l\'envoi de l\'event Kafka :', err);
  }
};

// ⭐ Fonction spécifique pour payment.confirmed
const sendPaymentConfirmed = async (paymentData) => {
  const event = {
    event_type: 'payment.confirmed',
    payload: paymentData,
    source: 'ms-paiement',
    timestamp: new Date().toISOString()
  };
  
  return await sendEvent('payment.confirmed', event);
};

module.exports = {
  connectProducer,
  sendEvent,
  sendPaymentConfirmed
};