// services/sabreService.js
const axios = require('axios');
const config = require('../config/config');

class SabreService {
    constructor() {
        // Environnement de test (certification) Sabre
        this.baseURL = process.env.SABRE_ENVIRONMENT === 'production' 
            ? 'https://api.platform.sabre.com'
            : 'https://api.platform.sabre.com'; // Sabre utilise la même URL avec paramètres différents
        
        this.accessToken = null;
        this.tokenExpiry = null;
        
        // Identifiants Sabre (à mettre dans .env)
        this.userId = process.env.SABRE_USER_ID || 'V1:kgb7as5w0pzi9tis:DEVCENTER:EXT';
        this.password = process.env.SABRE_PASSWORD;
        this.pcc = process.env.SABRE_PCC || 'EX1';
        this.domain = process.env.SABRE_DOMAIN || 'DEVCNTER';
    }

    // ============== TOKEN SABRE =============================
    async getAccessToken() {
        if (this.accessToken && this.tokenExpiry && Date.now() < this.tokenExpiry) {
            return this.accessToken;
        }

        try {
            console.log('🔄 Obtention du token Sabre (Certification)...');
            
            // Encoder UserID:Password en Base64
            const credentials = Buffer.from(`${this.userId}:${this.password}`).toString('base64');
            
            // Paramètres de la requête
            const params = new URLSearchParams();
            params.append('grant_type', 'client_credentials');
            
            const response = await axios.post(
                `${this.baseURL}/v2/auth/token`,
                params.toString(),
                {
                    headers: {
                        'Authorization': `Basic ${credentials}`,
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Originating-IP': '127.0.0.1',
                        'PCC': this.pcc,
                        'Domain': this.domain
                    }
                }
            );

            this.accessToken = response.data.access_token;
            // Token Sabre valable 7 jours (604800 secondes)
            this.tokenExpiry = Date.now() + (response.data.expires_in * 1000) - 60000;
            console.log('✅ Token Sabre obtenu');
            return this.accessToken;
            
        } catch (error) {
            console.error('❌ Erreur token Sabre:', error.response?.data || error.message);
            throw new Error('Impossible d\'obtenir le token Sabre');
        }
    }

