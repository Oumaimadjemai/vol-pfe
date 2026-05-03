const Eureka = require('eureka-js-client').Eureka;

const eurekaClient = new Eureka({
    instance: {
        app: 'MS-PAIEMENT',
        instanceId: `ms-paiement:${process.env.PORT || 3003}`,
        hostName: process.env.EUREKA_HOST || 'ms-paiement',  // ← Nom du service Docker
        ipAddr: process.env.EUREKA_IP || 'ms-paiement',     // ← Nom du service Docker
        statusPageUrl: `http://${process.env.EUREKA_HOST || 'ms-paiement'}:${process.env.PORT || 3003}/api/payments/health`,
        healthCheckUrl: `http://${process.env.EUREKA_HOST || 'ms-paiement'}:${process.env.PORT || 3003}/api/payments/health`,
        homePageUrl: `http://${process.env.EUREKA_HOST || 'ms-paiement'}:${process.env.PORT || 3003}`,
        port: {
            '$': process.env.PORT || 3003,
            '@enabled': true,
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
        host: process.env.EUREKA_SERVER_HOST || 'registry', 
        port: process.env.EUREKA_SERVER_PORT || 8888,
        servicePath: '/eureka/apps/',
        maxRetries: 10,
        requestRetryDelay: 2000,
        preferSameZone: true,
        useDns: false
    }
});

// Gestionnaire d'événements
eurekaClient.on('started', () => {
    console.log('✅ MS-PAIEMENT enregistré dans Eureka!');
    console.log(`   Eureka Server: http://${process.env.EUREKA_SERVER_HOST || 'registry'}:8888`);
    console.log(`   Service: http://${process.env.EUREKA_HOST || 'ms-paiement'}:${process.env.PORT || 3003}`);
});

eurekaClient.on('error', (error) => {
    console.error('❌ Erreur de connexion à Eureka:', error.message);
});

eurekaClient.on('registered', () => {
    console.log('✅ Service MS-PAIEMENT enregistré avec succès!');
});

eurekaClient.on('deregistered', () => {
    console.log('⚠️ Service MS-PAIEMENT désenregistré d\'Eureka');
});

// Démarrer l'enregistrement
eurekaClient.start((error) => {
    if (error) {
        console.error('❌ Service démarré mais non enregistré dans Eureka');
        console.error('   Erreur:', error.message);
        console.log('   Vérifiez que Eureka tourne sur registry:8888');
    } else {
        console.log('🔄 Tentative d\'enregistrement dans Eureka...');
    }
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('🛑 Arrêt du service...');
    eurekaClient.stop();
    process.exit();
});

module.exports = eurekaClient;