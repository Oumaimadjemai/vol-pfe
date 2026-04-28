// const amadeusService = require('../services/amadeusService');

// const flightController = {

//     // 1. RECHERCHE ALLER SIMPLE / ALLER-RETOUR
//     // ===========================================
//     searchFlights: async (req, res) => {
//         try {
//             const {
//                 origin, destination, departureDate, returnDate,
//                 adults = 1, children = 0, infants = 0,
//                 travelClass = 'ECONOMY',
//                 nonStop = 'false', refundable = 'false', baggage = 'false',
//                 currency = 'DZD'
//             } = req.query;

//             if (!origin || !destination || !departureDate) {
//                 return res.status(400).json({
//                     success: false,
//                     message: 'Paramètres requis: origin, destination, departureDate'
//                 });
//             }

//             console.log(' Recherche:', { origin, destination, departureDate, returnDate, adults, children, infants, travelClass, nonStop, refundable, baggage });

//             const result = await amadeusService.searchFlights({
//                 origin: origin.toUpperCase(),
//                 destination: destination.toUpperCase(),
//                 departureDate,
//                 returnDate: returnDate || null,
//                 adults: parseInt(adults),
//                 children: parseInt(children),
//                 infants: parseInt(infants),
//                 travelClass: travelClass.toUpperCase(),
//                 nonStop: nonStop === 'true',
//                 refundable: refundable === 'true',
//                 baggage: baggage === 'true',
//                 currency
//             });

//             res.json({
//                 success: true,
//                 data: result
//             });

//         } catch (error) {
//             console.error(' Erreur searchFlights:', error);
//             res.status(error.status || 500).json({
//                 success: false,
//                 message: error.message || 'Erreur lors de la recherche'
//             });
//         }
//     },

//     // ===========================================
//     // 2. RECHERCHE MULTI-DESTINATION
// searchMultiDestination: async (req, res) => {
//     try {
//         const {
//             flights, adults = 1, children = 0, infants = 0,
//             travelClass = 'ECONOMY',
//             nonStop = 'false', refundable = 'false', baggage = 'false',
//             currency = 'DZD'
//         } = req.body;

//         console.log(' Body reçu:', req.body);

//         if (!flights || !Array.isArray(flights) || flights.length < 2) {
//             return res.status(400).json({
//                 success: false,
//                 message: 'Minimum 2 segments requis pour multi-destination'
//             });
//         }

//         // Formater les vols
//         const formattedFlights = flights.map((flight, index) => {
//             const origin = flight.origin || flight.from;
//             const destination = flight.destination || flight.to;
//             const departureDate = flight.date || flight.departureDate;

//             if (!origin || !destination || !departureDate) {
//                 throw new Error(`Vol ${index + 1}: champs manquants`);
//             }

//             return {
//                 origin: origin.toUpperCase(),
//                 destination: destination.toUpperCase(),
//                 departureDate
//             };
//         });

//         console.log(' Vols formatés:', formattedFlights);

//         //  APPEL AU SERVICE
//         const results = await amadeusService.searchMultiDestination(
//             formattedFlights,
//             { adults: parseInt(adults), children: parseInt(children), infants: parseInt(infants) },
//             travelClass.toUpperCase(),
//             {
//                 nonStop: nonStop === 'true',
//                 refundable: refundable === 'true',
//                 baggage: baggage === 'true',
//                 currency
//             }
//         );

//         //  GÉNÉRER LES COMBINAISONS
//         let combinations = [];
//         if (results && results.segments && results.segments.length > 0) {
//             combinations = await amadeusService.generateCombinations(results.segments);
//             console.log(` ${combinations.length} combinaisons générées`);
//         } else {
//             console.log(' Pas de segments à combiner');
//         }

//         // Retourner les résultats
//         res.json({
//             success: true,
//             data: {
//                 tripType: "MULTI_DESTINATION",
//                 searchParams: {
//                     flights: formattedFlights,
//                     passengers: { adults, children, infants },
//                     travelClass: travelClass.toUpperCase(),
//                     filters: { nonStop, refundable, baggage }
//                 },
//                 segments: results.segments || [],
//                 combinations: combinations || [],
//                 totalCombinations: combinations.length || 0
//             }
//         });

//     } catch (error) {
//         console.error(' Erreur searchMultiDestination:', error);
//         res.status(500).json({
//             success: false,
//             message: error.message || 'Erreur recherche multi-destination'
//         });
//     }
// },

