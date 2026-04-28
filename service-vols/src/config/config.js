// config/config.js
require('dotenv').config();

module.exports = {
    port: process.env.PORT || 3002,
    
    // Amadeus configuration (add this)
    amadeus: {
        apiKey: process.env.AMADEUS_API_KEY,
        apiSecret: process.env.AMADEUS_API_SECRET,
        environment: process.env.AMADEUS_ENVIRONMENT || 'test'
    },
    
    // RapidAPI/Skyscanner configuration
    rapidapi: {
        key: process.env.RAPIDAPI_KEY,
        host: process.env.RAPIDAPI_HOST || 'skyscanner-api.p.rapidapi.com',
        baseUrl: 'https://skyscanner-api.p.rapidapi.com'
    },
    
    jwt: {
        secret: process.env.JWT_SECRET || 'secret_dev'
    }
};