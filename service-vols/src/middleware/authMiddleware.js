const jwt = require('jsonwebtoken');
const config = require('../config/config');

const authMiddleware = (req, res, next) => {
    try {
        const authHeader = req.headers.authorization;
        
        if (!authHeader) {
            return res.status(401).json({ 
                message: 'Token manquant. Veuillez vous authentifier.' 
            });
        }

        const token = authHeader.split(' ')[1];
        const decoded = jwt.verify(token, config.jwt.secret);
        
        req.user = decoded;
        next();
    } catch (error) {
        return res.status(401).json({ 
            message: 'Token invalide ou expiré' 
        });
    }
};

module.exports = authMiddleware;