// //  RÉCUPÉRER LES AÉROPORTS
// // ===========================================
// getAirports: async (req, res) => {
//     try {
//         const { search, popular = 'false' } = req.query;

//         const airportService = require('../services/airportService');

//         let airports;
//         if (popular === 'true') {
//             // Aéroports populaires
//             airports = await airportService.getPopularAirports();
//         } else if (search && search.length >= 2) {
//             // Recherche par mot-clé (minimum 2 caractères)
//             airports = await airportService.searchAirports(search, 20);
//         } else {
//             // Par défaut, retourner les populaires
//             airports = await airportService.getPopularAirports();
//         }

//         res.json({
//             success: true,
//             count: airports.length,
//             data: airports
//         });

//     } catch (error) {
//         console.error(' Erreur getAirports:', error);
//         res.status(500).json({
//             success: false,
//             message: error.message
//         });
//     }
// },

//     //  VÉRIFIER DISPONIBILITÉ
//     // ===========================================
//     checkAvailability: async (req, res) => {
//         try {
//             const { flightId } = req.params;

//             if (!flightId) {
//                 return res.status(400).json({
//                     success: false,
//                     message: 'ID du vol requis'
//                 });
//             }

//             const availability = await amadeusService.checkAvailability(flightId);

//             res.json({
//                 success: true,
//                 data: availability
//             });
//         } catch (error) {
//             res.status(500).json({
//                 success: false,
//                 message: error.message
//             });
//         }
//     }
// };

// module.exports = flightController;

const skyscannerService = require("../services/skyscannerService");
const { sendEvent } = require("../../KafkaProducer");
const flightController = {
  // ===========================================
  // 1. SEARCH FLIGHTS (ONE WAY / ROUND TRIP)
  // ===========================================
  searchFlights: async (req, res) => {
    try {
      const {
        origin,
        destination,
        departureDate,
        returnDate,
        adults = 1,
        children = 0,
        infants = 0,
        travelClass = "ECONOMY",
        currency = "DZD",
      } = req.query;

      if (!origin || !destination || !departureDate) {
        return res.status(400).json({
          success: false,
          message: "Paramètres requis: origin, destination, departureDate",
        });
      }

      console.log("🔍 Recherche Skyscanner:", {
        origin,
        destination,
        departureDate,
        returnDate,
      });

      const result = await skyscannerService.searchFlights({
        origin: origin.toUpperCase(),
        destination: destination.toUpperCase(),
        departureDate,
        returnDate: returnDate || null,
        adults: parseInt(adults),
        children: parseInt(children),
        infants: parseInt(infants),
        travelClass: travelClass.toUpperCase(),
        currency,
      });
      sendEvent("flight_search", {
  eventType: "FLIGHT_SEARCHED",
  search: {
    origin,
    destination,
    departureDate,
    returnDate,
  },
  resultSummary: {
    totalFlights: result?.data?.length || 0,
  },
  sampleFlights: result?.data?.slice(0, 3) || [], // optional preview
  timestamp: new Date().toISOString(),
});

      res.json({
        success: true,
        data: result,
      });
    } catch (error) {
      console.error("❌ Erreur searchFlights:", error);
      res.status(error.status || 500).json({
        success: false,
        message: error.message || "Erreur lors de la recherche",
      });
    }
  },

  // ===========================================
  // 2. SEARCH MULTI-DESTINATION
  // ===========================================
  searchMultiDestination: async (req, res) => {
    try {
      const {
        flights,
        adults = 1,
        children = 0,
        infants = 0,
        travelClass = "ECONOMY",
        currency = "DZD",
      } = req.body;

      if (!flights || !Array.isArray(flights) || flights.length < 2) {
        return res.status(400).json({
          success: false,
          message: "Minimum 2 segments requis pour multi-destination",
        });
      }

      // Format flights
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
          departureDate,
        };
      });

      console.log("📋 Vols formatés:", formattedFlights);

      // Call service
      const results = await skyscannerService.searchMultiDestination(
        formattedFlights,
        {
          adults: parseInt(adults),
          children: parseInt(children),
          infants: parseInt(infants),
        },
        travelClass.toUpperCase(),
        { currency },
      );
      sendEvent("flight-events", {
        eventType: "MULTI_DESTINATION_SEARCHED",
        flights: formattedFlights,
        passengers: { adults, children, infants },
        timestamp: new Date().toISOString(),
      });

      // Generate combinations
      let combinations = [];
      if (results && results.segments && results.segments.length > 0) {
        combinations = await skyscannerService.generateCombinations(
          results.segments,
        );
        console.log(`✅ ${combinations.length} combinaisons générées`);
      }

      res.json({
        success: true,
        data: {
          tripType: "MULTI_DESTINATION",
          searchParams: {
            flights: formattedFlights,
            passengers: { adults, children, infants },
            travelClass: travelClass.toUpperCase(),
          },
          segments: results.segments || [],
          combinations: combinations || [],
          totalCombinations: combinations.length || 0,
        },
      });
    } catch (error) {
      console.error("❌ Erreur searchMultiDestination:", error);
      res.status(500).json({
        success: false,
        message: error.message || "Erreur recherche multi-destination",
      });
    }
  },

  // ===========================================
  // 3. GET AIRPORTS
  // ===========================================
  getAirports: async (req, res) => {
    try {
      const { search, popular = "false" } = req.query;

      const airportService = require("../services/airportService");

      let airports;
      if (popular === "true") {
        airports = await airportService.getPopularAirports();
      } else if (search && search.length >= 2) {
        airports = await airportService.searchAirports(search, 20);
      } else {
        airports = await airportService.getPopularAirports();
      }

      res.json({
        success: true,
        count: airports.length,
        data: airports,
      });
    } catch (error) {
      console.error("❌ Erreur getAirports:", error);
      res.status(500).json({
        success: false,
        message: error.message,
      });
    }
  },

  // ===========================================
  // 4. CHECK AVAILABILITY
  // ===========================================
  checkAvailability: async (req, res) => {
    try {
      const { flightId } = req.params;

      if (!flightId) {
        return res.status(400).json({
          success: false,
          message: "ID du vol requis",
        });
      }

      const availability = await skyscannerService.checkAvailability(flightId);

      res.json({
        success: true,
        data: availability,
      });
    } catch (error) {
      res.status(500).json({
        success: false,
        message: error.message,
      });
    }
  },
};

