const Eureka = require('eureka-js-client').Eureka;

// Get environment variables with proper defaults for Docker
const eurekaHost = process.env.EUREKA_SERVER_HOST || process.env.EUREKA_HOST || 'registry';
const eurekaPort = process.env.EUREKA_SERVER_PORT || process.env.EUREKA_PORT || 8888;

console.log(`Connecting to Eureka at: ${eurekaHost}:${eurekaPort}`);

const client = new Eureka({
  instance: {
    app: 'service-vols',
    hostName: process.env.EUREKA_INSTANCE_HOST || 'service-vols',
    ipAddr: process.env.EUREKA_INSTANCE_IP || 'service-vols',
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
    host: eurekaHost,
    port: eurekaPort,
    servicePath: '/eureka/apps/',
    maxRetries: 10,
    requestRetryDelay: 2000,
    preferSameZone: true,
    useDns: false
  }
});

// Events
client.on('registered', () => {
  console.log('✅ SERVICE-VOLS successfully registered with Eureka!');
  console.log(`   Eureka server: http://${eurekaHost}:${eurekaPort}`);
});

client.on('started', () => {
  console.log('✅ Eureka client started for SERVICE-VOLS');
});

client.on('error', (error) => {
  console.error('❌ Eureka error:', error.message);
});

client.on('registryUpdated', () => {
  console.log('📋 Eureka registry updated');
});

// Start the client
client.start((error) => {
  if (error) {
    console.error('❌ Failed to register with Eureka:', error.message);
    console.error('   Make sure Eureka is running at:', `http://${eurekaHost}:${eurekaPort}`);
  } else {
    console.log('✅ Eureka registration completed successfully');
  }
});

module.exports = client;