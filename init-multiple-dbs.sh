#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE service_auth_db;
    CREATE DATABASE ms_reservation_db;
    CREATE DATABASE ms_destination_db;
EOSQL