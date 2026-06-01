const Payment = require('../models/payment');
const ChargilyService = require('../services/paymentService');
const WebhookService = require('../services/webhookService');

class PaymentController {
  constructor() {
    this.chargilyService = new ChargilyService();
    this.webhookService = new WebhookService();
  }

  async createPayment(req, res) {
    try {
      const { reservationId, amount, customerName, customerEmail, paymentMethod } = req.body;

      console.log(' Données reçues:', { reservationId, amount, customerName, customerEmail, paymentMethod });

      if (!reservationId || !amount) {
        return res.status(400).json({ error: 'reservationId et amount sont requis' });
      }

      const payment = new Payment({
        reservationId,
        amount,
        paymentMethod: paymentMethod || 'CIB',
        status: 'PENDING',
        metadata: { customerName, customerEmail },
      });
      
      await payment.save();
      console.log(`💰 Paiement créé: ${payment._id}`);

      // ============================================================
      //  CAS 1: Paiement par Carte (CIB) - via Chargily
      // ============================================================
      if (paymentMethod === 'CIB' || paymentMethod === 'cib') {
        const session = await this.chargilyService.createPaymentSession({
          amount,
          reservationId,
          customerName,
          customerEmail,
        });

        if (!session.success) {
          payment.status = 'FAILED';
          await payment.save();
          return res.status(500).json({ error: session.error });
        }

        payment.paymentIntentId = session.paymentIntentId;
        payment.transactionId = session.transactionId;
        payment.status = 'PROCESSING';
        await payment.save();

        return res.status(200).json({
          success: true,
          paymentId: payment._id,
          paymentUrl: session.paymentUrl,
          status: 'PROCESSING',
        });
      }
//  CAS 2: Paiement en espèces (CASH) - COMPLETED directement
// ============================================================
else if (paymentMethod === 'CASH' || paymentMethod === 'cash') {
  //  Status COMPLETED directement
  payment.status = 'COMPLETED';
  payment.paymentDate = new Date();
  payment.confirmedAt = new Date();
  payment.metadata.paymentType = 'cash';
  await payment.save();
  
  console.log(` Paiement CASH confirmé: ${payment._id}`);
  
  return res.status(200).json({
    success: true,
    paymentId: payment._id,
    status: 'COMPLETED',
    message: 'Paiement en espèces confirmé'
  });
}

// ============================================================
//  CAS 3: Paiement à la livraison (DELIVERY) - PENDING pour l'instant
// ============================================================
else if (paymentMethod === 'DELIVERY' || paymentMethod === 'delivery') {
  payment.status = 'PENDING';
  payment.metadata.paymentType = 'delivery';
  await payment.save();
  
  await this.webhookService.notifyReservationService({
    reservationId: payment.reservationId,
    paymentId: payment._id,
    amount: payment.amount,
    status: 'PENDING',
    paymentMethod: 'DELIVERY'
  });
  
  return res.status(200).json({
    success: true,
    paymentId: payment._id,
    status: 'PENDING',
    message: 'Paiement à la livraison confirmé'
  });
}
      
      // ============================================================
      //  CAS 4: Mode de paiement non supporté
      // ============================================================
      else {
        payment.status = 'FAILED';
        await payment.save();
        return res.status(400).json({ error: 'Mode de paiement non supporté' });
      }
      
    } catch (error) {
      console.error(' Erreur createPayment:', error);
      return res.status(500).json({ error: error.message });
    }
  }

  async getPaymentStatus(req, res) {
    try {
      const { paymentId } = req.params;
      const payment = await Payment.findById(paymentId);
      
      if (!payment) {
        return res.status(404).json({ error: 'Paiement non trouvé' });
      }

      return res.status(200).json({
        paymentId: payment._id,
        reservationId: payment.reservationId,
        status: payment.status,
        amount: payment.amount,
        paymentMethod: payment.paymentMethod,
        paymentDate: payment.paymentDate,
        confirmedAt: payment.confirmedAt,
      });
    } catch (error) {
      console.error(' Erreur getPaymentStatus:', error);
      return res.status(500).json({ error: error.message });
    }
  }

