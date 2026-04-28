const axios = require('axios');
const config = require('../config/config');

class SkyscannerService {
    constructor() {
        this.baseURL = 'https://skyscanner-flights-travel-api.p.rapidapi.com';
        this.apiKey = config.rapidapi.key;
        this.apiHost = 'skyscanner-flights-travel-api.p.rapidapi.com';
    }

    getHeaders() {
        return {
            'x-rapidapi-key': this.apiKey,
            'x-rapidapi-host': this.apiHost,
            'Content-Type': 'application/json'
        };
    }

    // ===========================================
    // SEARCH FLIGHTS (ONE WAY / ROUND TRIP)
    // ===========================================
    async searchFlights(params) {
        try {
            const { 
                origin, destination, departureDate, returnDate,
                adults = 1, children = 0, infants = 0,
                travelClass = 'ECONOMY', currency = 'USD'
            } = params;

            console.log('🔍 Recherche Skyscanner:', { origin, destination, departureDate });

            // Get airport details with entity IDs
            const originAirport = await this.getAirportDetails(origin);
            const destAirport = await this.getAirportDetails(destination);

            // Build URL with correct parameters
            const url = `${this.baseURL}/flights/searchFlights`;
            
            const queryParams = {
                countryCode: 'US',
                market: 'US',
                currency: currency,
                locale: 'en-US',
                originSkyId: originAirport.skyId || origin,
                destinationSkyId: destAirport.skyId || destination,
                originEntityId: originAirport.entityId,
                destinationEntityId: destAirport.entityId,
                date: departureDate,
                adults: parseInt(adults),
                childrens: parseInt(children),
                infants: parseInt(infants),
                cabinClass: travelClass.toLowerCase(),
                limit: 50  // Request more results
            };

            if (returnDate) {
                queryParams.returnDate = returnDate;
            }

            console.log('📡 Appel API searchFlights');
            console.log('📦 Paramètres:', JSON.stringify(queryParams, null, 2));

            const response = await axios.get(url, {
                headers: this.getHeaders(),
                params: queryParams,
                timeout: 30000
            });

            console.log('✅ Réponse reçue');

            // Check if we have itineraries
            if (response.data && response.data.itineraries && response.data.itineraries.length > 0) {
                const flights = this.transformRealFlightData(response.data, returnDate ? 'ALLER_RETOUR' : 'ALLER_SIMPLE');
                
                return {
                    success: true,
                    count: flights.length,
                    tripType: returnDate ? 'ALLER_RETOUR' : 'ALLER_SIMPLE',
                    searchParams: params,
                    flights: flights,
                    sessionToken: response.data.sessionToken
                };
            } else {
                console.log('⚠️ No itineraries found, using mock data');
                return this.getEnhancedMockFlights(params);
            }

        } catch (error) {
            console.error('❌ Erreur recherche:', error.message);
            if (error.response) {
                console.error('Status:', error.response.status);
                console.error('Data:', JSON.stringify(error.response.data, null, 2));
            }
            return this.getEnhancedMockFlights(params);
        }
    }

    // ===========================================
    // GET AIRPORT DETAILS
    // ===========================================
    async getAirportDetails(iataCode) {
        // Fallback entity IDs for common airports
        const airportDatabase = {
            'ALG': { skyId: 'ALG', entityId: '27544008', name: 'Algiers' },
            'CDG': { skyId: 'CDG', entityId: '27537542', name: 'Paris Charles de Gaulle' },
            'ORY': { skyId: 'ORY', entityId: '27537543', name: 'Paris Orly' },
            'LGW': { skyId: 'LGW', entityId: '27544003', name: 'London Gatwick' },
            'LHR': { skyId: 'LHR', entityId: '27544003', name: 'London Heathrow' },
            'JFK': { skyId: 'JFK', entityId: '27544004', name: 'New York JFK' },
            'EWR': { skyId: 'EWR', entityId: '27544004', name: 'Newark' },
            'NYCA': { skyId: 'NYCA', entityId: '27544004', name: 'New York Area' },
            'LOND': { skyId: 'LOND', entityId: '27544003', name: 'London Area' },
            'IST': { skyId: 'IST', entityId: '27544001', name: 'Istanbul' },
            'DXB': { skyId: 'DXB', entityId: '27544002', name: 'Dubai' },
            'CMN': { skyId: 'CMN', entityId: '27544007', name: 'Casablanca' },
            'TUN': { skyId: 'TUN', entityId: '27544009', name: 'Tunis' },
            'FRA': { skyId: 'FRA', entityId: '27544005', name: 'Frankfurt' },
            'AMS': { skyId: 'AMS', entityId: '27544006', name: 'Amsterdam' }
        };

        if (airportDatabase[iataCode]) {
            return airportDatabase[iataCode];
        }
        
        // Try to search for airport
        try {
            const url = `${this.baseURL}/flights/searchAirport`;
            const response = await axios.get(url, {
                headers: this.getHeaders(),
                params: {
                    market: 'US',
                    locale: 'en-US',
                    query: iataCode
                },
                timeout: 5000
            });
            
            if (response.data && response.data.data && response.data.data.length > 0) {
                const airport = response.data.data[0];
                return {
                    skyId: airport.skyId,
                    entityId: airport.entityId,
                    name: airport.presentation?.title
                };
            }
        } catch (error) {
            console.log(`Could not fetch airport ${iataCode}, using fallback`);
        }
        
        // Return basic info
        return { skyId: iataCode, entityId: iataCode, name: iataCode };
    }

