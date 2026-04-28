const {Kafka} = require('kafkajs');
const kafka = new Kafka({
  clientId: 'service-vols',
  brokers: [process.env.KAFKA_BOOTSTRAP_SERVERS || 'kafka:29092'],
});
const producer = kafka.producer();
const connectProducer = async()=>{
    await producer.connect();
    console.log('Kafka Producer connecté');
};
const sendEvent = async (topic, event)=>{
    try {
        await producer.send({
            topic,
            messages:[
                {value:JSON.stringify(event)

                }
            ]
        });
        console.log(`Event envoyé sur le topic ${topic} :`, event);
    } catch (err){
        console.error('Erreur lors de l\'envoi de l\'event Kafka :', err);
    }
    };
module.exports={
    connectProducer,
    sendEvent
};
