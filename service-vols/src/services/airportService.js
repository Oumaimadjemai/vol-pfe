// const axios = require('axios');
// const config = require('../config/config');

// class AirportService {
//     constructor() {
//         this.baseURL = config.amadeus.environment === 'production' 
//             ? 'https://api.amadeus.com'
//             : 'https://test.api.amadeus.com';
//         this.cache = new Map();
//         this.cacheTime = new Map();
//     }

   
//     //  TOKEN (via AmadeusService)
//     // ===========================================
//     async getToken() {
//         const amadeusService = require('./amadeusService');
//         return await amadeusService.getAccessToken();
//     }

//     // RECHERCHER DES AÉROPORTS VIA AMADEUS
//     // ===========================================
//     async searchAirports(keyword, max = 20) {
//         try {
//             console.log(` Recherche d'aéroports: "${keyword}"`);
            
//             // Vérifier le cache (5 minutes)
//             const cacheKey = `search_${keyword}_${max}`;
//             if (this.cache.has(cacheKey)) {
//                 const cached = this.cache.get(cacheKey);
//                 const cacheAge = Date.now() - (this.cacheTime.get(cacheKey) || 0);
//                 if (cacheAge < 300000) { // 5 minutes
//                     console.log(' Résultats depuis le cache');
//                     return cached;
//                 }
//             }

//             const token = await this.getToken();
            
//             // Appel à l'API Amadeus
//             const response = await axios.get(`${this.baseURL}/v1/reference-data/locations`, {
//                 headers: { 'Authorization': `Bearer ${token}` },
//                 params: {
//                     keyword: keyword,
//                     subType: 'AIRPORT',
//                     'page[limit]': max
//                 }
//             });

//             // Transformer les données
//             const airports = response.data.data.map(item => ({
//                 code: item.iataCode,
//                 name: item.name,
//                 city: item.address.cityName,
//                 country: item.address.countryName,
//                 latitude: item.geoCode.latitude,
//                 longitude: item.geoCode.longitude,
//                 timezone: item.timeZone.offset
//             }));

//             // Mettre en cache
//             this.cache.set(cacheKey, airports);
//             this.cacheTime.set(cacheKey, Date.now());

//             console.log(` ${airports.length} aéroports trouvés`);
//             return airports;

//         } catch (error) {
//             console.error(' Erreur recherche aéroports:', error.response?.data || error.message);
            
//             // En cas d'erreur, retourner une liste de secours
//             return this.getFallbackAirports(keyword);
//         }
//     }

//     // OBTENIR LES AÉROPORTS POPULAIRES
//     // ===========================================
//     async getPopularAirports() {
//         try {
//             const cacheKey = 'popular';
//             if (this.cache.has(cacheKey)) {
//                 const cached = this.cache.get(cacheKey);
//                 const cacheAge = Date.now() - (this.cacheTime.get(cacheKey) || 0);
//                 if (cacheAge < 3600000) { // 1 heure
//                     return cached;
//                 }
//             }

//             const token = await this.getToken();
            
//             // Liste des grandes villes pour avoir des aéroports populaires
//             const cities = ['PARI', 'LON', 'NYC', 'DXB', 'IST', 'CAS', 'ALG', 'TUN', 'CAI', 'JNB'];
            
//             const promises = cities.map(city => 
//                 axios.get(`${this.baseURL}/v1/reference-data/locations`, {
//                     headers: { 'Authorization': `Bearer ${token}` },
//                     params: {
//                         keyword: city,
//                         subType: 'AIRPORT',
//                         'page[limit]': 5
//                     }
//                 })
//             );

//             const responses = await Promise.all(promises);
            
//             let allAirports = [];
//             responses.forEach(response => {
//                 if (response.data.data) {
//                     const airports = response.data.data.map(item => ({
//                         code: item.iataCode,
//                         name: item.name,
//                         city: item.address.cityName,
//                         country: item.address.countryName,
//                         latitude: item.geoCode.latitude,
//                         longitude: item.geoCode.longitude,
//                         timezone: item.timeZone.offset
//                     }));
//                     allAirports = [...allAirports, ...airports];
//                 }
//             });

//             // Enlever les doublons
//             const uniqueAirports = Array.from(
//                 new Map(allAirports.map(a => [a.code, a])).values()
//             );

//             this.cache.set(cacheKey, uniqueAirports);
//             this.cacheTime.set(cacheKey, Date.now());

//             return uniqueAirports;

