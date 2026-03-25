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
    // ============== TOKEN =============================
    async getAccessToken() {
        if (this.accessToken && this.tokenExpiry && Date.now() < this.tokenExpiry) {
            return this.accessToken;
        }

        try {
            console.log('Obtention du token Amadeus...');
            
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
    // ===================  RECHERCHE DE VOLS ========================
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

            const totalPassengers = adults + children + infants;
            console.log(` Recherche pour ${totalPassengers} passagers`);

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

            console.log(' URL Amadeus:', url);

            const response = await axios.get(url, {
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Accept': 'application/json'
                }
            });

            console.log(` ${response.data.data?.length || 0} offres trouvées`);

            let flights = this.transformFlightData(response.data);
            
            // Filtrage par places dispo
            console.log(` Filtrage des vols par places disponibles`);
            const avant = flights.length;
            flights = flights.filter(flight => {
                const places = flight.seatsAvailable || 0;
                return places >= totalPassengers; 
            });
            const apres = flights.length;
           // console.log(` Filtrage places: ${avant} → ${apres} vols (${avant - apres} vols supprimés - pas assez de places pour ${totalPassengers} passagers)`);
            // Autres filtrages
            if (baggage) {
                flights = flights.filter(f => f.baggage.quantity > 0);
            }
            if (refundable) {
                flights = flights.filter(f => f.refundable.isRefundable);
            }
            if (nonStop) {
                flights = flights.filter(f => f.isDirect);
        

            return {
                success: true,
                count: flights.length,
                tripType: returnDate ? 'ALLER_RETOUR' : 'ALLER_SIMPLE',
                searchParams: { ...params, totalPassengers },
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
// ==================    RECHERCHE MULTI-DESTINATION   =========================
async searchMultiDestination(requestData) {
    try {
        console.log(' Recherche multi-destination');
        console.log(' Données reçues:', JSON.stringify(requestData, null, 2));
        
        // Extraire les données de l'objet requestData
        const { flights, adults, children, infants, travelClass, nonStop, refundable, baggage, currency } = requestData;//flights : Tableau des segments de vol (ex: CDG→JFK, puis JFK→LHR)
        const totalPassengers = (adults || 1) + (children || 0) + (infants || 0);
        console.log(` Total passagers: ${totalPassengers}`);

        // Créer l'objet passengers pour la compatibilité
        const passengers = {
            adults: adults || 1,
            children: children || 0,
            infants: infants || 0
        };
        // Créer l'objet filters
        const filters = {
            nonStop: nonStop || false,
            refundable: refundable || false,
            baggage: baggage || false,
            currency: currency || 'DZD'
        };
        // Lancer recherches en même temps
        const searchPromises = flights.map(async (flight, index) => {
            console.log(` Segment ${index+1}: ${flight.from || flight.origin} → ${flight.to || flight.destination} le ${flight.date || flight.departureDate}`);
            
            const result = await this.searchFlights({
                origin: flight.from || flight.origin,
                destination: flight.to || flight.destination,
                departureDate: flight.date || flight.departureDate,
                adults: passengers.adults,
                children: passengers.children,
                infants: passengers.infants,
                travelClass: travelClass,
                nonStop: filters.nonStop,
                refundable: filters.refundable,
                baggage: filters.baggage,
                currency: filters.currency
            });
            
            return {
                segment: index + 1,
                origin: flight.from || flight.origin,
                destination: flight.to || flight.destination,
                departureDate: flight.date || flight.departureDate,
                data: result
            };
        });
        const results = await Promise.all(searchPromises);//exécution parallèle des recherches pour chaque segment
        console.log(` ${results.length} segments recherchés`);

        // Filtrer nombre de places
        results.forEach(segment => {
            if (segment.data?.flights) {
                const avant = segment.data.flights.length;
                segment.data.flights = segment.data.flights.filter(
                    flight => (flight.seatsAvailable || 0) >= totalPassengers
                );
                const apres = segment.data.flights.length;
                if (avant !== apres) {
                    console.log(`Segment ${segment.segment}: ${avant} → ${apres} vols filtrés`);
                }
            }
        });
        // Vérifier disponibilité des vols pour chaque segment
        const hasFlights = results.every(segment => 
            segment.data?.flights && segment.data.flights.length > 0
        );//every verifier segment par segment ida >0

        if (!hasFlights) {
            console.log(' Aucun vol disponible avec assez de places');
            return {
                success: true,
                tripType: "MULTI_DESTINATION",
                searchParams: {
                    flights,
                    passengers,
                    totalPassengers,
                    travelClass,
                    filters
                },
                segments: results,
                combinations: [],
                totalCombinations: 0
            };
        }
        // Générer les combinaisons avec le nombre de passagers
        const combinations = this.generateCombinations(results, totalPassengers);
        console.log(` ${combinations.length} combinaisons valides générées`);

        return {
            success: true,
            tripType: "MULTI_DESTINATION",
            searchParams: {
                flights,
                passengers,
                totalPassengers,
                travelClass,
                filters
            },
            segments: results,
            combinations: combinations,
            totalCombinations: combinations.length
        };

    } catch (error) {
        console.error(' Erreur multi-destination:', error);
        throw error;
    }
}    // ================  GÉNÉRER LES COMBINAISONS  ===========================
    generateCombinations(segments, totalPassengers) {
        try {
            console.log(' Génération des combinaisons...');
            
            if (!segments || segments.length === 0) {
                console.log(' Aucun segment à combiner');
                return [];
            }
            // Filtrer chaque segment par nombre de places
            const filteredSegments = segments.map(segment => {
                const filteredFlights = segment.data.flights.filter(flight => 
                    (flight.seatsAvailable || 0) >= totalPassengers
                );
                
                return {
                    ...segment,
                    data: {
                        ...segment.data,
                        flights: filteredFlights
                    }
                };
            });
            // Vérifier qu'il reste des vols
            for (let i = 0; i < filteredSegments.length; i++) {
                if (filteredSegments[i].data.flights.length === 0) {
                    console.log(` Segment ${i+1} n'a plus de vols après filtrage`);
                    return [];
                }
            }
            // Démarrer avec le premier segment
            let combinations = filteredSegments[0].data.flights.map(flight => ({
                flights: [flight],
                totalPrice: flight.price.total,
                segments: [flight]
            }));
            console.log(`📦 Départ avec ${combinations.length} combinaisons`);

            // Ajouter les segments suivants
            for (let i = 1; i < filteredSegments.length; i++) {
                const newCombinations = [];
                const currentFlights = filteredSegments[i].data.flights;

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
                console.log(`Après segment ${i+1}: ${combinations.length} combinaisons`);
            }
            return combinations;

        } catch (error) {
            console.error(' Erreur generateCombinations:', error);
            return [];
        }
    }
    // TRANSFORMER LES DONNÉES
    // ===========================================
    transformFlightData(amadeusData) {
        try {
            if (!amadeusData.data || !Array.isArray(amadeusData.data)) {
                return [];
            }

            return amadeusData.data.map(offer => {
                try {
                    const itinerary = offer.itineraries[0];
                    const segment = itinerary.segments[0];
                    
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
                    
                    const isDirect = itinerary.segments.length === 1;
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
    // FORMATER LA DURÉE
    // ===========================================
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
    // VÉRIFIER Disponibilite pour Reservation
    // ===========================================
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