    // =================== RECHERCHE DE VOLS ========================
    async searchFlights(params) {
        try {
            const token = await this.getAccessToken();
            
            const { 
                origin, destination, departureDate, returnDate,
                adults = 1, children = 0, infants = 0,
                travelClass = 'ECONOMY', nonStop = false,
                refundable = false, baggage = false,
                currency = 'DZD', maxResults = 10
            } = params;

            const totalPassengers = adults + children + infants;
            console.log(`🔍 Recherche Sabre pour ${totalPassengers} passagers`);
            console.log(`📍 ${origin} → ${destination} le ${departureDate}`);

            // Construction de l'URL pour l'API Sabre
            let url = `${this.baseURL}/v1/shop/flights`;
            const queryParams = {
                origin: origin,
                destination: destination,
                departuredate: departureDate,
                passengers: adults,
                limit: maxResults,
                sort: 'price'
            };
            
            if (returnDate) {
                queryParams.returndate = returnDate;
            }
            
            if (travelClass) {
                let sabreClass = 'Y'; // ECONOMY par défaut
                switch(travelClass) {
                    case 'ECONOMY': sabreClass = 'Y'; break;
                    case 'PREMIUM_ECONOMY': sabreClass = 'S'; break;
                    case 'BUSINESS': sabreClass = 'C'; break;
                    case 'FIRST': sabreClass = 'F'; break;
                }
                queryParams.cabinclass = sabreClass;
            }

            const response = await axios.get(url, {
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Accept': 'application/json',
                    'PCC': this.pcc,
                    'Domain': this.domain
                },
                params: queryParams
            });

            console.log(`📊 ${response.data?.data?.length || 0} offres trouvées Sabre`);

            // Transformation des données Sabre vers le format attendu par votre frontend
            let flights = this.transformFlightData(response.data);
            
            // Filtrage par places disponibles
            const avant = flights.length;
            flights = flights.filter(flight => {
                const places = flight.seatsAvailable || 0;
                return places >= totalPassengers; 
            });
            const apres = flights.length;
            
            // Autres filtrages
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
                searchParams: { ...params, totalPassengers },
                flights: flights
            };

        } catch (error) {
            console.error('❌ Erreur recherche Sabre:', error.response?.data || error.message);
            
            // Si l'API Sabre ne répond pas, retourner des données mockées
            console.log('⚠️ Mode dégradé: retour de données mockées');
            return this.getMockFlights(params);
        }
    }

    // ================== RECHERCHE MULTI-DESTINATION =========================
    async searchMultiDestination(requestData) {
        try {
            console.log('🔍 Recherche multi-destination Sabre');
            
            const { flights, adults, children, infants, travelClass, nonStop, refundable, baggage, currency } = requestData;
            const totalPassengers = (adults || 1) + (children || 0) + (infants || 0);
            
            const passengers = {
                adults: adults || 1,
                children: children || 0,
                infants: infants || 0
            };
            
            const filters = {
                nonStop: nonStop || false,
                refundable: refundable || false,
                baggage: baggage || false,
                currency: currency || 'DZD'
            };
            
            // Lancer recherches en parallèle
            const searchPromises = flights.map(async (flight, index) => {
                console.log(`📌 Segment ${index+1}: ${flight.from || flight.origin} → ${flight.to || flight.destination}`);
                
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
            
            const results = await Promise.all(searchPromises);
            
            // Générer les combinaisons
            const combinations = this.generateCombinations(results, totalPassengers);
            
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
            console.error('❌ Erreur multi-destination Sabre:', error);
            throw error;
        }
    }

    // ================ GÉNÉRER LES COMBINAISONS ===========================
    generateCombinations(segments, totalPassengers) {
        try {
            if (!segments || segments.length === 0) return [];
            
            let combinations = segments[0].data.flights.map(flight => ({
                flights: [flight],
                totalPrice: flight.price.total,
                segments: [flight]
            }));
            
            for (let i = 1; i < segments.length; i++) {
                const newCombinations = [];
                const currentFlights = segments[i].data.flights;
                
                for (const combo of combinations) {
                    for (const flight of currentFlights) {
                        newCombinations.push({
                            flights: [...combo.flights, flight],
                            totalPrice: combo.totalPrice + flight.price.total,
                            segments: [...combo.segments, flight]
                        });
                    }
                }
                combinations = newCombinations;
            }
            
            // Trier par prix
            combinations.sort((a, b) => a.totalPrice - b.totalPrice);
            
            // Limiter à 100 combinaisons
            return combinations.slice(0, 100);
            
        } catch (error) {
            console.error('❌ Erreur generateCombinations:', error);
            return [];
        }
    }

    // ================ TRANSFORMER LES DONNÉES SABRE ===========================
    transformFlightData(sabreData) {
        try {
            if (!sabreData.data || !Array.isArray(sabreData.data)) {
                return this.getMockFlights({}).flights;
            }

            return sabreData.data.map(offer => {
                try {
                    const segment = offer.itineraries[0].segments[0];
                    const lastSegment = offer.itineraries[0].segments[offer.itineraries[0].segments.length - 1];
                    const isDirect = offer.itineraries[0].segments.length === 1;
                    
                    // Prix
                    const totalPrice = parseFloat(offer.price.total);
                    const pricePerPassenger = totalPrice / (offer.travelerPricings?.length || 1);
                    
                    // Bagages
                    let baggageQuantity = 0;
                    let baggageInfo = "Non inclus";
                    if (offer.travelerPricings && offer.travelerPricings[0]?.fareDetailsBySegment?.[0]?.includedCheckedBags) {
                        baggageQuantity = offer.travelerPricings[0].fareDetailsBySegment[0].includedCheckedBags.quantity || 0;
                        baggageInfo = `${baggageQuantity} bagage(s)`;
                    }
                    
                    // Remboursabilité
                    let isRefundable = false;
                    const fareBasis = offer.travelerPricings?.[0]?.fareDetailsBySegment?.[0]?.fareBasis || "";
                    isRefundable = fareBasis.includes("REF") || fareBasis.includes("FLEX");
                    
                    // Gestion des escales
                    let stopoverCities = [];
                    let stopoverDetails = [];
                    
                    if (!isDirect) {
                        for (let i = 0; i < offer.itineraries[0].segments.length - 1; i++) {
                            const currentSeg = offer.itineraries[0].segments[i];
                            stopoverCities.push(currentSeg.arrival.iataCode);
                            stopoverDetails.push({
                                airport: currentSeg.arrival.iataCode,
                                arrivalTime: currentSeg.arrival.at
                            });
                        }
                    }
                    
                    return {
                        id: offer.id || `SAB-${Date.now()}-${Math.random()}`,
                        airline: segment.carrierCode,
                        flightNumber: segment.number,
                        price: {
                            total: totalPrice,
                            perPassenger: pricePerPassenger,
                            currency: offer.price.currency || 'USD'
                        },
                        departure: {
                            airport: segment.departure.iataCode,
                            terminal: segment.departure.terminal,
                            time: segment.departure.at
                        },
                        arrival: {
                            airport: lastSegment.arrival.iataCode,
                            terminal: lastSegment.arrival.terminal,
                            time: lastSegment.arrival.at
                        },
                        duration: offer.itineraries[0].duration || 'PT0H',
                        durationISO: offer.itineraries[0].duration || 'PT0H',
                        seatsAvailable: offer.numberOfBookableSeats || 10,
                        stops: offer.itineraries[0].segments.length - 1,
                        isDirect: isDirect,
                        hasStopovers: !isDirect,
                        stopoverCount: offer.itineraries[0].segments.length - 1,
                        stopoverCities: stopoverCities,
                        stopoverAirports: stopoverCities,
                        stopoverDetails: stopoverDetails,
                        segments: offer.itineraries[0].segments.map(s => ({
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
                            duration: s.duration
                        })),
                        baggage: { 
                            included: baggageInfo, 
                            quantity: baggageQuantity 
                        },
                        refundable: { 
                            isRefundable: isRefundable, 
                            policy: isRefundable ? "Remboursable" : "Non remboursable" 
                        },
                        lastTicketingDate: offer.lastTicketingDate || new Date().toISOString(),
                        source: 'SABRE'
                    };
                } catch (e) {
                    console.error('Erreur transformation vol:', e);
                    return null;
                }
            }).filter(f => f !== null);
            
        } catch (error) {
            console.error('❌ Erreur transformation Sabre:', error);
            return [];
        }
    }

    // ================ DONNÉES MOCKÉES (Fallback) ===========================
    getMockFlights(params) {
        const { origin = 'CDG', destination = 'JFK', departureDate = '2025-05-15', adults = 1 } = params;
        
        const mockFlights = [
            {
                id: `MOCK-${Date.now()}-1`,
                airline: 'AF',
                flightNumber: '378',
                price: { total: 450, perPassenger: 450, currency: 'EUR' },
                departure: { airport: origin, time: `${departureDate}T08:00:00` },
                arrival: { airport: destination, time: `${departureDate}T11:30:00` },
                duration: 'PT3H30M',
                seatsAvailable: 25,
                stops: 0,
                isDirect: true,
                baggage: { included: "1 bagage(s)", quantity: 1 },
                refundable: { isRefundable: false, policy: "Non remboursable" },
                source: 'MOCK'
            },
            {
                id: `MOCK-${Date.now()}-2`,
                airline: 'BA',
                flightNumber: '189',
                price: { total: 520, perPassenger: 520, currency: 'EUR' },
                departure: { airport: origin, time: `${departureDate}T14:00:00` },
                arrival: { airport: destination, time: `${departureDate}T17:45:00` },
                duration: 'PT3H45M',
                seatsAvailable: 12,
                stops: 0,
                isDirect: true,
                baggage: { included: "2 bagage(s)", quantity: 2 },
                refundable: { isRefundable: true, policy: "Remboursable" },
                source: 'MOCK'
            }
        ];
        
        return {
            success: true,
            count: mockFlights.length,
            tripType: params.returnDate ? 'ALLER_RETOUR' : 'ALLER_SIMPLE',
            searchParams: params,
            flights: mockFlights
        };
    }

    // ================ VÉRIFIER DISPONIBILITÉ ===========================
    async checkAvailability(flightId) {
        try {
            const token = await this.getAccessToken();
            const url = `${this.baseURL}/v1/shop/flights/${flightId}`;
            
            const response = await axios.get(url, {
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'PCC': this.pcc,
                    'Domain': this.domain
                }
            });
            
            return {
                flightId: flightId,
                available: response.data?.numberOfBookableSeats > 0,
                seatsLeft: response.data?.numberOfBookableSeats || 0,
                price: response.data?.price?.total || null,
                lastTicketingDate: response.data?.lastTicketingDate
            };
            
        } catch (error) {
            // Fallback mocké
            return {
                flightId: flightId,
                available: true,
                seatsLeft: 15,
                note: "Données simulées (API Sabre non disponible)"
            };
        }
    }
}

module.exports = new SabreService();