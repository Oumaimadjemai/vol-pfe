# ms-paiement/Dockerfile

FROM node:18-alpine

WORKDIR /app

# Copier package files (pour optimiser le cache)
COPY package*.json ./

# Installer les dépendances
RUN npm install && npm cache clean --force

# Copier l'application
COPY . .

# Copier le fichier .env (si existant)
COPY .env .env

# Créer un utilisateur non-root pour la sécurité
RUN addgroup -g 1001 -S appgroup && \
    adduser -S appuser -u 1001 -G appgroup && \
    chown -R appuser:appgroup /app

# Passer à l'utilisateur non-root
USER appuser

# Exposer le port (3003 pour ms-paiement)
EXPOSE 3003

# Commande de démarrage
CMD ["npm", "start"]