//         } catch (error) {
//             console.error(' Erreur aéroports populaires:', error);
//             return this.getFallbackAirports('');
//         }
//     }

  
//     // LISTE (QUAND AMADEUS EST INDISPONIBLE)
//     // ===========================================
//     getFallbackAirports(keyword = '') {
//         const fallbackList = [
//             { code: "CDG", name: "Charles de Gaulle Airport", city: "Paris", country: "France" },
//             { code: "ORY", name: "Orly Airport", city: "Paris", country: "France" },
//             { code: "LHR", name: "Heathrow Airport", city: "Londres", country: "Royaume-Uni" },
//             { code: "LGW", name: "Gatwick Airport", city: "Londres", country: "Royaume-Uni" },
//             { code: "JFK", name: "John F. Kennedy International Airport", city: "New York", country: "États-Unis" },
//             { code: "EWR", name: "Newark Liberty International Airport", city: "New York", country: "États-Unis" },
//             { code: "DXB", name: "Dubai International Airport", city: "Dubaï", country: "Émirats Arabes Unis" },
//             { code: "AUH", name: "Abu Dhabi International Airport", city: "Abou Dabi", country: "Émirats Arabes Unis" },
//             { code: "FCO", name: "Leonardo da Vinci International Airport", city: "Rome", country: "Italie" },
//             { code: "MXP", name: "Malpensa Airport", city: "Milan", country: "Italie" },
//             { code: "BCN", name: "Barcelona-El Prat Airport", city: "Barcelone", country: "Espagne" },
//             { code: "MAD", name: "Adolfo Suárez Madrid-Barajas Airport", city: "Madrid", country: "Espagne" },
//             { code: "AMS", name: "Amsterdam Airport Schiphol", city: "Amsterdam", country: "Pays-Bas" },
//             { code: "FRA", name: "Frankfurt Airport", city: "Francfort", country: "Allemagne" },
//             { code: "MUC", name: "Munich Airport", city: "Munich", country: "Allemagne" },
//             { code: "IST", name: "Istanbul Airport", city: "Istanbul", country: "Turquie" },
//             { code: "SAW", name: "Sabiha Gökçen International Airport", city: "Istanbul", country: "Turquie" },
//             { code: "DSS", name: "Blaise Diagne International Airport", city: "Dakar", country: "Sénégal" },
//             { code: "ALG", name: "Houari Boumediene Airport", city: "Alger", country: "Algérie" },
//             { code: "CMN", name: "Mohammed V International Airport", city: "Casablanca", country: "Maroc" },
//             { code: "RAK", name: "Marrakech Menara Airport", city: "Marrakech", country: "Maroc" },
//             { code: "TUN", name: "Tunis-Carthage International Airport", city: "Tunis", country: "Tunisie" },
//             { code: "CAI", name: "Cairo International Airport", city: "Le Caire", country: "Égypte" },
//             { code: "NBO", name: "Jomo Kenyatta International Airport", city: "Nairobi", country: "Kenya" },
//             { code: "JNB", name: "O.R. Tambo International Airport", city: "Johannesburg", country: "Afrique du Sud" }
//         ];

//         if (!keyword) return fallbackList;

//         const searchTerm = keyword.toLowerCase();
//         return fallbackList.filter(airport => 
//             airport.code.toLowerCase().includes(searchTerm) ||
//             airport.name.toLowerCase().includes(searchTerm) ||
//             airport.city.toLowerCase().includes(searchTerm) ||
//             airport.country.toLowerCase().includes(searchTerm)
//         );
//     }
// }

// module.exports = new AirportService();

const axios = require('axios');
const config = require('../config/config');

class AirportService {
    constructor() {
        this.baseURL = 'https://skyscanner-flights-travel-api.p.rapidapi.com';
        this.apiKey = config.rapidapi.key;
        this.apiHost = 'skyscanner-flights-travel-api.p.rapidapi.com';
        this.cache = new Map();
        this.cacheTime = new Map();
    }

    getHeaders() {
        return {
            'x-rapidapi-key': this.apiKey,
            'x-rapidapi-host': this.apiHost,
            'Content-Type': 'application/json'
        };
    }