module.exports = flightController;


// service-vols/controllers/flightController.js
// const duffelService = require('../services/duffelService');

// const flightController = {

//     searchFlights: async (req, res) => {
//         try {
//             const {
//                 origin, destination, departureDate, returnDate,
//                 adults = 1, children = 0, infants = 0,
//                 cabinClass = 'economy'
//             } = req.query;

//             if (!origin || !destination || !departureDate) {
//                 return res.status(400).json({
//                     success: false,
//                     message: 'Paramètres requis: origin, destination, departureDate'
//                 });
//             }

//             console.log('🔍 Recherche Duffel:', { origin, destination, departureDate });

//             const totalPassengers = parseInt(adults) + parseInt(children) + parseInt(infants);
            
//             const result = await duffelService.searchFlights({
//                 origin: origin.toUpperCase(),
//                 destination: destination.toUpperCase(),
//                 departureDate,
//                 returnDate: returnDate || null,
//                 adults: totalPassengers || 1,
//                 cabinClass: cabinClass.toLowerCase()
//             });

//             res.json({
//                 success: true,
//                 source: 'duffel',
//                 data: result
//             });

//         } catch (error) {
//             console.error('❌ Erreur recherche:', error);
//             res.status(error.status || 500).json({
//                 success: false,
//                 message: error.message || 'Erreur lors de la recherche des vols',
//                 details: error.details
//             });
//         }
//     },

//     testDuffelConnection: async (req, res) => {
//         try {
//             const result = await duffelService.searchFlights({
//                 origin: 'JFK',
//                 destination: 'EWR',
//                 departureDate: '2026-06-15',
//                 adults: 1
//             });
            
//             res.json({
//                 success: true,
//                 message: 'Duffel API is working!',
//                 apiKeyConfigured: true,
//                 apiVersion: 'v2',
//                 testResult: result
//             });
//         } catch (error) {
//             res.status(500).json({
//                 success: false,
//                 message: 'Duffel API connection failed',
//                 error: error.message,
//                 apiKeyConfigured: !!process.env.DUFFEL_API_KEY
//             });
//         }
//     }
// };

// module.exports = flightController;