const amadeusService = require('../services/amadeusService');

const flightController = {
    
    // 1. RECHERCHE ALLER SIMPLE / ALLER-RETOUR
    // ===========================================
    searchFlights: async (req, res) => {
        try {
            const { 
                origin, destination, departureDate, returnDate,
                adults = 1, children = 0, infants = 0,
                travelClass = 'ECONOMY',
                nonStop = 'false', refundable = 'false', baggage = 'false',
                currency = 'DZD'
            } = req.query;

            if (!origin || !destination || !departureDate) {
                return res.status(400).json({
                    success: false,
                    message: 'Paramètres requis: origin, destination, departureDate'
                });
            }

            console.log(' Recherche:', { origin, destination, departureDate, returnDate, adults, children, infants, travelClass, nonStop, refundable, baggage });

            const result = await amadeusService.searchFlights({
                origin: origin.toUpperCase(),
                destination: destination.toUpperCase(),
                departureDate,
                returnDate: returnDate || null,
                adults: parseInt(adults),
                children: parseInt(children),
                infants: parseInt(infants),
                travelClass: travelClass.toUpperCase(),
                nonStop: nonStop === 'true',
                refundable: refundable === 'true',
                baggage: baggage === 'true',
                currency
            });

            res.json({
                success: true,
                data: result
            });

        } catch (error) {
            console.error(' Erreur searchFlights:', error);
            res.status(error.status || 500).json({
                success: false,
                message: error.message || 'Erreur lors de la recherche'
            });
        }
    },

    // ===========================================
    // 2. RECHERCHE MULTI-DESTINATION
searchMultiDestination: async (req, res) => {
    try {
        const { 
            flights, adults = 1, children = 0, infants = 0,
            travelClass = 'ECONOMY',
            nonStop = 'false', refundable = 'false', baggage = 'false',
            currency = 'DZD'
        } = req.body;

        console.log(' Body reçu:', req.body);

        if (!flights || !Array.isArray(flights) || flights.length < 2) {
            return res.status(400).json({
                success: false,
                message: 'Minimum 2 segments requis pour multi-destination'
            });
        }

        // Formater les vols
        const formattedFlights = flights.map((flight, index) => {
            const origin = flight.origin || flight.from;
            const destination = flight.destination || flight.to;
            const departureDate = flight.date || flight.departureDate;

            if (!origin || !destination || !departureDate) {
                throw new Error(`Vol ${index + 1}: champs manquants`);
            }

            return {
                origin: origin.toUpperCase(),
                destination: destination.toUpperCase(),
                departureDate
            };
        });

        console.log(' Vols formatés:', formattedFlights);

        //  APPEL AU SERVICE
        const results = await amadeusService.searchMultiDestination(
            formattedFlights,
            { adults: parseInt(adults), children: parseInt(children), infants: parseInt(infants) },
            travelClass.toUpperCase(),
            {
                nonStop: nonStop === 'true',
                refundable: refundable === 'true',
                baggage: baggage === 'true',
                currency
            }
        );

        //  GÉNÉRER LES COMBINAISONS
        let combinations = [];
        if (results && results.segments && results.segments.length > 0) {
            combinations = await amadeusService.generateCombinations(results.segments);
            console.log(` ${combinations.length} combinaisons générées`);
        } else {
            console.log(' Pas de segments à combiner');
        }

        // Retourner les résultats
        res.json({
            success: true,
            data: {
                tripType: "MULTI_DESTINATION",
                searchParams: {
                    flights: formattedFlights,
                    passengers: { adults, children, infants },
                    travelClass: travelClass.toUpperCase(),
                    filters: { nonStop, refundable, baggage }
                },
                segments: results.segments || [],
                combinations: combinations || [],
                totalCombinations: combinations.length || 0
            }
        });

    } catch (error) {
        console.error(' Erreur searchMultiDestination:', error);
        res.status(500).json({
            success: false,
            message: error.message || 'Erreur recherche multi-destination'
        });
    }
},

//  RÉCUPÉRER LES AÉROPORTS 
// ===========================================
getAirports: async (req, res) => {
    try {
        const { search, popular = 'false' } = req.query;
        
        const airportService = require('../services/airportService');
        
        let airports;
        if (popular === 'true') {
            // Aéroports populaires
            airports = await airportService.getPopularAirports();
        } else if (search && search.length >= 2) {
            // Recherche par mot-clé (minimum 2 caractères)
            airports = await airportService.searchAirports(search, 20);
        } else {
            // Par défaut, retourner les populaires
            airports = await airportService.getPopularAirports();
        }
        
        res.json({
            success: true,
            count: airports.length,
            data: airports
        });
        
    } catch (error) {
        console.error(' Erreur getAirports:', error);
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
},
   
    //  VÉRIFIER DISPONIBILITÉ
    // ===========================================
    checkAvailability: async (req, res) => {
        try {
            const { flightId } = req.params;
            
            if (!flightId) {
                return res.status(400).json({
                    success: false,
                    message: 'ID du vol requis'
                });
            }
            
            const availability = await amadeusService.checkAvailability(flightId);
            
            res.json({
                success: true,
                data: availability
            });
        } catch (error) {
            res.status(500).json({
                success: false,
                message: error.message
            });
        }
    }
};

module.exports = flightController;