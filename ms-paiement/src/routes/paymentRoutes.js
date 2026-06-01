const express = require('express');
const router = express.Router();
const PaymentController = require('../controllers/PaymentController');

const paymentController = new PaymentController();

// Routes API
router.post('/api/payments/create-payment', (req, res) => paymentController.createPayment(req, res));
router.get('/api/payments/payment-status/:paymentId', (req, res) => paymentController.getPaymentStatus(req, res));
router.get('/api/payments/reservation/:reservationId/payments', (req, res) => paymentController.getReservationPayments(req, res));
router.post('/api/payments/refund/:paymentId', (req, res) => paymentController.refundPayment(req, res));

// Webhook route
router.post('/webhooks/chargily', (req, res) => paymentController.handleWebhook(req, res));

// Health check
router.get('/api/payments/health', (req, res) => {
  res.status(200).json({ 
    status: 'UP', 
    service: 'ms-paiement',
    timestamp: new Date().toISOString()
  });
});

module.exports = router;