const Eureka = require('eureka-js-client').Eureka;

const client = new Eureka({
   instance: {
  app: 'service-vols',

  hostName: 'service-vols',   // 🔥 IMPORTANT FIX
  ipAddr: 'service-vols',

  port: {
    '$': 3002,
    '@enabled': true,
  },


        vipAddress: 'service-vols',

        statusPageUrl: 'http://service-vols:3002/health',
        healthCheckUrl: 'http://service-vols:3002/health',
        homePageUrl: 'http://service-vols:3002',

        dataCenterInfo: {
            '@class': 'com.netflix.appinfo.InstanceInfo$DefaultDataCenterInfo',
            name: 'MyOwn',
        },

        registerWithEureka: true,
        fetchRegistry: true
    },

    eureka: {
        // 🔥 THIS IS THE REAL FIX
        host: process.env.EUREKA_HOST || 'registry',
        port: process.env.EUREKA_PORT || 8888,
        servicePath: '/eureka/apps/',

        maxRetries: 5,
        requestRetryDelay: 2000,
        preferSameZone: true,
        useDns: false
    }
});

// Events
client.on('started', () => {
    console.log('SERVICE-VOLS enregistré dans Eureka!');
    console.log('Voir: http://registry:8888');
});

client.on('error', (error) => {
    console.log('Erreur Eureka:', error.message);
});

// Start
client.start((error) => {
    if (error) {
        console.log('Eureka registration failed');
    }
});

module.exports = client;