const axios = require('axios');
const config = require('../config/config');

class AmadeusService {
    constructor() {
        this.baseURL = config.amadeus.environment === 'production' 
            ? 'https://api.amadeus.com'
            : 'https://test.api.amadeus.com';
        this.accessToken = null;
        this.tokenExpiry = null;
    }

   
    // TOKEN
   
    async getAccessToken() {
        if (this.accessToken && this.tokenExpiry && Date.now() < this.tokenExpiry) {
            return this.accessToken;
        }

        try {
            console.log(' Obtention du token Amadeus...');
            
            const response = await axios.post(
                `${this.baseURL}/v1/security/oauth2/token`,
                `grant_type=client_credentials&client_id=${config.amadeus.apiKey}&client_secret=${config.amadeus.apiSecret}`,
                {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
                }
            );

            this.accessToken = response.data.access_token;
            this.tokenExpiry = Date.now() + (response.data.expires_in * 1000) - 60000;
            console.log(' Token Amadeus obtenu');
            return this.accessToken;
        } catch (error) {
            console.error(' Erreur token Amadeus:', error.response?.data || error.message);
            throw new Error('Impossible d\'obtenir le token Amadeus');
        }
    }


    // RECHERCHE DE VOLS
   
    async searchFlights(params) {
        try {
            const token = await this.getAccessToken();
            
            const { 
                origin, destination, departureDate, returnDate,
                adults = 1, children = 0, infants = 0,
                travelClass = 'ECONOMY', nonStop = false,
                refundable = false, baggage = false,
                currency = 'DZD', maxResults =  10
            } = params;

            let url = `${this.baseURL}/v2/shopping/flight-offers`;
            url += `?originLocationCode=${origin}`;
            url += `&destinationLocationCode=${destination}`;
            url += `&departureDate=${departureDate}`;
            url += `&adults=${adults}`;
            if (children > 0) url += `&children=${children}`;
            if (infants > 0) url += `&infants=${infants}`;
            if (returnDate) url += `&returnDate=${returnDate}`;
            if (travelClass) url += `&travelClass=${travelClass}`;
            if (nonStop) url += `&nonStop=true`;
            url += `&currencyCode=${currency}`;
            url += `&max=${maxResults}`;

            console.log('📡 URL Amadeus:', url);

            const response = await axios.get(url, {
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Accept': 'application/json'
                }
            });

            console.log(` ${response.data.data?.length || 0} offres trouvées`);

            let flights = this.transformFlightData(response.data);

            // Filtrage
            if (baggage) {
                flights = flights.filter(f => f.baggage.quantity > 0);
            }
            if (refundable) {
                flights = flights.filter(f => f.refundable.isRefundable);
            }
            if (nonStop) {
                flights = flights.filter(f => f.isDirect);
            }

            return {
                success: true,
                count: flights.length,
                tripType: returnDate ? 'ALLER_RETOUR' : 'ALLER_SIMPLE',
                searchParams: params,
                flights: flights
            };

        } catch (error) {
            console.error(' Erreur recherche:', error.response?.data || error.message);
            throw {
                message: 'Erreur lors de la recherche des vols',
                details: error.response?.data || error.message,
                status: error.response?.status || 500
            };
        }
    }

   
    // 3. GÉNÉRER LES COMBINAISONS 
  
