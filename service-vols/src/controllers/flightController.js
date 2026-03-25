const amadeusService = require('../services/amadeusService');
const airportService = require('../services/airportService');

const flightController = {
    
    // Recherche aller simple / aller-retour
    searchFlights: async (req, res) => {
        try {
            const params = {
                origin: req.query.origin,
                destination: req.query.destination,
                departureDate: req.query.departureDate,
                returnDate: req.query.returnDate,
                adults: parseInt(req.query.adults) || 1,
                children: parseInt(req.query.children) || 0,
                infants: parseInt(req.query.infants) || 0,
                travelClass: req.query.travelClass || 'ECONOMY',
                nonStop: req.query.nonStop === 'true',
                refundable: req.query.refundable === 'true',
                baggage: req.query.baggage === 'true',
                currency: req.query.currency || 'DZD'
            };

            if (!params.origin || !params.destination || !params.departureDate) {
                return res.status(400).json({
                    success: false,
                    message: 'Paramètres requis: origin, destination, departureDate'
                });
            }

            const result = await amadeusService.searchFlights(params);
            
            res.json({
                success: true,
                data: result
            });

        } catch (error) {
            console.error('Erreur searchFlights:', error);
            res.status(error.status || 500).json({
                success: false,
                message: error.message || 'Erreur lors de la recherche'
            });
        }
    },

    // Recherche multi-destination 
searchMultiDestination: async (req, res) => {
  try {
    console.log(" Corps de la requête reçu:", JSON.stringify(req.body, null, 2));
    
    // Extraire les données des passagers de manière flexible
    let adults = 1, children = 0, infants = 0;
    
    // Format 1: { adults: 1, children: 0, infants: 0 }
    if (req.body.adults !== undefined) {
      adults = parseInt(req.body.adults) || 1;
      children = parseInt(req.body.children) || 0;
      infants = parseInt(req.body.infants) || 0;
    }
    // Format 2: { passengers: { adult: 1, child: 0, baby: 0 } }
    else if (req.body.passengers) {
      adults = parseInt(req.body.passengers.adult) || 1;
      children = parseInt(req.body.passengers.child) || 0;
      infants = parseInt(req.body.passengers.baby) || 0;
    }
    // Format 3: { passengers: { adults: 1, children: 0, infants: 0 } }
    else if (req.body.passengers?.adults !== undefined) {
      adults = parseInt(req.body.passengers.adults) || 1;
      children = parseInt(req.body.passengers.children) || 0;
      infants = parseInt(req.body.passengers.infants) || 0;
    }

    // Extraire les options
    const options = req.body.options || {};
    
    const requestData = {
      flights: req.body.flights,
      adults: adults,
      children: children,
      infants: infants,
      travelClass: req.body.travelClass || 'ECONOMY',
      nonStop: options.direct === true || req.body.nonStop === true || req.body.nonStop === 'true',
      refundable: options.refundable === true || req.body.refundable === true || req.body.refundable === 'true',
      baggage: options.baggage === true || req.body.baggage === true || req.body.baggage === 'true',
      currency: req.body.currency || 'DZD'
    };

    console.log("Données transformées:", requestData);

    if (!requestData.flights || !Array.isArray(requestData.flights) || requestData.flights.length < 2) {
      return res.status(400).json({
        success: false,
        message: 'Minimum 2 segments requis'
      });
    }

    const result = await amadeusService.searchMultiDestination(requestData);

    res.json({
      success: true,
      data: result
    });

  } catch (error) {
    console.error(' Erreur searchMultiDestination:', error);
    res.status(error.status || 500).json({
      success: false,
      message: error.message || 'Erreur recherche multi-destination'
    });
  }
},

    // Récupérer les aéroports
    getAirports: async (req, res) => {
        try {
            const { search, popular = 'false' } = req.query;
            
            const airports = popular === 'true' 
                ? await airportService.getPopularAirports()
                : search?.length >= 2 
                    ? await airportService.searchAirports(search)
                    : await airportService.getPopularAirports();
            
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

    // Vérifier disponibilité d'un vol
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
            console.error('Erreur checkAvailability:', error);
            res.status(500).json({
                success: false,
                message: error.message
            });
        }
    }
};

module.exports = flightController;