const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const bodyParser = require('body-parser');
require('dotenv').config();

const paymentRoutes = require('./routes/paymentRoutes');
const connectDB = require('./config/database');
const eurekaClient = require('./eurekaClient');

class App {
  constructor() {
    this.app = express();
    this.setupMiddleware();
    this.setupDatabase();
    this.setupRoutes();
    this.setupEureka();
  }

  setupMiddleware() {
    this.app.use(cors());
    
    // Raw body pour webhook
    this.app.use('/webhooks', bodyParser.raw({ type: 'application/json' }));
    
    // JSON parser pour les autres routes
    this.app.use(bodyParser.json());
    this.app.use(bodyParser.urlencoded({ extended: true }));
    
    this.app.use((req, res, next) => {
      console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
      next();
    });
  }

  async setupDatabase() {
    await connectDB();
  }

  setupEureka() {
    console.log('\n🔵 Starting Eureka client for MS-PAIEMENT...');
    console.log('   Server: http://localhost:8888/eureka/');
    console.log('   Host: localhost');
    console.log('   Port: 3003');
    
    eurekaClient.start((error) => {
      if (error) {
        console.error('❌ Failed to start Eureka client:', error.message);
      } else {
        console.log('✅ MS-PAIEMENT successfully registered with Eureka!');
      }
    });
  }

  setupRoutes() {
    this.app.use('/', paymentRoutes);
    
    this.app.get('/', (req, res) => {
      res.json({
        service: 'ms-paiement',
        version: '1.0.0',
        status: 'running',
        endpoints: [
          'POST /api/payments/create-payment',
          'POST /webhooks/chargily',
          'GET /api/payments/payment-status/:paymentId',
          'POST /api/payments/refund/:paymentId',
          'GET /api/payments/reservation/:reservationId/payments'
        ]
      });
    });
  }

  start() {
    const PORT = process.env.PORT || 3003;
    this.app.listen(PORT, () => {
      console.log(`\n✅ Service de paiement démarré sur le port ${PORT}`);
      console.log(`📝 Environnement: ${process.env.NODE_ENV || 'development'}`);
    });
  }
}

module.exports = App;