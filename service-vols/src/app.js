/* // Configuration de l'application Express
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const flightController = require('./controllers/flightController');
const authMiddleware = require('./middleware/authMiddleware');

const app = express();

// Middleware globaux
app.use(helmet());
app.use(cors());
app.use(express.json());

// Route de test (publique)
app.get('/Vols', (req, res) => {
    res.json({ 
        status: 'OK', 
        service: 'Service Vols',
        time: new Date().toISOString()
    });
});

app.get('/api/test-amadeus', async (req, res) => {
    try {
        const amadeusService = require('./services/amadeusService');
        const token = await amadeusService.getAccessToken();
        res.json({ 
            success: true, 
            message: "Connexion Amadeus OK", 
            token_obtenu: !!token 
        });
    } catch (error) {
        res.json({ 
            success: false, 
            message: "Erreur Amadeus", 
            error: error.message 
        });
    }
});


app.get('/api/flights/search', flightController.searchFlights);

// Routes protégées
//app.get('/api/flights/search', authMiddleware, flightController.searchFlights);
app.get('/api/flights/:flightId', authMiddleware, flightController.getFlightDetails);
app.get('/api/flights/:flightId/availability', authMiddleware, flightController.checkAvailability);
//app.get('/api/flights/search', flightController.searchFlights);
app.get("/api/airports", flightController.getAirports);
app.post('/search-multi', flightController.searchMultiDestination);
app.get('/api/flights/:flightId/availability', authMiddleware, flightController.checkAvailability);
// Gestion 404
app.use('*', (req, res) => {
    res.status(404).json({ message: 'Route non trouvée' });
});

module.exports = app; */
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const flightController = require('./controllers/flightController');
const authMiddleware = require('./middleware/authMiddleware');

const app = express();

// Middleware 
app.use(helmet());
app.use(cors());
app.use(express.json());

// Route de test
app.get('/Vols', (req, res) => {
    res.json({ 
        status: 'OK', 
        service: 'Service Vols',
        time: new Date().toISOString()
    });
});

// Test Amadeus
app.get('/api/test-amadeus', async (req, res) => {
    try {
        const amadeusService = require('./services/amadeusService');
        const token = await amadeusService.getAccessToken();
        res.json({ 
            success: true, 
            message: "Connexion Amadeus OK", 
            token_obtenu: !!token 
        });
    } catch (error) {
        res.json({ 
            success: false, 
            message: "Erreur Amadeus", 
            error: error.message 
        });
    }
});

// ===== ROUTES PRINCIPALES =====
// Aéroports
app.get('/api/airports', flightController.getAirports);

// Recherche vols (aller simple / aller-retour)
app.get('/api/flights/search', flightController.searchFlights);

// Recherche multi-destination 
app.post('/api/flights/multi-destination', flightController.searchMultiDestination);

// Routes protégées
//app.get('/api/flights/:flightId', authMiddleware, flightController.getFlightDetails);
app.get('/api/flights/:flightId/availability',  flightController.checkAvailability);

// Gestion 404
app.use('*', (req, res) => {
    res.status(404).json({ message: 'Route non trouvée' });
});

module.exports = app;