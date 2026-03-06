// Point d'entrée principal
const app = require('./src/app');
const config = require('./src/config/config');
require('./src/eureka'); 

const PORT = config.port;

app.listen(PORT, () => {
    console.log(`
     Service Vols démarré!
     Port: ${PORT}
     http://localhost:${PORT}
     Health: http://localhost:${PORT}/health
    `);
});