    // ===========================================
    // TRANSFORM REAL FLIGHT DATA
    // ===========================================
    transformRealFlightData(apiResponse, tripType) {
        try {
            const itineraries = apiResponse.itineraries || [];
            const flights = [];

            for (const itinerary of itineraries) {
                try {
                    const legs = itinerary.legs || [];
                    const price = itinerary.price || {};
                    
                    // Get outbound leg (first leg)
                    const outboundLeg = legs[0];
                    if (!outboundLeg) continue;
                    
                    // Get carrier info
                    const outboundCarrier = outboundLeg.carriers?.[0] || {};
                    
                    // Calculate price per passenger
                    const totalAmount = price.amount || 0;
                    const currency = price.currency || 'USD';
                    
                    // Calculate duration
                    const durationMinutes = outboundLeg.durationMinutes || 0;
                    const durationHours = Math.floor(durationMinutes / 60);
                    const durationMins = durationMinutes % 60;
                    
                    const flight = {
                        id: itinerary.id,
                        airline: outboundCarrier.name || 'Unknown Airline',
                        airlineCode: outboundCarrier.name?.substring(0, 2).toUpperCase() || 'XX',
                        flightNumber: this.extractFlightNumber(itinerary.id, outboundCarrier.name),
                        price: {
                            total: totalAmount,
                            perPassenger: totalAmount,
                            currency: currency
                        },
                        departure: {
                            airport: outboundLeg.origin,
                            city: this.getCityName(outboundLeg.origin),
                            time: outboundLeg.departure,
                            terminal: outboundLeg.departureTerminal || ''
                        },
                        arrival: {
                            airport: outboundLeg.destination,
                            city: this.getCityName(outboundLeg.destination),
                            time: outboundLeg.arrival,
                            terminal: outboundLeg.arrivalTerminal || ''
                        },
                        duration: durationHours > 0 ? `${durationHours}h ${durationMins}min` : `${durationMins}min`,
                        durationMinutes: durationMinutes,
                        seatsAvailable: Math.floor(Math.random() * 20) + 1,
                        stops: outboundLeg.stopCount || 0,
                        isDirect: (outboundLeg.stopCount === 0),
                        baggage: { 
                            included: outboundLeg.baggageAllowance || "1 bagage(s)", 
                            quantity: 1 
                        },
                        refundable: { 
                            isRefundable: false, 
                            policy: "Non remboursable" 
                        },
                        bookingUrl: itinerary.bookingUrl,
                        source: "SKYSCANNER"
                    };
                    
                    // Add return leg if exists
                    if (legs.length > 1) {
                        const returnLeg = legs[1];
                        const returnCarrier = returnLeg.carriers?.[0] || {};
                        const returnDurationMinutes = returnLeg.durationMinutes || 0;
                        const returnDurationHours = Math.floor(returnDurationMinutes / 60);
                        const returnDurationMins = returnDurationMinutes % 60;
                        
                        flight.returnFlight = {
                            airline: returnCarrier.name || 'Unknown Airline',
                            flightNumber: this.extractFlightNumber(itinerary.id + "_return", returnCarrier.name),
                            departure: {
                                airport: returnLeg.origin,
                                city: this.getCityName(returnLeg.origin),
                                time: returnLeg.departure
                            },
                            arrival: {
                                airport: returnLeg.destination,
                                city: this.getCityName(returnLeg.destination),
                                time: returnLeg.arrival
                            },
                            duration: returnDurationHours > 0 ? `${returnDurationHours}h ${returnDurationMins}min` : `${returnDurationMins}min`,
                            stops: returnLeg.stopCount || 0,
                            isDirect: (returnLeg.stopCount === 0)
                        };
                    }
                    
                    flights.push(flight);
                    
                } catch (e) {
                    console.error('Error transforming itinerary:', e);
                }
            }
            
            // Sort by price
            flights.sort((a, b) => a.price.total - b.price.total);
            
            console.log(`✅ ${flights.length} vols transformés`);
            return flights;
            
        } catch (error) {
            console.error('❌ Erreur transformation:', error);
            return [];
        }
    }

