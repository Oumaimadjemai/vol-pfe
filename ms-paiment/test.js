const { MongoClient } = require('mongodb');

const uri ="mongodb://TaibiNarimane:paymentvol2026@cluster0-shard-00-00.q662isg.mongodb.net:27017,cluster0-shard-00-01.q662isg.mongodb.net:27017,cluster0-shard-00-02.q662isg.mongodb.net:27017/PaymentDB?ssl=true&replicaSet=atlas-l6uueg-shard-0&authSource=admin&retryWrites=true&w=majority";

async function run() {
  try {
    const client = new MongoClient(uri);
    await client.connect();
    console.log("✅ Connecté!");
    await client.close();
  } catch (err) {
    console.error("❌ Erreur:", err.message);
  }
}
run();