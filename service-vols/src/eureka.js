const Eureka = require('eureka-js-client').Eureka;

const client = new Eureka({
    instance: {
        app: 'SERVICE-VOLS',                    
        hostName: 'localhost',
        ipAddr: '127.0.0.1',
        statusPageUrl: 'http://localhost:3002/health',
        healthCheckUrl: 'http://localhost:3002/health',
        homePageUrl: 'http://localhost:3002',
        port: {
            '$': 3002,
            '@enabled': 'true',
        },
        vipAddress: 'service-vols',
        dataCenterInfo: {
            '@class': 'com.netflix.appinfo.InstanceInfo$DefaultDataCenterInfo',
            name: 'MyOwn',
        },
        registerWithEureka: true,
        fetchRegistry: true,
        leaseRenewalIntervalInSeconds: 30,
        leaseExpirationDurationInSeconds: 90
    },
    eureka: {
        host: 'localhost',
        port: 8888,
        servicePath: '/eureka/apps/',
        maxRetries: 5,
        requestRetryDelay: 2000,
        preferSameZone: true,
        useDns: false
    }
});

// Gestionnaire d'événements
client.on('started', () => {
    console.log(' SERVICE-VOLS enregistré dans Eureka!');
    console.log('   Voir: http://localhost:8888');
});

client.on('error', (error) => {
    console.log(' Erreur de connexion à Eureka');
});

// Démarrer l'enregistrement
client.start((error) => {
    if (error) {
        console.log(' Service démarré mais non enregistré dans Eureka');
        console.log('   Vérifiez que Eureka tourne sur http://localhost:8888');
    }
});

module.exports = client;