generateCombinations(segments) {
    try {
        console.log(' Génération des combinaisons...');
        console.log(' Segments reçus:', JSON.stringify(segments, null, 2).substring(0, 500) + '...');
        
        if (!segments || segments.length === 0) {
            console.log(' Aucun segment à combiner');
            return [];
        }

        // Vérifier la structure
        for (let i = 0; i < segments.length; i++) {
            const segment = segments[i];
            console.log(` Segment ${i+1}:`, {
                hasData: !!segment.data,
                hasFlights: !!(segment.data && segment.data.flights),
                flightCount: segment.data?.flights?.length || 0
            });
            
            if (!segment.data || !segment.data.flights || segment.data.flights.length === 0) {
                console.log(` Segment ${i+1} n'a pas de vols`);
                return [];
            }
        }

        // Démarrer avec le premier segment
        let combinations = segments[0].data.flights.map(flight => ({
            flights: [flight],
            totalPrice: flight.price.total,
            segments: [flight]
        }));

        console.log(` Départ avec ${combinations.length} combinaisons`);

        // Pour chaque segment suivant
        for (let i = 1; i < segments.length; i++) {
            const newCombinations = [];
            const currentFlights = segments[i].data.flights;

            for (let j = 0; j < combinations.length; j++) {
                const combo = combinations[j];
                for (let k = 0; k < currentFlights.length; k++) {
                    const flight = currentFlights[k];
                    newCombinations.push({
                        flights: [...combo.flights, flight],
                        totalPrice: combo.totalPrice + flight.price.total,
                        segments: [...combo.segments, flight]
                    });
                }
            }
            combinations = newCombinations;
            console.log(` Après segment ${i+1}: ${combinations.length} combinaisons`);
        }

        return combinations;

    } catch (error) {
        console.error(' Erreur generateCombinations:', error);
        return [];
    }
}

   
    //  RECHERCHE MULTI-DESTINATION 
// ===========================================