    async searchAirports(keyword, max = 20) {
        try {
            console.log(`🔍 Recherche d'aéroports: "${keyword}"`);
            
            const cacheKey = `search_${keyword}_${max}`;
            if (this.cache.has(cacheKey)) {
                const cached = this.cache.get(cacheKey);
                const cacheAge = Date.now() - (this.cacheTime.get(cacheKey) || 0);
                if (cacheAge < 300000) {
                    console.log('📦 Résultats depuis le cache');
                    return cached;
                }
            }

            // Use the correct searchAirport endpoint
            const url = `${this.baseURL}/flights/searchAirport`;
            
            const response = await axios.get(url, {
                headers: this.getHeaders(),
                params: {
                    market: 'DZ',
                    locale: 'fr-FR',
                    query: keyword
                }
            });

            const airports = [];
            if (response.data && response.data.data) {
                for (const item of response.data.data) {
                    airports.push({
                        code: item.skyId,
                        name: item.presentation?.title || item.name,
                        city: item.presentation?.subtitle?.split(',')[0] || '',
                        country: item.presentation?.subtitle?.split(',')[1] || '',
                        entityId: item.entityId,
                        latitude: 0,
                        longitude: 0,
                        timezone: 'UTC'
                    });
                }
            }

            const results = airports.slice(0, max);
            
            this.cache.set(cacheKey, results);
            this.cacheTime.set(cacheKey, Date.now());

            console.log(`✅ ${results.length} aéroports trouvés`);
            return results;

        } catch (error) {
            console.error('❌ Erreur recherche aéroports:', error.message);
            return this.getFallbackAirports(keyword);
        }
    }

    async getPopularAirports() {
        const popular = [
            { code: "ALG", name: "Houari Boumediene Airport", city: "Alger", country: "Algérie", entityId: "27544008" },
            { code: "CDG", name: "Charles de Gaulle Airport", city: "Paris", country: "France", entityId: "27537542" },
            { code: "ORY", name: "Orly Airport", city: "Paris", country: "France", entityId: "27537543" },
            { code: "IST", name: "Istanbul Airport", city: "Istanbul", country: "Turquie", entityId: "27544001" },
            { code: "DXB", name: "Dubai International Airport", city: "Dubaï", country: "UAE", entityId: "27544002" },
            { code: "LHR", name: "Heathrow Airport", city: "Londres", country: "Royaume-Uni", entityId: "27544003" },
            { code: "JFK", name: "John F. Kennedy Airport", city: "New York", country: "USA", entityId: "27544004" },
            { code: "CMN", name: "Mohammed V Airport", city: "Casablanca", country: "Maroc", entityId: "27544007" },
            { code: "TUN", name: "Tunis-Carthage Airport", city: "Tunis", country: "Tunisie", entityId: "27544009" },
            { code: "FRA", name: "Frankfurt Airport", city: "Francfort", country: "Allemagne", entityId: "27544005" },
            { code: "AMS", name: "Schiphol Airport", city: "Amsterdam", country: "Pays-Bas", entityId: "27544006" }
        ];
        
        return popular;
    }

    getFallbackAirports(keyword = '') {
        const fallbackList = [
            { code: "ALG", name: "Houari Boumediene Airport", city: "Alger", country: "Algérie", entityId: "27544008" },
            { code: "CDG", name: "Charles de Gaulle Airport", city: "Paris", country: "France", entityId: "27537542" },
            { code: "ORY", name: "Orly Airport", city: "Paris", country: "France", entityId: "27537543" },
            { code: "IST", name: "Istanbul Airport", city: "Istanbul", country: "Turquie", entityId: "27544001" },
            { code: "DXB", name: "Dubai International Airport", city: "Dubaï", country: "UAE", entityId: "27544002" },
            { code: "LHR", name: "Heathrow Airport", city: "Londres", country: "Royaume-Uni", entityId: "27544003" },
            { code: "JFK", name: "John F. Kennedy Airport", city: "New York", country: "USA", entityId: "27544004" },
            { code: "CMN", name: "Mohammed V Airport", city: "Casablanca", country: "Maroc", entityId: "27544007" },
            { code: "TUN", name: "Tunis-Carthage Airport", city: "Tunis", country: "Tunisie", entityId: "27544009" },
            { code: "FRA", name: "Frankfurt Airport", city: "Francfort", country: "Allemagne", entityId: "27544005" },
            { code: "AMS", name: "Schiphol Airport", city: "Amsterdam", country: "Pays-Bas", entityId: "27544006" }
        ];

        if (!keyword) return fallbackList;

        const searchTerm = keyword.toLowerCase();
        return fallbackList.filter(airport => 
            airport.code.toLowerCase().includes(searchTerm) ||
            airport.name.toLowerCase().includes(searchTerm) ||
            airport.city.toLowerCase().includes(searchTerm) ||
            airport.country.toLowerCase().includes(searchTerm)
        );
    }
}

module.exports = new AirportService();