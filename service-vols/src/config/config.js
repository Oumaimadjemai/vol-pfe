// Configuration du service
require('dotenv').config();

module.exports = {
    port: process.env.PORT || 3002,
    
    amadeus: {
        apiKey: process.env.AMADEUS_API_KEY,
        apiSecret: process.env.AMADEUS_API_SECRET,
        environment: process.env.AMADEUS_ENVIRONMENT || 'test'
    },
    
    jwt: {
        secret: process.env.JWT_SECRET || 'secret_dev'
    }
};