  async handleWebhook(req, res) {
  try {
    const signature = req.headers['signature'];
    
    console.log('========== WEBHOOK RECU ==========');
    console.log('Signature:', signature);
    
    //  Récupérer le body correctement
    let event;
    
    // Si le body est déjà un objet (parsé par Express)
    if (req.body && typeof req.body === 'object' && !Buffer.isBuffer(req.body)) {
      event = req.body;
    }
    // Si le body est un buffer (raw)
    else if (req.body && Buffer.isBuffer(req.body)) {
      event = JSON.parse(req.body.toString('utf8'));
    }
    // Si le body est une string
    else if (typeof req.body === 'string') {
      event = JSON.parse(req.body);
    }
    else {
      console.log(' Format body non supporté:', typeof req.body);
      return res.status(400).json({ error: 'Invalid body format' });
    }
    
    console.log('Type événement:', event.type);
    
    switch (event.type) {
      case 'checkout.paid':
        console.log('💰 Paiement réussi!');
        const checkout = event.data;
        
        const payment = await Payment.findOne({ 
          paymentIntentId: checkout.id 
        });
        
        if (payment) {
          payment.status = 'COMPLETED';
          payment.paymentDate = new Date();
          payment.confirmedAt = new Date();
          payment.webhookReceived = true;
          payment.webhookData = event;
          await payment.save();
          
          console.log(` Paiement ${payment._id} confirmé pour réservation ${payment.reservationId}`);
          
          const notificationResult = await this.webhookService.notifyReservationService({
            reservationId: payment.reservationId,
            paymentId: payment._id,
            transactionId: payment.transactionId,
            amount: payment.amount,
            status: 'COMPLETED',
            paymentMethod: payment.paymentMethod,
            metadata: payment.metadata
          });
          
          if (notificationResult.success) {
            console.log('✅ Notification ms-reservation réussie');
          } else {
            console.log('⚠️ Notification ms-reservation échouée', notificationResult.error);
          }
        } else {
          console.log(`⚠️ Paiement non trouvé pour ID: ${checkout.id}`);
        }
        break;
        
      case 'checkout.failed':
        console.log('❌ Paiement échoué');
        const failedCheckout = event.data;
        
        const failedPayment = await Payment.findOne({ 
          paymentIntentId: failedCheckout.id 
        });
        
        if (failedPayment) {
          failedPayment.status = 'FAILED';
          failedPayment.failedAt = new Date();
          failedPayment.errorMessage = 'Paiement échoué';
          failedPayment.webhookData = event;
          await failedPayment.save();
          console.log(`⚠️ Paiement ${failedPayment._id} échoué`);
        }
        break;
        
      case 'checkout.expired':
        console.log('⏰ Session de paiement expirée');
        const expiredCheckout = event.data;
        
        const expiredPayment = await Payment.findOne({ 
          paymentIntentId: expiredCheckout.id 
        });
        
        if (expiredPayment) {
          expiredPayment.status = 'CANCELLED';
          expiredPayment.webhookData = event;
          await expiredPayment.save();
          console.log(`⚠️ Paiement ${expiredPayment._id} expiré`);
        }
        break;
        
      default:
        console.log(`⚠️ Événement non traité: ${event.type}`);
    }
    
    return res.status(200).json({ received: true });
    
  } catch (error) {
    console.error('❌ Erreur traitement webhook:', error);
    return res.status(500).json({ error: error.message });
  }
}

async refundPayment(paymentIntentId, amount = null) {
  try {
    const payload = amount ? { amount } : {};
    // hadi mnb3d f mode live
    const response = await axios.post(
      `${this.apiUrl}/payments/${paymentIntentId}/refund`,
      payload,
      {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    return {
      success: true,
      refundId: response.data.id,
      status: response.data.status
    };
  } catch (error) {
    console.error('❌ Erreur remboursement:', error.response?.data || error.message);
    return {
      success: false,
      error: error.response?.data?.message || error.message
    };
  }
}
  async getReservationPayments(req, res) {
    try {
      const { reservationId } = req.params;
      const payments = await Payment.find({ reservationId }).sort({ createdAt: -1 });
      
      return res.status(200).json({
        reservationId,
        payments: payments.map(p => ({
          id: p._id,
          amount: p.amount,
          status: p.status,
          paymentMethod: p.paymentMethod,
          paymentDate: p.paymentDate,
          createdAt: p.createdAt,
        })),
      });
    } catch (error) {
      console.error(' Erreur getReservationPayments:', error);
      return res.status(500).json({ error: error.message });
    }
  }
}

module.exports = PaymentController;