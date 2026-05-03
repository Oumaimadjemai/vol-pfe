// src/models/Payment.js
const mongoose = require('mongoose');

/**
 * Schéma de paiement pour tracer toutes les transactions
 */
const paymentSchema = new mongoose.Schema({
  // Identifiant unique de la réservation (lié au ms-reservation)
  reservationId: {
    type: String,
    required: true,
    index: true
  },
  
  // Informations du paiement
  amount: {
    type: Number,
    required: true
  },
  currency: {
    type: String,
    default: 'DZD',
    enum: ['DZD', 'EUR', 'USD']
  },
  
  // Statuts du paiement
  status: {
    type: String,
    enum: ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'REFUNDED', 'CANCELLED'],
    default: 'PENDING'
  },
  
  // Méthode de paiement utilisée
  paymentMethod: {
    type: String,
    enum: ['CIB', 'EDAHABIA', 'SATIM', 'CHARGILY', 'CASH'],
    required: true
  },
  
  // Références externess
  transactionId: {
    type: String,
    sparse: true
  },
  paymentIntentId: {
    type: String,
    sparse: true
  },
  
  // Données de la carte (cryptées en production)
  cardInfo: {
    last4: String,     // 4 derniers chiffres
    cardType: String,  // VISA, Mastercard, etc.
    expiryMonth: String,
    expiryYear: String
  },
  
  // Webhook et callbacks
  webhookReceived: {
    type: Boolean,
    default: false
  },
  webhookData: {
    type: mongoose.Schema.Types.Mixed
  },
  
  // Timestamps
  paymentDate: Date,
  confirmedAt: Date,
  failedAt: Date,
  
  // Messages d'erreur
  errorMessage: String,
  errorCode: String,
  
  // Métadonnées
  metadata: {
    type: mongoose.Schema.Types.Mixed,
    default: {}
  }
}, {
  timestamps: true // Ajoute createdAt et updatedAt automatiquement
});

// Index pour améliorer les performances des recherches
paymentSchema.index({ transactionId: 1 });
paymentSchema.index({ paymentIntentId: 1 });
paymentSchema.index({ status: 1, createdAt: -1 });

module.exports = mongoose.model('Payment', paymentSchema);