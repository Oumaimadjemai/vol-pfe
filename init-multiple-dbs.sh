#!/bin/bash
# init-multiple-dbs.sh

set -e
set -u

function create_database() {
    local database=$1
    echo "Creating database '$database'"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        CREATE DATABASE $database;
        GRANT ALL PRIVILEGES ON DATABASE $database TO $POSTGRES_USER;
EOSQL
}

# Create super admin database (already created by PostgreSQL)
echo "Super admin database already exists"

# Future agency databases will be created dynamically by the application
echo "Agency databases will be created dynamically by the application"