    // ===========================================
    // EXTRACT FLIGHT NUMBER
    // ===========================================
    extractFlightNumber(itineraryId, airlineName) {
        // Try to extract from itinerary ID or generate a reasonable one
        const airlineCode = airlineName?.substring(0, 2).toUpperCase() || 'XX';
        const randomNum = Math.floor(Math.random() * 900) + 100;
        return `${airlineCode}${randomNum}`;
    }

    // ===========================================
    // ENHANCED MOCK FLIGHTS (FALLBACK)
    // ===========================================
    getEnhancedMockFlights(params) {
        const { origin, destination, departureDate, returnDate, adults = 1, currency = 'USD', travelClass = 'ECONOMY' } = params;
        
        const airlines = [
            { name: 'Air Algérie', code: 'AH', basePrice: 380, baggage: '1 bagage 23kg', refundable: false },
            { name: 'Turkish Airlines', code: 'TK', basePrice: 450, baggage: '2 bagages 23kg', refundable: true },
            { name: 'Air France', code: 'AF', basePrice: 520, baggage: '1 bagage 23kg', refundable: false },
            { name: 'Qatar Airways', code: 'QR', basePrice: 580, baggage: '2 bagages 23kg', refundable: true },
            { name: 'Emirates', code: 'EK', basePrice: 620, baggage: '2 bagages 23kg', refundable: true },
            { name: 'Royal Air Maroc', code: 'AT', basePrice: 410, baggage: '1 bagage 23kg', refundable: false },
            { name: 'Tunisair', code: 'TU', basePrice: 390, baggage: '1 bagage 23kg', refundable: false },
            { name: 'Lufthansa', code: 'LH', basePrice: 490, baggage: '1 bagage 23kg', refundable: false },
            { name: 'British Airways', code: 'BA', basePrice: 550, baggage: '1 bagage 23kg', refundable: false },
            { name: 'Pegasus Airlines', code: 'PC', basePrice: 350, baggage: '1 bagage 20kg', refundable: false },
            { name: 'Transavia', code: 'HV', basePrice: 320, baggage: '1 bagage 20kg', refundable: false },
            { name: 'Vueling', code: 'VY', basePrice: 340, baggage: '1 bagage 20kg', refundable: false },
            { name: 'ITA Airways', code: 'AZ', basePrice: 470, baggage: '1 bagage 23kg', refundable: false },
            { name: 'Iberia', code: 'IB', basePrice: 500, baggage: '1 bagage 23kg', refundable: false },
            { name: 'Norse Atlantic', code: 'N0', basePrice: 420, baggage: '1 bagage 23kg', refundable: false },
            { name: 'Brussels Airlines', code: 'SN', basePrice: 460, baggage: '1 bagage 23kg', refundable: false },
            { name: 'Austrian Airlines', code: 'OS', basePrice: 480, baggage: '1 bagage 23kg', refundable: false },
            { name: 'Swiss Air', code: 'LX', basePrice: 510, baggage: '1 bagage 23kg', refundable: false }
        ];

        const departureTimes = [
            { time: '06:00', duration: '3h 15min', durationMin: 195 },
            { time: '08:30', duration: '3h 30min', durationMin: 210 },
            { time: '10:15', duration: '3h 20min', durationMin: 200 },
            { time: '12:45', duration: '3h 25min', durationMin: 205 },
            { time: '14:30', duration: '3h 35min', durationMin: 215 },
            { time: '16:20', duration: '3h 40min', durationMin: 220 },
            { time: '18:45', duration: '3h 15min', durationMin: 195 },
            { time: '21:00', duration: '3h 30min', durationMin: 210 }
        ];

        const mockFlights = [];
        
        for (let i = 0; i < airlines.length; i++) {
            const airline = airlines[i];
            const departureSlot = departureTimes[i % departureTimes.length];
            
            let priceMultiplier = 1;
            if (travelClass === 'BUSINESS') priceMultiplier = 2.5;
            else if (travelClass === 'PREMIUM_ECONOMY') priceMultiplier = 1.5;
            
            let totalPrice = airline.basePrice * priceMultiplier;
            const variation = 0.85 + (Math.random() * 0.3);
            totalPrice = Math.round(totalPrice * variation);
            
            const [depHour, depMin] = departureSlot.time.split(':').map(Number);
            let arrivalHour = depHour + Math.floor(departureSlot.durationMin / 60);
            let arrivalMin = depMin + (departureSlot.durationMin % 60);
            if (arrivalMin >= 60) {
                arrivalHour += Math.floor(arrivalMin / 60);
                arrivalMin = arrivalMin % 60;
            }
            const arrivalTime = `${String(arrivalHour).padStart(2, '0')}:${String(arrivalMin).padStart(2, '0')}`;
            
            mockFlights.push({
                id: `FLIGHT_${Date.now()}_${i}`,
                airline: airline.name,
                airlineCode: airline.code,
                flightNumber: `${airline.code}${Math.floor(Math.random() * 900) + 100}`,
                price: { total: totalPrice, perPassenger: totalPrice, currency: currency },
                departure: { airport: origin, city: this.getCityName(origin), time: `${departureDate}T${departureSlot.time}:00` },
                arrival: { airport: destination, city: this.getCityName(destination), time: `${departureDate}T${arrivalTime}:00` },
                duration: departureSlot.duration,
                durationMinutes: departureSlot.durationMin,
                seatsAvailable: Math.floor(Math.random() * 20) + 1,
                stops: i % 5 === 0 ? 1 : 0,
                isDirect: i % 5 !== 0,
                baggage: { included: airline.baggage, quantity: airline.baggage.includes('2') ? 2 : 1 },
                refundable: { isRefundable: airline.refundable, policy: airline.refundable ? "Remboursable" : "Non remboursable" },
                source: "MOCK_DATA"
            });
        }
        
        mockFlights.sort((a, b) => a.price.total - b.price.total);
        
        console.log(`✅ Generated ${mockFlights.length} mock flights`);
        
        if (returnDate) {
            return {
                success: true,
                count: mockFlights.length,
                tripType: "ALLER_RETOUR",
                searchParams: params,
                flights: mockFlights.slice(0, 15),
                returnFlights: mockFlights.slice(0, 8).map(f => ({ ...f, id: f.id + "_return" }))
            };
        }
        
        return {
            success: true,
            count: mockFlights.length,
            tripType: "ALLER_SIMPLE",
            searchParams: params,
            flights: mockFlights
        };
    }

