#!/bin/sh
SCRIPT_DIR="/docker-entrypoint-initdb.d"
PGPASSWORD=${POSTGRES_PASSWORD} psql -f ${SCRIPT_DIR}/db-create.psql
PGPASSWORD=${POSTGRES_PASSWORD} psql kea kea -f ${SCRIPT_DIR}/kea-schema.psql
PGPASSWORD=${POSTGRES_PASSWORD} psql pdns pdns -f ${SCRIPT_DIR}/pdns-schema.psql
PGPASSWORD=${POSTGRES_PASSWORD} psql pdns pdns -f ${SCRIPT_DIR}/pdns-init.psql