async searchMultiDestination(flights, passengers, travelClass, filters = {}) {
    try {
        console.log('🔍 Recherche multi-destination en parallèle...');
        
        // Lancer toutes les recherches en même temps
        const searchPromises = flights.map(async (flight, index) => {
            console.log(` Segment ${index+1}: ${flight.origin} → ${flight.destination} le ${flight.departureDate}`);
            
            const result = await this.searchFlights({
                origin: flight.origin,
                destination: flight.destination,
                departureDate: flight.departureDate,
                adults: passengers.adults,
                children: passengers.children || 0,
                infants: passengers.infants || 0,
                travelClass: travelClass,
                nonStop: filters.nonStop || false,
                refundable: filters.refundable || false,
                baggage: filters.baggage || false,
                currency: filters.currency || 'DZD'
            });
            
            return {
                segment: index + 1,
                origin: flight.origin,
                destination: flight.destination,
                departureDate: flight.departureDate,
                data: result
            };
        });
        
        // Attendre que TOUTES les recherches  terminées
        const results = await Promise.all(searchPromises);
        
        console.log(` ${results.length} segments recherchés en parallèle`);
        
        return {
            success: true,
            segments: results
        };
        
    } catch (error) {
        console.error(' Erreur multi-destination:', error);
        throw error;
    }
}

   
    //  TRANSFORMER LES DONNÉES
   
    transformFlightData(amadeusData) {
        try {
            if (!amadeusData.data || !Array.isArray(amadeusData.data)) {
                return [];
            }

            return amadeusData.data.map(offer => {
                try {
                    const itinerary = offer.itineraries[0];
                    const segment = itinerary.segments[0];
                    
                    // Bagages
                    let baggageQuantity = 0;
                    let baggageInfo = "Non inclus";
                    
                    if (offer.travelerPricings && offer.travelerPricings[0]) {
                        const traveler = offer.travelerPricings[0];
                        const includedBags = traveler.fareDetailsBySegment?.[0]?.includedCheckedBags;
                        if (includedBags) {
                            baggageQuantity = includedBags.quantity || 0;
                            baggageInfo = `${baggageQuantity} bagage(s)`;
                            if (includedBags.weight) {
                                baggageInfo += ` (${includedBags.weight} ${includedBags.weightUnit || 'kg'})`;
                            }
                        }
                    }
                    
                    // Remboursement
                    let isRefundable = false;
                    const fareBasis = offer.travelerPricings?.[0]?.fareDetailsBySegment?.[0]?.fareBasis || "";
                    const cabin = offer.travelerPricings?.[0]?.fareDetailsBySegment?.[0]?.cabin || "";
                    
                    isRefundable = fareBasis.includes("FLEX") || 
                                  fareBasis.includes("FULL") || 
                                  fareBasis.includes("BUS") || 
                                  fareBasis.includes("PRM") ||
                                  fareBasis.includes("REF") ||
                                  cabin.includes("BUSINESS") ||
                                  cabin.includes("FIRST");
                    
                    // Vol direct
                    const isDirect = itinerary.segments.length === 1;
                    
                    // Prix
                    const totalPrice = parseFloat(offer.price.total);
                    const pricePerPassenger = totalPrice / (offer.travelerPricings?.length || 1);
                    
                    return {
                        id: offer.id,
                        airline: segment.carrierCode,
                        flightNumber: segment.number,
                        price: {
                            total: totalPrice,
                            perPassenger: pricePerPassenger,
                            currency: offer.price.currency
                        },
                        departure: {
                            airport: segment.departure.iataCode,
                            terminal: segment.departure.terminal,
                            time: segment.departure.at
                        },
                        arrival: {
                            airport: itinerary.segments[itinerary.segments.length - 1].arrival.iataCode,
                            terminal: itinerary.segments[itinerary.segments.length - 1].arrival.terminal,
                            time: itinerary.segments[itinerary.segments.length - 1].arrival.at
                        },
                        duration: this.formatDuration(itinerary.duration),
                        durationISO: itinerary.duration,
                        seatsAvailable: offer.numberOfBookableSeats || 0,
                        stops: itinerary.segments.length - 1,
                        isDirect: isDirect,
                        segments: itinerary.segments.map(s => ({
                            airline: s.carrierCode,
                            flightNumber: s.number,
                            departure: {
                                airport: s.departure.iataCode,
                                time: s.departure.at
                            },
                            arrival: {
                                airport: s.arrival.iataCode,
                                time: s.arrival.at
                            },
                            duration: s.duration,
                            aircraft: s.aircraft?.code
                        })),
                        baggage: { 
                            included: baggageInfo, 
                            quantity: baggageQuantity 
                        },
                        refundable: { 
                            isRefundable: isRefundable, 
                            policy: isRefundable ? "Remboursable" : "Non remboursable" 
                        },
                        lastTicketingDate: offer.lastTicketingDate,
                        source: offer.source
                    };
                } catch (e) {
                    return null;
                }
            }).filter(f => f !== null);

        } catch (error) {
            console.error(' Erreur transformation:', error);
            return [];
        }
    }

   
    //  FORMATER LA DURÉE
   
    formatDuration(duration) {
        if (!duration) return '';
        const matches = duration.match(/PT(?:(\d+)H)?(?:(\d+)M)?/);
        if (!matches) return duration;
        const hours = matches[1] ? parseInt(matches[1]) : 0;
        const minutes = matches[2] ? parseInt(matches[2]) : 0;
        
        if (hours > 0 && minutes > 0) return `${hours}h ${minutes}min`;
        if (hours > 0) return `${hours}h`;
        if (minutes > 0) return `${minutes}min`;
        return duration;
    }

   
    //  VÉRIFIER DISPONIBILITÉ
   
    async checkAvailability(flightId) {
        try {
            const token = await this.getAccessToken();
            const url = `${this.baseURL}/v1/shopping/flight-offers/${flightId}`;
            
            const response = await axios.get(url, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            const flightData = response.data;
            
            return {
                flightId: flightId,
                available: flightData.numberOfBookableSeats > 0,
                seatsLeft: flightData.numberOfBookableSeats || 0,
                price: flightData.price?.total || null,
                lastTicketingDate: flightData.lastTicketingDate
            };
            
        } catch (error) {
            return {
                flightId: flightId,
                available: true,
                seatsLeft: 5,
                note: "Données simulées"
            };
        }
    }
}

module.exports = new AmadeusService();