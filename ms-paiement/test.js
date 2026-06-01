// ms-paiement/test-kafka.js
const kafkaProducer = require('./src/services/kafkaProducer');

async function test() {
  console.log('🧪 Test Kafka Producer...');
  
  await kafkaProducer.connect();
  
  const testMessage = {
    event_type: 'payment.confirmed',
    payload: {
      reservationId: '999',
      paymentId: 'test-123',
      amount: 1000,
      status: 'COMPLETED',
      paymentMethod: 'CIB'
    },
    source: 'test',
    timestamp: new Date().toISOString()
  };
  
  const result = await kafkaProducer.sendPaymentConfirmed(testMessage.payload);
  
  if (result) {
    console.log('✅ Message envoyé avec succès!');
  } else {
    console.log('❌ Échec envoi message');
  }
  
  await kafkaProducer.disconnect();
  process.exit(0);
}

test().catch(console.error);