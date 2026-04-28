const Eureka = require('eureka-js-client').Eureka;

const eurekaClient = new Eureka({
    instance: {
        app: 'MS-PAIEMENT',
        hostName: 'http://localhost:3003/',
        ipAddr: '127.0.0.1',
        statusPageUrl: 'http://localhost:3003/api/payments/health',
        healthCheckUrl: 'http://localhost:3003/api/payments/health',
        homePageUrl: 'http://localhost:3003',
        port: {
            '$': 3003,
            '@enabled': 'true',
        },
        vipAddress: 'ms-paiement',
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
eurekaClient.on('started', () => {
    console.log(' MS-PAIEMENT enregistré dans Eureka!');
    console.log('   Voir: http://localhost:8888');
});

eurekaClient.on('error', (error) => {
    console.log('❌ Erreur de connexion à Eureka');
});

// Démarrer l'enregistrement
eurekaClient.start((error) => {
    if (error) {
        console.log(' Service démarré mais non enregistré dans Eureka');
        console.log('   Vérifiez que Eureka tourne sur http://localhost:8888');
    }
});

module.exports = eurekaClient;