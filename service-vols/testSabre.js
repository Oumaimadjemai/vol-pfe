const sabreService = require('./src/services/sabreService');

async function test() {
    const result = await sabreService.searchFlights({
        origin: 'CDG',
        destination: 'JFK',
        departureDate: '2025-05-15',
        adults: 1
    });
    
    console.log('Résultat:', JSON.stringify(result, null, 2));
}

test();