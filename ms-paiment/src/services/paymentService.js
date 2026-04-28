const axios = require('axios');
const crypto = require('crypto');

class PaymentService {
  constructor() {
    this.apiKey = process.env.CHARGILY_API_KEY;
    this.secretKey = process.env.CHARGILY_SECRET_KEY;
    this.apiUrl = process.env.CHARGILY_API_URL;
    this.webhookSecret = process.env.CHARGILY_WEBHOOK_SECRET;
  }

  async createPaymentSession(paymentData) {
    try {
      const {
        amount,
        currency = 'dzd',
        reservationId,
        customerName,
        customerEmail,
        successUrl,
        cancelUrl,
        webhookUrl
      } = paymentData;

      const payload = {
        amount: amount,
        currency: currency.toLowerCase(),
        success_url: successUrl || 'http://localhost:3000/payment/success',// menba3d nchof ida ndirhom front 
        failure_url: cancelUrl || 'http://localhost:3000/payment/cancel',
        webhook_endpoint: webhookUrl || 'http://localhost:3003/webhooks/chargily',
        metadata: {
          reservationId: reservationId,
          customerName: customerName,
          customerEmail: customerEmail
        }
      };

      console.log(' Payload:', JSON.stringify(payload, null, 2));

      const response = await axios.post(
        `${this.apiUrl}/checkouts`,
        payload,
        {
          headers: {
            'Authorization': `Bearer ${this.apiKey}`,
            'Content-Type': 'application/json'
          }
        }
      );

      console.log(' Réponse:', response.data);

      return {
        success: true,
        paymentUrl: response.data.checkout_url,
        paymentIntentId: response.data.id,
        transactionId: response.data.id
      };

    } catch (error) {
      console.error(' Erreur Chargily:', error.response?.data || error.message);
      return {
        success: false,
        error: error.response?.data?.message || error.message || 'Erreur de création de paiement'
      };
    }
  }

  verifyWebhookSignature(signature, rawPayload) {
    try {
      const expectedSignature = crypto
        .createHmac('sha256', this.webhookSecret)
        .update(rawPayload)
        .digest('hex');
      
      console.log(' Signature reçue:', signature);
      console.log(' Signature attendue:', expectedSignature);
      
      const isValid = signature === expectedSignature;
      
      if (isValid) {
        console.log(' Signature valide');
      } else {
        console.log(' Signature invalide');
      }
      
      return isValid;
    } catch (error) {
      console.error('Erreur vérification signature:', error);
      return false;
    }
  }

  async getPaymentStatus(paymentIntentId) {
    try {
      const response = await axios.get(
        `${this.apiUrl}/checkouts/${paymentIntentId}`,
        {
          headers: {
            'Authorization': `Bearer ${this.apiKey}`
          }
        }
      );

      return {
        success: true,
        status: response.data.status,
        amount: response.data.amount,
        currency: response.data.currency,
        paymentMethod: response.data.payment_method
      };

    } catch (error) {
      console.error('Erreur récupération statut:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  async refundPayment(paymentIntentId, amount = null) {
    try {
      const payload = amount ? { amount } : {};
      
      const response = await axios.post(
        `${this.apiUrl}/checkouts/${paymentIntentId}/refund`,
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
      console.error('Erreur remboursement:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }
}

module.exports = PaymentService;