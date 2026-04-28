const Payment = require('../models/Payment');
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

      // ============================================================
      //  CAS 2: Paiement à la livraison (DELIVERY)
      // ============================================================
      else if (paymentMethod === 'DELIVERY' || paymentMethod === 'delivery') {
        payment.status = 'PENDING';
        payment.metadata.paymentType = 'delivery';
        await payment.save();
        
        // Notifier le service de réservation
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
      //  CAS 3: Paiement en espèces (CASH)
      // ============================================================
      else if (paymentMethod === 'CASH' || paymentMethod === 'cash') {
        payment.status = 'PENDING';
        payment.metadata.paymentType = 'cash';
        await payment.save();
        
        await this.webhookService.notifyReservationService({
          reservationId: payment.reservationId,
          paymentId: payment._id,
          amount: payment.amount,
          status: 'PENDING',
          paymentMethod: 'CASH'
        });
        
        return res.status(200).json({
          success: true,
          paymentId: payment._id,
          status: 'PENDING',
          message: 'Paiement en espèces confirmé'
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
      const rawPayload = req.body;
      
      console.log(' ========== WEBHOOK RECU ==========');
      console.log(' Signature:', signature);
      
      const isValid = true; // Temporaire pour test
      
      if (!isValid) {
        console.log(' Signature invalide, requête ignorée');
        return res.status(403).json({ error: 'Signature invalide' });
      }
      
      console.log(' Signature valide');
      
      const event = JSON.parse(rawPayload);
      console.log(' Type événement:', event.type);
      
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
              console.log(' Notification ms-reservation: réussie ');
            } else {
              console.log(' Notification ms-reservation: échouée', notificationResult.error);
            }
          } else {
            console.log(` Paiement non trouvé pour ID: ${checkout.id}`);
          }
          break;
          
        case 'checkout.failed':
          console.log(' Paiement échoué');
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
            console.log(` Paiement ${failedPayment._id} échoué`);
          }
          break;
          
        case 'checkout.expired':
          console.log(' Session de paiement expirée');
          const expiredCheckout = event.data;
          
          const expiredPayment = await Payment.findOne({ 
            paymentIntentId: expiredCheckout.id 
          });
          
          if (expiredPayment) {
            expiredPayment.status = 'CANCELLED';
            expiredPayment.webhookData = event;
            await expiredPayment.save();
            console.log(` Paiement ${expiredPayment._id} expiré`);
          }
          break;
          
        default:
          console.log(` Événement non traité: ${event.type}`);
      }
      
      return res.status(200).json({ received: true });
      
    } catch (error) {
      console.error(' Erreur traitement webhook:', error);
      return res.status(500).json({ error: error.message });
    }
  }

  async refundPayment(req, res) {
    try {
      const { paymentId } = req.params;
      const { amount } = req.body;
      
      const payment = await Payment.findById(paymentId);
      
      if (!payment) {
        return res.status(404).json({ error: 'Paiement non trouvé' });
      }
      
      if (payment.status !== 'COMPLETED') {
        return res.status(400).json({ error: 'Seul un paiement complété peut être remboursé' });
      }
      
      const refund = await this.chargilyService.refundPayment(payment.paymentIntentId, amount);
      
      if (!refund.success) {
        return res.status(500).json({ error: refund.error });
      }
      
      payment.status = 'REFUNDED';
      payment.metadata.refundId = refund.refundId;
      payment.metadata.refundAmount = amount || payment.amount;
      await payment.save();
      
      await this.webhookService.notifyReservationService({
        reservationId: payment.reservationId,
        paymentId: payment._id,
        transactionId: payment.transactionId,
        amount: payment.amount,
        status: 'REFUNDED',
        paymentMethod: payment.paymentMethod,
        metadata: { refundAmount: amount || payment.amount }
      });
      
      return res.status(200).json({
        success: true,
        message: 'Paiement remboursé avec succès',
        refundId: refund.refundId
      });
    } catch (error) {
      console.error(' Erreur refundPayment:', error);
      return res.status(500).json({ error: error.message });
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