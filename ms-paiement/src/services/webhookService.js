const axios = require('axios');
const crypto = require('crypto');
const kafkaProducer = require('./kafkaProducer');

class WebhookService {
  constructor() {
    this.msReservationUrl = process.env.MS_RESERVATION_URL;
    this.jwtToken = process.env.JWT_TOKEN;
    this.webhookSecret = process.env.WEBHOOK_SECRET;
    this.retryAttempts = 3;
    this.retryDelay = 2000;
    this.useKafka = process.env.USE_KAFKA === 'true' || true; // ⭐ Activer Kafka par défaut
  }

  async notifyReservationService(paymentData) {
    const {
      reservationId,
      paymentId,
      transactionId,
      amount,
      status,
      paymentMethod,
      metadata
    } = paymentData;

    const webhookPayload = {
      event: 'payment.confirmed',
      reservationId: reservationId,
      paymentId: paymentId,
      transactionId: transactionId,
      amount: amount,
      currency: 'DZD',
      status: status,
      paymentMethod: paymentMethod,
      timestamp: new Date().toISOString(),
      metadata: metadata
    };

    // ============================================================
    //  CAS 1: Envoi via KAFKA (asynchrone - recommandé)
    // ============================================================
    if (this.useKafka) {
      console.log(`📡 [KAFKA] Envoi notification pour réservation ${reservationId}`);
      
      const result = await kafkaProducer.sendPaymentConfirmed(webhookPayload);
      
      if (result) {
        console.log(`✅ [KAFKA] Message envoyé avec succès: réservation ${reservationId}`);
        return {
          success: true,
          response: { message: 'sent to kafka', event: 'payment.confirmed' }
        };
      } else {
        console.log(`❌ [KAFKA] Échec envoi: réservation ${reservationId}, fallback HTTP`);
        // Fallback to HTTP if Kafka fails
        return await this.sendViaHttp(webhookPayload, reservationId);
      }
    }

    // ============================================================
    //  CAS 2: Envoi via HTTP direct (fallback)
    // ============================================================
    return await this.sendViaHttp(webhookPayload, reservationId);
  }

  /**
   * Envoi via HTTP (ancienne méthode - fallback)
   */
  async sendViaHttp(webhookPayload, reservationId) {
    const confirmPriceUrl = `${this.msReservationUrl}/reservations/${reservationId}/confirm_price/`;
    
    console.log(`📡 [HTTP] Envoi webhook à: ${confirmPriceUrl}`);

    for (let attempt = 1; attempt <= this.retryAttempts; attempt++) {
      try {
        console.log(`📡 Tentative ${attempt} d'envoi HTTP...`);
        
        const response = await axios.post(
          confirmPriceUrl,  
          {}, 
          {
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${this.jwtToken}`,
              'X-Webhook-Signature': this.generateSignature(webhookPayload)
            },
            timeout: 20000
          }
        );

        if (response.status === 200 || response.status === 201) {
          console.log(`✅ [HTTP] Webhook envoyé avec succès pour réservation ${reservationId}`);
          console.log(`📝 Réponse:`, response.data);
          return {
            success: true,
            response: response.data
          };
        }

      } catch (error) {
        console.error(`❌ Tentative ${attempt} échouée:`, error.response?.data || error.message);
        
        if (attempt === this.retryAttempts) {
          await this.saveFailedWebhook(webhookPayload, error.message);
          return {
            success: false,
            error: error.message,
            webhookData: webhookPayload
          };
        }
        
        await this.sleep(this.retryDelay * attempt);
      }
    }
  }

  generateSignature(payload) {
    const secret = this.webhookSecret;
    return crypto
      .createHmac('sha256', secret)
      .update(JSON.stringify(payload))
      .digest('hex');
  }

  async saveFailedWebhook(payload, error) {
    console.log('💾 Sauvegarde webhook échoué:', { payload, error });
  }

  async retryFailedWebhooks() {
    console.log('🔄 Retraitement des webhooks échoués...');
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

module.exports = WebhookService;