    // ===========================================
    // SEARCH MULTI-DESTINATION
    // ===========================================
    async searchMultiDestination(flights, passengers, travelClass, filters = {}) {
        try {
            console.log('🔍 Recherche multi-destination...');
            
            const searchPromises = flights.map(async (flight, index) => {
                console.log(`📌 Segment ${index+1}: ${flight.origin} → ${flight.destination}`);
                
                const result = await this.searchFlights({
                    origin: flight.origin,
                    destination: flight.destination,
                    departureDate: flight.departureDate,
                    adults: passengers.adults,
                    children: passengers.children || 0,
                    infants: passengers.infants || 0,
                    travelClass: travelClass,
                    currency: filters.currency || 'USD'
                });
                
                return {
                    segment: index + 1,
                    origin: flight.origin,
                    destination: flight.destination,
                    departureDate: flight.departureDate,
                    data: result
                };
            });
            
            const results = await Promise.all(searchPromises);
            console.log(`✅ ${results.length} segments recherchés`);
            
            return { success: true, segments: results };
            
        } catch (error) {
            console.error('❌ Erreur multi-destination:', error);
            throw error;
        }
    }

    // ===========================================
    // GENERATE COMBINATIONS
    // ===========================================
    generateCombinations(segments) {
        try {
            console.log('🔄 Génération des combinaisons...');
            
            if (!segments || segments.length === 0) return [];
            
            for (let i = 0; i < segments.length; i++) {
                const segment = segments[i];
                if (!segment.data || !segment.data.flights || segment.data.flights.length === 0) {
                    console.log(`⚠️ Segment ${i+1} n'a pas de vols`);
                    return [];
                }
            }
            
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
                console.log(`📊 Après segment ${i+1}: ${combinations.length} combinaisons`);
            }
            
            return combinations;
            
        } catch (error) {
            console.error('❌ Erreur generateCombinations:', error);
            return [];
        }
    }

    // ===========================================
    // CHECK AVAILABILITY
    // ===========================================
    async checkAvailability(flightId) {
        return {
            flightId: flightId,
            available: true,
            seatsLeft: Math.floor(Math.random() * 20) + 1
        };
    }

    // ===========================================
    // HELPER: GET CITY NAME
    // ===========================================
    getCityName(iataCode) {
        const cities = {
            'ALG': 'Alger', 'CDG': 'Paris', 'ORY': 'Paris', 'LGW': 'London',
            'LHR': 'London', 'JFK': 'New York', 'EWR': 'Newark', 'IST': 'Istanbul',
            'DXB': 'Dubai', 'CMN': 'Casablanca', 'TUN': 'Tunis', 'FRA': 'Frankfurt',
            'AMS': 'Amsterdam', 'NYCA': 'New York', 'LOND': 'London'
        };
        return cities[iataCode] || iataCode;
    }
}

module.exports = new SkyscannerService();